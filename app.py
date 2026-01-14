from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import uuid
import shutil
import base64
import json

app = FastAPI(title="StyleMeta Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
RESULT_DIR = "results"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# ✅ Çevre değişkeninden token al
HF_TOKEN = os.getenv("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}

# ✅ İKİ ALTERNATİF MODEL (istediğinizi seçin veya geçiş yapın)
MODELS = {
    "idm": "https://jjlealse-idm-vton.hf.space/run/predict",  # IDM-VTON
    "kolors": "https://kwai-kolors-kolors-virtual-try-on.hf.space/run/predict"  # Kolors
}

# ✅ Varsayılan model (değiştirebilirsiniz)
CURRENT_MODEL = "idm"

def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

@app.get("/")
def health():
    return {"status": "StyleMeta backend running"}

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...),
    model: str = CURRENT_MODEL  # ?model=idm veya ?model=kolors
):
    uid = str(uuid.uuid4())
    person_path = f"{UPLOAD_DIR}/{uid}_person.jpg"
    cloth_path = f"{UPLOAD_DIR}/{uid}_cloth.jpg"
    result_path = f"{RESULT_DIR}/{uid}_result.jpg"

    # Seçilen modeli kontrol et
    if model not in MODELS:
        model = CURRENT_MODEL
    
    hf_url = MODELS[model]
    
    try:
        # Dosyaları kaydet
        with open(person_path, "wb") as f:
            shutil.copyfileobj(person.file, f)
        with open(cloth_path, "wb") as f:
            shutil.copyfileobj(cloth.file, f)

        # ✅ MODEL'e GÖRE FARKLI PAYLOAD YAPILARI
        if model == "idm":
            # IDM-VTON payload (eski sürüm)
            payload = {
                "data": [
                    f"data:image/jpeg;base64,{image_to_base64(person_path)}",
                    f"data:image/jpeg;base64,{image_to_base64(cloth_path)}"
                ]
            }
        else:  # kolors modeli
            # Kolors-Virtual-Try-On payload
            payload = {
                "data": [
                    {
                        "data": f"data:image/jpeg;base64,{image_to_base64(person_path)}",
                        "name": "person.jpg"
                    },
                    {
                        "data": f"data:image/jpeg;base64,{image_to_base64(cloth_path)}",
                        "name": "cloth.jpg"
                    }
                ]
            }

        # HF Space'e istek gönder
        response = requests.post(
            hf_url,
            json=payload,
            headers=HEADERS,
            timeout=300
        )

        # Hata kontrolü
        if response.status_code != 200:
            error_detail = f"Model: {model}, Status: {response.status_code}, Error: {response.text[:200]}"
            raise HTTPException(status_code=502, detail=error_detail)

        result = response.json()
        
        # ✅ MODEL'e GÖRE FARKLI RESPONSE PARSING
        if model == "idm":
            # IDM-VTON response formatı
            if "data" not in result or not result["data"]:
                raise HTTPException(status_code=503, detail="Model boş sonuç döndü")
            
            img_base64 = result["data"][0]
            if isinstance(img_base64, dict) and "data" in img_base64:
                img_base64 = img_base64["data"]
        else:  # kolors modeli
            # Kolors response formatı
            if "data" not in result or not result["data"]:
                raise HTTPException(status_code=503, detail="Kolors model boş sonuç döndü")
            
            # Kolors genellikle base64 string döner
            img_base64 = result["data"][0] if isinstance(result["data"], list) else result["data"]

        # Base64'ten çıkar
        if isinstance(img_base64, str) and "," in img_base64:
            img_base64 = img_base64.split(",")[1]
        
        # Decode et
        try:
            img_bytes = base64.b64decode(img_base64)
        except:
            raise HTTPException(status_code=503, detail="Base64 decode hatası")

        # Boş/küçük resim kontrolü
        if len(img_bytes) < 1000:
            raise HTTPException(status_code=503, detail="Model geçersiz resim döndü")

        # Sonucu kaydet
        with open(result_path, "wb") as f:
            f.write(img_bytes)

        return FileResponse(
            result_path,
            media_type="image/jpeg",
            filename=f"tryon_{model}_result.jpg"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model {model} hatası: {str(e)}")
    finally:
        # Temizlik
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                os.remove(path)

# ✅ Model değiştirme endpoint'i
@app.post("/switch-model")
async def switch_model(new_model: str):
    global CURRENT_MODEL
    if new_model in MODELS:
        CURRENT_MODEL = new_model
        return {"message": f"Model {new_model} olarak değiştirildi", "current": CURRENT_MODEL}
    else:
        raise HTTPException(400, detail=f"Geçersiz model. Seçenekler: {list(MODELS.keys())}")
