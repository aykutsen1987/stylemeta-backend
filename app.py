from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import uuid
import shutil
import base64

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

# ✅ PUBLIC HF SPACE (NO TOKEN)
HF_SPACE_URL = "https://cuuupid-idm-vton-lite.hf.space/run/predict"


def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@app.get("/")
def health():
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
            HF_SPACE_URL,
            json=payload,
            timeout=300
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"HF error: {response.text}"
            )

        result = response.json()

        if "data" not in result or not result["data"]:
            raise HTTPException(
                status_code=503,
                detail="HF returned empty result"
            )

        img_base64 = result["data"][0]
        if "," in img_base64:
            img_base64 = img_base64.split(",")[1]

        img_bytes = base64.b64decode(img_base64)

        if len(img_bytes) < 1000:
            raise HTTPException(
                status_code=503,
                detail="HF returned invalid image (black or empty)"
            )

        with open(result_path, "wb") as f:
            f.write(img_bytes)

        return FileResponse(
            result_path,
            media_type="image/jpeg",
            filename="stylemeta_result.jpg"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(person_path):
            os.remove(person_path)
        if os.path.exists(cloth_path):
            os.remove(cloth_path)
