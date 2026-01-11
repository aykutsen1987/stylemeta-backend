from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import uuid
import shutil

HF_API_KEY = os.environ.get("HF_API_KEY")

HF_MODEL_URL = "https://api-inference.huggingface.co/models/yisol/IDM-VTON"

HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}"
}

app = FastAPI()

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

@app.get("/")
def home():
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

    with open(person_path, "wb") as f:
        shutil.copyfileobj(person.file, f)

    with open(cloth_path, "wb") as f:
        shutil.copyfileobj(cloth.file, f)

    with open(person_path, "rb") as p, open(cloth_path, "rb") as c:
        response = requests.post(
            HF_MODEL_URL,
            headers=HEADERS,
            files={
                "person": p,
                "cloth": c
            },
            timeout=120
        )

    if response.status_code != 200:
        return {"error": "AI processing failed"}

    with open(result_path, "wb") as out:
        out.write(response.content)

    # 🔐 güvenlik: geçici dosyaları sil
    os.remove(person_path)
    os.remove(cloth_path)

    return {
        "result_url": f"/results/{uid}_result.jpg"
    }
