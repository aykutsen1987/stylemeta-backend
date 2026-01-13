import base64
import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SPACE_URL = "https://yisol-idm-vton.hf.space/run/predict"

@app.post("/tryon")
async def tryon(person: UploadFile = File(...), cloth: UploadFile = File(...)):

    person_bytes = await person.read()
    cloth_bytes = await cloth.read()

    payload = {
        "data": [
            base64.b64encode(person_bytes).decode(),
            base64.b64encode(cloth_bytes).decode()
        ]
    }

    r = requests.post(SPACE_URL, json=payload, timeout=180)

    if r.status_code != 200:
        return {"error": "HF Space failed", "detail": r.text}

    result_base64 = r.json()["data"][0]
    image_bytes = base64.b64decode(result_base64)

    return Response(content=image_bytes, media_type="image/jpeg")
