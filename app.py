from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from gradio_client import Client
import uuid, os, shutil

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

# 🔥 GRADIO CLIENT
client = Client("akhaliq/IDM-VTON")

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

    try:
        # 🔥 DOĞRU IDM-VTON ÇAĞRISI
        result = client.predict(
            person_path,
            cloth_path,
            "upper",        # upper / lower / dress
            api_name="/tryon"
        )

        shutil.copy(result, result_path)

        return FileResponse(result_path, media_type="image/jpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
