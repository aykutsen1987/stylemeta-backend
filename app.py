from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from gradio_client import Client, handle_file
import os
import uuid
import tempfile
import shutil
import cv2
import numpy as np

# MediaPipe'ı hata almadan yüklemek için bu yöntemi deneyelim
try:
    import mediapipe as mp
    from mediapipe.python.solutions import pose as mp_pose
    pose_tracker = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)
    MP_AVAILABLE = True
    print("✅ MediaPipe Pose başarıyla yüklendi.")
except Exception as e:
    MP_AVAILABLE = False
    print(f"⚠️ MediaPipe yüklenemedi, analiz devre dışı: {e}")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def analyze_pose(image_path):
    if not MP_AVAILABLE:
        return None
    try:
        image = cv2.imread(image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = pose_tracker.process(image_rgb)
        
        if not results.pose_landmarks:
            return None
            
        lm = results.pose_landmarks.landmark
        return {
            "shoulder_width": abs(lm[11].x - lm[12].x),
            "hip_width": abs(lm[23].x - lm[24].x)
        }
    except:
        return None

@app.post("/tryon")
async def try_on_proxy(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    temp_dir = tempfile.mkdtemp()
    p_path = os.path.join(temp_dir, f"p_{uuid.uuid4()}.jpg")
    c_path = os.path.join(temp_dir, f"c_{uuid.uuid4()}.jpg")
    
    try:
        with open(p_path, "wb") as f: f.write(await person.read())
        with open(c_path, "wb") as f: f.write(await cloth.read())

        # Adım 2: Analiz (Hata olsa bile devam etmesi için try-except içinde)
        metrics = analyze_pose(p_path)
        if metrics:
            print(f"📊 Analiz: Omuz={metrics['shoulder_width']:.2f}")

        # Adım 1 & 5: AI Giydirme
        client = Client("yisol/IDM-VTON")
        result = client.predict(
            dict={"background": handle_file(p_path), "layers": [], "composite": None},
            garm_img=handle_file(c_path),
            garment_des="garment", is_checked=True, is_auto_mask=True,
            denoise_steps=30, seed=42, api_name="/tryon"
        )

        final_image = result[0] if isinstance(result, (list, tuple)) else result
        output_file = os.path.join(temp_dir, "output.jpg")
        shutil.copy(final_image, output_file)
        
        return FileResponse(output_file, media_type="image/jpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
