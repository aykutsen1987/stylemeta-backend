from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import uuid
import shutil
import cv2

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

    # Dosyaları kaydet
    with open(person_path, "wb") as f:
        shutil.copyfileobj(person.file, f)

    with open(cloth_path, "wb") as f:
        shutil.copyfileobj(cloth.file, f)

    # OpenCV ile oku
    person_img = cv2.imread(person_path)
    cloth_img = cv2.imread(cloth_path)

    if person_img is None or cloth_img is None:
        return {"error": "Görüntü okunamadı"}

    # Elbiseyi kişinin üstüne basitçe yerleştir
    h, w, _ = person_img.shape
    cloth_resized = cv2.resize(cloth_img, (int(w * 0.6), int(h * 0.4)))

    x_offset = int(w * 0.2)
    y_offset = int(h * 0.25)

    person_img[
        y_offset:y_offset + cloth_resized.shape[0],
        x_offset:x_offset + cloth_resized.shape[1]
    ] = cloth_resized

    cv2.imwrite(result_path, person_img)

    return FileResponse(
        result_path,
        media_type="image/jpeg"
    )
