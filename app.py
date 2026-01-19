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

# DAHA GENİŞ VE GÜNCEL MODEL HAVUZU
MODEL_POOL = [
    {"name": "Kwai-Kolors", "src": "Kwai-Kolors/Kolors-Virtual-Try-On", "type": "kolors"},
    {"name": "Nymbo", "src": "Nymbo/Virtual-Try-On", "type": "vton"},
    {"name": "IDM-VTON", "src": "yisol/IDM-VTON", "type": "vton"},
    {"name": "Fals-Backup", "src": "fffiloni/IDM-VTON", "type": "vton"} # Yedek
]

@app.get("/")
def read_root():
    return {"status": "Multi-Model Engine Active", "version": "1.2.0"}

@app.post("/tryon")
async def try_on_proxy(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    temp_dir = tempfile.mkdtemp()
    p_path = os.path.join(temp_dir, f"p_{uuid.uuid4()}.jpg")
    c_path = os.path.join(temp_dir, f"c_{uuid.uuid4()}.jpg")
    
    try:
        with open(p_path, "wb") as f: f.write(await person.read())
        with open(c_path, "wb") as f: f.write(await cloth.read())

        for model in MODEL_POOL:
            try:
                print(f"📡 {model['name']} deneniyor ({model['src']})...")
                client = Client(model["src"])
                
                if model["type"] == "kolors":
                    # Kolors için isim kullanmadan tahmin (index üzerinden)
                    result = client.predict(
                        handle_file(p_path), handle_file(c_path), 
                        True, False, 30, 42
                    )
                else:
                    # VTON modelleri için standart yapı
                    result = client.predict(
                        dict={"background": handle_file(p_path), "layers": [], "composite": None},
                        garm_img=handle_file(c_path),
                        garment_des="garment", is_checked=True, is_auto_mask=True,
                        denoise_steps=30, seed=42
                    )

                final_image = result[0] if isinstance(result, (list, tuple)) else result
                output_file = os.path.join(temp_dir, "result.jpg")
                shutil.copy(final_image, output_file)
                
                print(f"✅ BAŞARILI: {model['name']}")
                return FileResponse(output_file, media_type="image/jpeg")

            except Exception as e:
                print(f"⚠️ {model['name']} başarısız oldu: {str(e)[:100]}")
                continue 

        raise Exception("Şu an tüm yapay zeka servisleri Hugging Face üzerinde bakımda. Lütfen 5-10 dakika sonra tekrar deneyin.")

    except Exception as e:
        print(f"❌ TÜM MODELLER ÇÖKTÜ: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
