from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import uuid
import shutil
import base64

app = FastAPI()   # 🔥 BU SATIR OLMAZSA BU HATA OLUR

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

def image_to_base64(path):
    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode("utf-8")

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

    payload = {
        "data": [
            f"data:image/jpeg;base64,{image_to_base64(person_path)}",
            f"data:image/jpeg;base64,{image_to_base64(cloth_path)}"
        ]
    }

    response = requests.post(
        "https://yisol-idm-vton.hf.space/run/predict",
        json=payload,
        timeout=300
    )

    result_base64 = response.json()["data"][0].split(",")[1]

    with open(result_path, "wb") as f:
        f.write(base64.b64decode(result_base64))

    return FileResponse(result_path, media_type="image/jpeg")
