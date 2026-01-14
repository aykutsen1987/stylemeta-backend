from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from gradio_client import Client, handle_file
import os
import uuid
import shutil
import time
from pathlib import Path

app = FastAPI(title="StyleMeta AI - Stable VTON")

# Klasör Yapılandırması
UPLOAD_DIR = Path("uploads")
RESULT_DIR = Path("results")
UPLOAD_DIR.mkdir(exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Görev Takip Sözlüğü (Basit bellek içi saklama)
# Gerçek projede Redis veya Veritabanı önerilir
tasks = {}

# Modellerin Gradio Adresleri
MODEL_SOURCES = {
    "kolors": "Kwai-Kolors/Kolors-Virtual-Try-On",
    "idm": "jjlealse/IDM-VTON",
    "bridal": "Mariya789/IDM-VTON-AI2BRIDAL"
}

@app.get("/")
def health():
    return {"status": "online", "active_tasks": len(tasks), "models": list(MODEL_SOURCES.keys())}

@app.post("/tryon")
async def start_tryon(
    background_tasks: BackgroundTasks,
    person: UploadFile = File(...),
    cloth: UploadFile = File(...),
    model_type: str = "kolors"
):
    task_id = str(uuid.uuid4())[:8]
    
    # Dosyaları yerel diske kaydet
    person_path = UPLOAD_DIR / f"{task_id}_person.jpg"
    cloth_path = UPLOAD_DIR / f"{task_id}_cloth.jpg"
    
    with person_path.open("wb") as buffer:
        shutil.copyfileobj(person.file, buffer)
    with cloth_path.open("wb") as buffer:
        shutil.copyfileobj(cloth.file, buffer)

    tasks[task_id] = {"status": "processing", "progress": 10}
    
    # Arka planda AI işlemini başlat
    background_tasks.add_task(process_vton, task_id, str(person_path), str(cloth_path), model_type)
    
    return {
        "task_id": task_id,
        "status": "started",
        "message": "İşlem arka planda devam ediyor. Lütfen task_id ile sorgulayın."
    }

def process_vton(task_id: str, person_path: str, cloth_path: str, model_type: str):
    try:
        model_name = MODEL_SOURCES.get(model_type, MODEL_SOURCES["kolors"])
        client = Client(model_name)
        
        tasks[task_id]["progress"] = 30
        
        # Modele göre API çağrısı (Gradio Client Yapısı)
        if model_type == "kolors":
            result = client.predict(
                person_img=handle_file(person_path),
                cloth_img=handle_file(cloth_path),
                is_checked=True,
                api_name="/predict"
            )
        else: # IDM veya Bridal
            result = client.predict(
                dict={"background": handle_file(person_path), "layers": [], "composite": None},
                garm_img=handle_file(cloth_path),
                garment_des="A beautiful garment",
                is_checked=True,
                is_auto_mask=True,
                denoise_steps=30,
                seed=42,
                api_name="/tryon"
            )

        # Gradio genellikle sonucun geçici dosya yolunu döner
        final_image_path = result[0] if isinstance(result, (list, tuple)) else result
        
        # Sonucu kalıcı klasöre taşı
        output_filename = f"result_{task_id}.jpg"
        final_dest = RESULT_DIR / output_filename
        shutil.move(final_image_path, final_dest)
        
        tasks[task_id].update({
            "status": "completed",
            "progress": 100,
            "result_url": f"/result/{task_id}"
        })

    except Exception as e:
        print(f"Hata Task {task_id}: {str(e)}")
        tasks[task_id] = {"status": "failed", "error": str(e)}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task bulunamadı")
    return tasks[task_id]

@app.get("/result/{task_id}")
async def get_result(task_id: str):
    result_path = RESULT_DIR / f"result_{task_id}.jpg"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Sonuç henüz hazır değil")
    
    return FileResponse(result_path, media_type="image/jpeg")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
