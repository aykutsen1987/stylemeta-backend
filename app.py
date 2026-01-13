from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import base64
import requests
import uuid
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SPACE_API_URL = "https://yisol-idm-vton.hf.space/run/predict"

RESULT_DIR = "results"
os.makedirs(RESULT_DIR, exist_ok=True)

@app.get("/")
def home():
    return {"status": "StyleMeta backend running"}

def file_to_base64(upload_file: UploadFile) -> str:
    return base64.b64encode(upload_file.file.read()).decode("utf-8")

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...)
):
    person_b64 = file_to_base64(person)
    cloth_b64 = file_to_base64(cloth)

    payload = {
        "data": [
            person_b64,
            cloth_b64
        ]
    }

    response = requests.post(
        SPACE_API_URL,
        json=payload,
        timeout=180
