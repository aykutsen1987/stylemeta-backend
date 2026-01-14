from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import uuid
import base64
import tempfile
from PIL import Image, ImageDraw, ImageFont
import io

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sadece Kolors için sabit endpoint (deneme sonuçlarına göre en olası yollar)
KOLORS_URLS = [
    "https://kwai-kolors-kolors-virtual-try-on.hf.space/predict",
    "https://kwai-kolors-kolors-virtual-try-on.hf.space/run/predict",
    "https://kwai-kolors-kolors-virtual-try-on.hf.space/call/predict"
]

@app.get("/")
def health():
    return {
        "status": "StyleMeta Proxy - Kolors Virtual Try-On",
        "note": "POST /tryon ile person + garment gönderin"
    }

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...),   # garment
):
    uid = str(uuid.uuid4())[:8]
    temp_dir = tempfile.gettempdir()
    
    person_path = os.path.join(temp_dir, f"{uid}_person.jpg")
    cloth_path = os.path.join(temp_dir, f"{uid}_cloth.jpg")
    result_path = os.path.join(temp_dir, f"{uid}_result.jpg")
    
    try:
        person_bytes = await person.read()
        cloth_bytes = await cloth.read()
        
        with open(person_path, "wb") as f: f.write(person_bytes)
        with open(cloth_path, "wb") as f: f.write(cloth_bytes)
        
        print(f"İstek alındı → person: {len(person_bytes)}B, garment: {len(cloth_bytes)}B")
        
        # Base64'e çevir (data URI prefix ile – Gradio genelde kabul eder)
        def to_b64(data: bytes) -> str:
            return f"data:image/jpeg;base64,{base64.b64encode(data).decode('utf-8')}"
        
        person_b64 = to_b64(person_bytes)
        cloth_b64 = to_b64(cloth_bytes)
        
        # Payload – Kolors için muhtemel input sırası: person, garment, seed?, random?
        payload = {
            "data": [
                person_b64,           # 0: person image
                cloth_b64,            # 1: garment image
                42,                   # 2: seed (sabit, random istemiyorsak)
                False                 # 3: random seed checkbox (False = sabit seed kullan)
            ]
        }
        
        success = False
        response_text = ""
        
        # Farklı endpoint'leri sırayla dene
        for url in KOLORS_URLS:
            print(f"Deneniyor: {url}")
            try:
                resp = requests.post(url, json=payload, timeout=180)
                print(f"Status: {resp.status_code} | Response: {resp.text[:200]}...")
                
                if resp.status_code == 200:
                    result = resp.json()
                    # Gradio genelde {"data": [image_base64 veya dict]} döner
                    if "data" in result and isinstance(result["data"], list) and result["data"]:
                        output = result["data"][0]
                        
                        if isinstance(output, str) and "," in output:
                            b64_part = output.split(",", 1)[1]
                            img_bytes = base64.b64decode(b64_part)
                            
                            if len(img_bytes) > 5000:  # mantıklı boyutta mı kontrol
                                with open(result_path, "wb") as f:
                                    f.write(img_bytes)
                                success = True
                                break
                        
                        elif isinstance(output, dict) and "url" in output:
                            # Bazı space'ler URL döner
                            img_resp = requests.get(output["url"])
                            if img_resp.status_code == 200:
                                with open(result_path, "wb") as f:
                                    f.write(img_resp.content)
                                success = True
                                break
            except Exception as ex:
                print(f"Hata ({url}): {ex}")
        
        if success:
            return FileResponse(
                result_path,
                media_type="image/jpeg",
                filename="tryon_result.jpg",
                headers={"X-Success": "true"}
            )
        else:
            # Hata durumunda görsel hata ekranı üret
            img = Image.new('RGB', (600, 400), color=(30, 30, 40))
            draw = ImageDraw.Draw(img)
            draw.text((50, 150), "Kolors API hatası aldı", fill=(255, 100, 100), font_size=30)
            draw.text((50, 220), "Logları kontrol et: Render dashboard", fill=(200, 200, 255))
            img.save(result_path)
            return FileResponse(result_path, media_type="image/jpeg")

    except Exception as e:
        print(f"Genel hata: {e}")
        return {"error": str(e)}
    
    finally:
        for p in [person_path, cloth_path, result_path]:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
