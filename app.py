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

# MediaPipe hatasını tamamen bypass etmek için Adım 2'yi 
# şimdilik sadece fonksiyon olarak tanımlıyoruz, içeriği boş bırakıyoruz
def analyze_pose_v2(image_path):
    print("📊 Pose analizi şu an bypass edildi, AI modeline geçiliyor.")
    return None

@app.get("/")
def read_root():
    return {"status": "StyleMeta API is Live", "model": "Nymbo-VTON"}

@app.post("/tryon")
async def try_on_proxy(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    temp_dir = tempfile.mkdtemp()
    p_path = os.path.join(temp_dir, f"p_{uuid.uuid4()}.jpg")
    c_path = os.path.join(temp_dir, f"c_{uuid.uuid4()}.jpg")
    
    try:
        with open(p_path, "wb") as f: f.write(await person.read())
        with open(c_path, "wb") as f: f.write(await cloth.read())

        # ADIM 1: ÇALIŞAN MODEL (Şu an aktif olan bir başkasını deniyoruz)
        # IDM-VTON çöktüğü için alternatif:
        print("🚀 Alternatif AI Modeline (Nymbo) bağlanılıyor...")
        client = Client("Nymbo/Virtual-Try-On") # Bu model genelde daha stabildir
        
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
        print(f"❌ HATA: {str(e)}")
        # Eğer bu model de hata verirse Android'e bilgi gönder
        raise HTTPException(status_code=500, detail=f"Model hatası veya meşgul: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
