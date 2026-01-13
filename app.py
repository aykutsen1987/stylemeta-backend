from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests, os, uuid, shutil, base64, traceback

app = FastAPI()

# CORS
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

# Utils
def image_to_base64(path: str) -> str:
    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode("utf-8")

# Root (Render health check için – 404 olmasın)
@app.get("/")
def root():
    return {"status": "StyleMeta backend is running"}

# TRY-ON
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
        # Save uploads
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

        print("HF STATUS:", response.status_code)
        print("HF RESPONSE:", response.text)

        if response.status_code != 200:
            return JSONResponse(
                status_code=502,
                content={
                    "status": "error",
                    "message": "HuggingFace request failed",
                    "detail": response.text
                }
            )

        result = response.json()

        # 🔴 HF boş / loading / rate-limit kontrolü
        if (
            "data" not in result
            or not result["data"]
            or result["data"][0] is None
        ):
            return JSONResponse(
                status_code=202,
                content={
                    "status": "loading",
                    "message": "Model is loading or returned empty result",
                    "hf_response": result
                }
            )

        image_data = result["data"][0]

        if "," not in image_data:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": "Invalid image format from HF",
                    "hf_response": result
                }
            )

        image_base64 = image_data.split(",")[1]

        with open(result_path, "wb") as f:
            f.write(base64.b64decode(image_base64))

        return FileResponse(
            result_path,
            media_type="image/jpeg",
            filename="result.jpg"
        )

    except Exception as e:
        print("SERVER CRASH:", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "status": "crash",
                "error": str(e)
            }
        )
