from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import uuid
import shutil
import base64

# =========================
# FASTAPI APP
# =========================
app = FastAPI(title="StyleMeta Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# FOLDERS
# =========================
UPLOAD_DIR = "uploads"
RESULT_DIR = "results"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# =========================
# HF SPACE (GRADIO)
# =========================
HF_SPACE_URL = "https://cuuupid-idm-vton-lite.hf.space/run/predict"

# =========================
# HELPERS
# =========================
def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# =========================
# ROUTES
# =========================
@app.get("/")
def root():
    return {"status": "StyleMeta backend running"}

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...)
):
    uid = str(uuid.uuid4())

    person_path = f"{UPLOAD_DIR}/{uid}_person.jpg"
    cloth_path = f"{UPLOAD_DIR}/{uid}_cloth.jpg"
    result_path = f"{RESULT_DIR}/{uid}_result.jpg"

    try:
        # 1️⃣ Dosyaları kaydet
        with open(person_path, "wb") as f:
            shutil.copyfileobj(person.file, f)

        with open(cloth_path, "wb") as f:
            shutil.copyfileobj(cloth.file, f)

        # 2️⃣ HF payload (BASE64)
        payload = {
            "data": [
                f"data:image/jpeg;base64,{image_to_base64(person_path)}",
                f"data:image/jpeg;base64,{image_to_base64(cloth_path)}"
            ]
        }

        # 3️⃣ HF çağrısı
        response = requests.post(
            HF_SPACE_URL,
            json=payload,
            timeout=300
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"HuggingFace error: {response.text}"
            )

        result_json = response.json()

        if "data" not in result_json or not result_json["data"]:
            raise HTTPException(
                status_code=503,
                detail="HF returned empty result (space sleeping or crashed)"
            )

        # 4️⃣ BASE64 → IMAGE
        base64_image = result_json["data"][0]

        # bazen direkt base64 gelir
        if "," in base64_image:
            base64_image = base64_image.split(",")[1]

        image_bytes = base64.b64decode(base64_image)

        if len(image_bytes) < 1000:
            raise HTTPException(
                status_code=503,
                detail="HF returned invalid image (too small / black)"
            )

        with open(result_path, "wb") as f:
            f.write(image_bytes)

        # 5️⃣ Sonucu döndür
        return FileResponse(
            result_path,
            media_type="image/jpeg",
            filename="stylemeta_result.jpg"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 🔐 geçici dosyaları temizle
        if os.path.exists(person_path):
            os.remove(person_path)
        if os.path.exists(cloth_path):
            os.remove(cloth_path)
