from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from gradio_client import Client, handle_file
import os
import uuid
import tempfile
import shutil

app = FastAPI()

# Android ve dış erişim için tam yetki
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "StyleMeta API is Live", "version": "1.0.0"}

@app.post("/tryon")
async def try_on_proxy(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    # Geçici çalışma dizini oluştur
    temp_dir = tempfile.mkdtemp()
    p_path = os.path.join(temp_dir, f"p_{uuid.uuid4()}.jpg")
    c_path = os.path.join(temp_dir, f"c_{uuid.uuid4()}.jpg")
    
    try:
        # 1. Android'den gelen dosyaları oku ve kaydet
        with open(p_path, "wb") as f:
            content = await person.read()
            f.write(content)
            
        with open(c_path, "wb") as f:
            content = await cloth.read()
            f.write(content)

        print(f"🚀 İşlem Başladı: {person.filename} + {cloth.filename}")

        # 2. Kararlı Model (IDM-VTON) bağlantısı
        # Not: Kolors API kapalı olduğu için şu an en iyi alternatif budur.
        client = Client("yisol/IDM-VTON")
        
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

        # 3. Sonucu temizle ve gönder
        final_image_path = result[0] if isinstance(result, (list, tuple)) else result
        
        # Dosyayı güvenli bir yere kopyalayıp gönderelim
        output_file = os.path.join(temp_dir, "output.jpg")
        shutil.copy(final_image_path, output_file)
        
        return FileResponse(output_file, media_type="image/jpeg")

    except Exception as e:
        print(f"❌ Hata oluştu: {str(e)}")
        # Hata durumunda Android tarafına detay gönder
        raise HTTPException(status_code=500, detail=f"Backend Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Render portu 10000 kullanır
    uvicorn.run(app, host="0.0.0.0", port=10000)
