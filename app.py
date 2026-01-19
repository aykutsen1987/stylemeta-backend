from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import mediapipe as mp
import os
import uuid

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

mp_selfie = mp.solutions.selfie_segmentation
segmenter = mp_selfie.SelfieSegmentation(model_selection=1)

@app.post("/tryon")
async def tryon(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...)
):
    uid = str(uuid.uuid4())

    person_path = f"{UPLOAD_DIR}/{uid}_person.jpg"
    cloth_path = f"{UPLOAD_DIR}/{uid}_cloth.png"
    result_path = f"{RESULT_DIR}/{uid}_result.jpg"

    with open(person_path, "wb") as f:
        f.write(await person.read())

    with open(cloth_path, "wb") as f:
        f.write(await cloth.read())

    # Görselleri oku
    person_img = cv2.imread(person_path)
    cloth_img = cv2.imread(cloth_path, cv2.IMREAD_UNCHANGED)

    person_rgb = cv2.cvtColor(person_img, cv2.COLOR_BGR2RGB)
    result = segmenter.process(person_rgb)

    mask = result.segmentation_mask > 0.6
    mask = mask.astype(np.uint8) * 255

    mask_3c = cv2.merge([mask, mask, mask])

    # Elbiseyi insan boyutuna getir
    cloth_resized = cv2.resize(
        cloth_img,
        (person_img.shape[1], person_img.shape[0])
    )

    if cloth_resized.shape[2] == 4:
        alpha = cloth_resized[:, :, 3] / 255.0
        for c in range(3):
            person_img[:, :, c] = (
                alpha * cloth_resized[:, :, c] +
                (1 - alpha) * person_img[:, :, c]
            )
    else:
        person_img = np.where(
            mask_3c == 255,
            cloth_resized[:, :, :3],
            person_img
        )

    cv2.imwrite(result_path, person_img)

    return FileResponse(result_path, media_type="image/jpeg")
