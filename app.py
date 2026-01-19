from fastapi import FastAPI, UploadFile, File
from fastapi.responses import Response
from PIL import Image
import numpy as np
import cv2
import io

app = FastAPI()

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...)
):
    # Fotoğrafları oku
    person_img = Image.open(io.BytesIO(await person.read())).convert("RGB")
    cloth_img = Image.open(io.BytesIO(await cloth.read())).convert("RGBA")

    person_np = np.array(person_img)
    h, w, _ = person_np.shape

    # 🎯 Tahmini gövde alanı
    torso_top = int(h * 0.25)
    torso_bottom = int(h * 0.65)
    torso_left = int(w * 0.25)
    torso_right = int(w * 0.75)

    torso_width = torso_right - torso_left
    torso_height = torso_bottom - torso_top

    # 👕 Kıyafeti ölçekle
    cloth_resized = cloth_img.resize(
        (torso_width, torso_height),
        Image.LANCZOS
    )

    # RGBA → BGR + Alpha
    cloth_np = np.array(cloth_resized)
    alpha = cloth_np[:, :, 3] / 255.0

    for c in range(3):
        person_np[
            torso_top:torso_bottom,
            torso_left:torso_right,
            c
        ] = (
            alpha * cloth_np[:, :, c]
            + (1 - alpha) * person_np[
                torso_top:torso_bottom,
                torso_left:torso_right,
                c
            ]
        )

    # Sonuç
    result_img = Image.fromarray(person_np)
    buf = io.BytesIO()
    result_img.save(buf, format="JPEG")

    return Response(
        content=buf.getvalue(),
        media_type="image/jpeg"
    )
