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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# MediaPipe'ı tamamen korumalı yükle
try:
    import mediapipe as mp
    mp_pose = mp.solutions.pose
    pose_tracker = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)
    MP_AVAILABLE = True
    print("✅ MediaPipe Pose Sistemi Aktif")
except Exception as e:
    MP_AVAILABLE = False
    print(f"⚠️ MediaPipe Yüklenemedi (Sadece AI Giydirme Çalışacak): {e}")

@app.get("/")
def read_root():
    return {"status": "StyleMeta API is Live", "mp_active": MP_AVAILABLE}

@app.post("/tryon")
async def try_on_proxy(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    temp_dir = tempfile.mkdtemp()
    p_path = os.path.join(temp_dir, f"p_{uuid.uuid4()}.jpg")
    c_path = os.path.join(temp_dir, f"c_{uuid.uuid4()}.jpg")
    
    try:
        # 1. Dosya Kaydetme
        with open(p_path, "wb") as f: f.write(await person.read())
        with open(c_path, "wb") as f: f.write(await cloth.read())

        # 2. MediaPipe Analizi (Adım 2)
        if MP_AVAILABLE:
            try:
                img = cv2.imread(p_path)
                results = pose_tracker.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                if results.pose_landmarks:
                    print("✅ Gövde analizi başarılı.")
            except:
                print("⚠️ Pose analizi sırasında hata.")

        # 3. AI Model İsteyi (Adım 1)
        print("🚀 AI Modeline istek gönderiliyor...")
        client = Client("yisol/IDM-VTON")
        
        # IDM-VTON parametre yapısı
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

        final_image = result[0] if isinstance(result, (list, tuple)) else result
        output_file = os.path.join(temp_dir, "result.jpg")
        shutil.copy(final_image, output_file)
        
        return FileResponse(output_file, media_type="image/jpeg")

    except Exception as e:
        print(f"❌ KRİTİK HATA: {str(e)}")
        # Hatayı Android'e gönder
        raise HTTPException(status_code=500, detail=f"Backend Hatası: {str(e)}")
    finally:
        # Temizlik işlemleri burada yapılabilir
        pass
