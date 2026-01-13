from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests, os, uuid, shutil, base64

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

def image_to_base64(path):
    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode()

@app.post("/tryon")
async def try_on(person: UploadFile = File(...), cloth: UploadFile = File(...)):
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

    try:
        response = requests.post(
            "https://yisol-idm-vton.hf.space/run/predict",
            json=payload,
            timeout=300
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"HF error: {response.text}"
            )

        result = response.json()

        if "data" not in result:
            raise HTTPException(
                status_code=503,
                detail=f"HF response invalid: {result}"
            )

        image_base64 = result["data"][0].split(",")[1]

        with open(result_path, "wb") as f:
            f.write(base64.b64decode(image_base64))

        return FileResponse(result_path, media_type="image/jpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
