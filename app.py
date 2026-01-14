from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import uuid
import shutil
import base64
import tempfile

app = FastAPI(title="StyleMeta Backend")

# ✅ CORS AYARLARI (Android için gerekli)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tüm origin'lere izin ver
    allow_credentials=True,
    allow_methods=["*"],   # Tüm method'lara izin ver
    allow_headers=["*"],   # Tüm header'lara izin ver
)

# ✅ UPLOAD KLASÖRLERİ
UPLOAD_DIR = tempfile.gettempdir()  # Render'da geçici dizin kullan
RESULT_DIR = os.path.join(UPLOAD_DIR, "results")
os.makedirs(RESULT_DIR, exist_ok=True)

# ✅ TEST MODU (Hugging Face olmadan çalışsın)
TEST_MODE = True  # Önce True yapın, çalışınca False yapın

@app.get("/")
def health():
    return {"status": "StyleMeta backend running", "endpoint": "/tryon"}

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...)
):
    """Android'den gelen isteği işler - /tryon endpoint'i"""
    
    print(f"📱 Android'den istek geldi: person={person.filename}, cloth={cloth.filename}")
    
    # Benzersiz dosya isimleri
    uid = str(uuid.uuid4())[:8]
    person_path = os.path.join(UPLOAD_DIR, f"{uid}_person.jpg")
    cloth_path = os.path.join(UPLOAD_DIR, f"{uid}_cloth.jpg")
    result_path = os.path.join(RESULT_DIR, f"{uid}_result.jpg")

    try:
        # 1. DOSYALARI KAYDET
        print(f"💾 Dosyalar kaydediliyor: {person_path}")
        
        with open(person_path, "wb") as f:
            content = await person.read()
            f.write(content)
            print(f"✅ Person dosyası kaydedildi: {len(content)} bytes")
        
        with open(cloth_path, "wb") as f:
            content = await cloth.read()
            f.write(content)
            print(f"✅ Cloth dosyası kaydedildi: {len(content)} bytes")

        # 2. TEST MODU: Hemen cevap dön
        if TEST_MODE:
            print("🧪 TEST MODU: Hugging Face'siz cevap dönülüyor")
            
            # Test görseli oluştur (basit bir JPEG)
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (400, 600), color='lightblue')
            d = ImageDraw.Draw(img)
            d.text((100, 250), "TRY-ON TEST\nAndroid OK!", fill='black')
            img.save(result_path, 'JPEG')
            
            print(f"✅ Test görseli oluşturuldu: {result_path}")
            
            return FileResponse(
                result_path,
                media_type="image/jpeg",
                filename="tryon_result.jpg"
            )

        # 3. HUGGING FACE İSTEĞİ (TEST_MODE=False olduğunda)
        print("🚀 Hugging Face'e istek gönderiliyor...")
        
        # HF Space URL'si (token gerekebilir)
        HF_SPACE_URL = "https://jjlealse-idm-vton.hf.space/run/predict"
        HF_TOKEN = os.getenv("HF_TOKEN", "")
        
        headers = {}
        if HF_TOKEN:
            headers["Authorization"] = f"Bearer {HF_TOKEN}"
        
        # Resimleri base64'e çevir
        def img_to_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        
        payload = {
            "data": [
                f"data:image/jpeg;base64,{img_to_base64(person_path)}",
                f"data:image/jpeg;base64,{img_to_base64(cloth_path)}"
            ]
        }
        
        # HF'e istek gönder
        response = requests.post(
            HF_SPACE_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            error_msg = f"HF Hatası: {response.status_code}"
            print(f"❌ {error_msg}")
            raise HTTPException(502, detail=error_msg)
        
        result = response.json()
        
        # Sonucu kaydet
        if "data" in result and result["data"]:
            img_data = result["data"][0]
            if "," in img_data:
                img_data = img_data.split(",")[1]
            
            with open(result_path, "wb") as f:
                f.write(base64.b64decode(img_data))
            
            print(f"✅ HF'den sonuç alındı: {result_path}")
            
            return FileResponse(
                result_path,
                media_type="image/jpeg",
                filename="tryon_result.jpg"
            )
        else:
            raise HTTPException(503, detail="HF boş sonuç döndü")

    except Exception as e:
        print(f"❌ HATA: {str(e)}")
        
        # Hata durumunda JSON dön (Android'in anlaması için)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Backend hatası",
                "message": str(e),
                "android_note": "Uygulama bu mesajı görebilir"
            }
        )
    
    finally:
        # Geçici dosyaları temizle
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                os.remove(path)
                print(f"🧹 Temizlendi: {path}")

# ✅ Render'da çalışması için
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
