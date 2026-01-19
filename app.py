from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from gradio_client import Client, handle_file
import os
import uuid
import tempfile
import shutil
import cv2
import mediapipe as mp
import numpy as np

app = FastAPI()

# Android bağlantısı için CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MediaPipe Pose kurulumu
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)

def analyze_pose(image_path):
    """İnsan fotoğrafındaki gövde noktalarını tespit eder."""
    try:
        image = cv2.imread(image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = pose.process(image_rgb)
        
        if not results.pose_landmarks:
            return None
            
        # Omuz (11, 12) ve Kalça (23, 24) noktalarını al
        landmarks = results.pose_landmarks.landmark
        body_data = {
            "left_shoulder": [landmarks[11].x, landmarks[11].y],
            "right_shoulder": [landmarks[12].x, landmarks[12].y],
            "left_hip": [landmarks[23].x, landmarks[23].y],
            "right_hip": [landmarks[24].x, landmarks[24].y]
        }
        return body_data
    except Exception as e:
        print(f"Pose Analiz Hatası: {e}")
        return None

@app.get("/")
def read_root():
    return {"status": "StyleMeta AI is Live", "version": "1.1.0 (Pose Analysis Active)"}

@app.post("/tryon")
async def try_on_proxy(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    temp_dir = tempfile.mkdtemp()
    p_path = os.path.join(temp_dir, f"p_{uuid.uuid4()}.jpg")
    c_path = os.path.join(temp_dir, f"c_{uuid.uuid4()}.jpg")
    
    try:
        # 1. Dosyaları Kaydet
        with open(p_path, "wb") as f:
            f.write(await person.read())
        with open(c_path, "wb") as f:
            f.write(await cloth.read())

        print(f"🚀 İşlem Başladı. Pose analizi yapılıyor...")

        # 2. ADIM 2: MediaPipe Analizi (Gövde Tespiti)
        body_metrics = analyze_pose(p_path)
        if body_metrics:
            print(f"✅ Gövde Tespit Edildi: Omuz Genişliği Yaklaşık {abs(body_metrics['left_shoulder'][0] - body_metrics['right_shoulder'][0]):.2f}")
        else:
            print("⚠️ Gövde tespit edilemedi, standart işleme devam ediliyor.")

        # 3. Model Entegrasyonu (IDM-VTON)
        client = Client("yisol/IDM-VTON")
        
        # Log: Hugging Face'e istek atılıyor
        result = client.predict(
            dict={"background": handle_file(p_path), "layers": [], "composite": None},
            garm_img=handle_file(c_path),
            garment_des="garment", 
            is_checked=True,
            is_auto_mask=True,
            denoise_steps=30,
            seed=42,
            api_name="/tryon"
        )

        # 4. Sonucu Hazırla
        final_image_path = result[0] if isinstance(result, (list, tuple)) else result
        output_file = os.path.join(temp_dir, "output_result.jpg")
        shutil.copy(final_image_path, output_file)
        
        return FileResponse(output_file, media_type="image/jpeg")

    except Exception as e:
        print(f"❌ Hata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
