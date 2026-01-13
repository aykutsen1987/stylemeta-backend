import base64
import json

def image_to_base64(path):
    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode("utf-8")


@app.post("/tryon")
async def try_on(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    uid = str(uuid.uuid4())

    person_path = f"uploads/{uid}_person.jpg"
    cloth_path = f"uploads/{uid}_cloth.jpg"
    result_path = f"results/{uid}_result.jpg"

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
