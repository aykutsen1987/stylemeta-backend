from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os, uuid, shutil
from pose_utils import detect_pose

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/tryon")
async def tryon(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    uid = str(uuid.uuid4())
    person_path = f"{UPLOAD_DIR}/{uid}_person.jpg"

    with open(person_path, "wb") as f:
        shutil.copyfileobj(person.file, f)

    pose = detect_pose(person_path)

    if pose is None:
        raise HTTPException(status_code=400, detail="Pose tespit edilemedi")

    return {
        "status": "pose_detected",
        "pose": pose
    }
