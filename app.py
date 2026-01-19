from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from gradio_client import Client, handle_file
import os
import uuid
import tempfile
import shutil

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DENENECEK MODELLER (Sırasıyla)
MODEL_POOL = [
    {"name": "Nymbo", "src": "Nymbo/Virtual-Try-On", "api": "/tryon"},
    {"name": "IDM-VTON", "src": "yisol/IDM-VTON", "api": "/tryon"},
    {"name": "Kolors-Alt", "src": "Kwai-Kolors/Kolors-Virtual-Try-On", "api": "/predict"}
]

@app.get("/")
def read_root():
    return {"status": "StyleMeta API is Live", "msg": "Send POST to /tryon"}

@app.post("/tryon")
async def try_on_proxy(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    temp_dir = tempfile.mkdtemp()
    p_path = os.path.join(temp_dir, f"p_{uuid.uuid4()}.jpg")
    c_path = os.path.join(temp_dir, f"c_{uuid.uuid4()}.jpg")
    
    try:
        with open(p_path, "wb") as f: f.write(await person.read())
        with open(c_path, "wb") as f: f.write(await cloth.read())

        last_error = ""
        
        for model in MODEL_POOL:
            try:
                print(f"🚀 {model['name']} modeli deneniyor...")
                client = Client(model["src"])
                
                # Model tipine göre parametre ayarı
                if "Kolors" in model["name"]:
                    result = client.predict(
                        handle_file(p_path), handle_file(c_path), 
                        True, False, 30, 42, api_name=model["api"]
                    )
                else:
                    result = client.predict(
                        dict={"background": handle_file(p_path), "layers": [], "composite": None},
                        garm_img=handle_file(c_path),
                        garment_des="garment", is_checked=True, is_auto_mask=True,
                        denoise_steps=30, seed=42, api_name=model["api"]
                    )

                final_image = result[0] if isinstance(result, (list, tuple)) else result
                output_file = os.path.join(temp_dir, "result.jpg")
                shutil.copy(final_image, output_file)
                
                print(f"✅ {model['name']} ile başarıyla sonuç üretildi.")
                return FileResponse(output_file, media_type="image/jpeg")

            except Exception as e:
                last_error = str(e)
                print(f"⚠️ {model['name']} başarısız: {last_error}")
                continue # Bir sonraki modele geç

        # Eğer hiçbir model çalışmadıysa
        raise Exception(f"Tüm modeller şu an meşgul veya hatalı. Son hata: {last_error}")

    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
