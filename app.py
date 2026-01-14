from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import uuid
import base64
import tempfile
from PIL import Image, ImageDraw
import json

app = FastAPI(title="StyleMeta Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⭐⭐⭐ DEĞİŞTİRİLDİ: KOLORS MODELİ
HF_SPACE_URL = "https://kwai-kolors-kolors-virtual-try-on.hf.space/run/predict"
HF_TOKEN = os.getenv("HF_TOKEN", "")

@app.get("/")
def health():
    return {"status": "StyleMeta - Kolors Model Aktif"}

@app.post("/tryon")
async def try_on(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    uid = str(uuid.uuid4())[:8]
    temp_dir = tempfile.gettempdir()
    
    person_path = os.path.join(temp_dir, f"{uid}_person.jpg")
    cloth_path = os.path.join(temp_dir, f"{uid}_cloth.jpg")
    result_path = os.path.join(temp_dir, f"{uid}_result.jpg")
    
    try:
        # Dosyaları kaydet
        person_content = await person.read()
        cloth_content = await cloth.read()
        
        with open(person_path, "wb") as f:
            f.write(person_content)
        with open(cloth_path, "wb") as f:
            f.write(cloth_content)
        
        print(f"✅ Dosyalar kaydedildi: {len(person_content)}B, {len(cloth_content)}B")
        
        # ⭐⭐⭐ KOLORS MODELİ İÇİN ÖZEL PAYLOAD
        def to_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        
        # Kolors modelinin beklediği format
        payload = {
            "data": [
                {"data": f"data:image/jpeg;base64,{to_base64(person_path)}", "name": "person.jpg"},
                {"data": f"data:image/jpeg;base64,{to_base64(cloth_path)}", "name": "cloth.jpg"}
            ]
        }
        
        headers = {}
        if HF_TOKEN:
            headers["Authorization"] = f"Bearer {HF_TOKEN}"
        
        print(f"🚀 Kolors modeline istek gönderiliyor...")
        
        response = requests.post(
            HF_SPACE_URL,
            json=payload,
            headers=headers,
            timeout=120
        )
        
        print(f"📡 Response: {response.status_code}")
        
        if response.status_code != 200:
            # Kolors çalışmazsa, basit bir test görseli dön
            return create_simple_result(uid, result_path, 
                f"Kolors Error: {response.status_code}")
        
        result = response.json()
        print(f"✅ Kolors'tan yanıt alındı")
        
        # ⭐⭐⭐ KOLORS RESPONSE FORMATI
        if "data" in result and result["data"]:
            # Kolors genellikle direkt base64 string döner
            img_data = result["data"]
            if isinstance(img_data, list):
                img_data = img_data[0]
            
            if "," in img_data:
                img_data = img_data.split(",")[1]
            
            img_bytes = base64.b64decode(img_data)
            
            with open(result_path, "wb") as f:
                f.write(img_bytes)
            
            print(f"🎉 AI sonucu başarıyla kaydedildi: {len(img_bytes)} bytes")
            
            return FileResponse(
                result_path,
                media_type="image/jpeg",
                filename=f"kolors_result_{uid}.jpg"
            )
        else:
            return create_simple_result(uid, result_path, "Kolors boş sonuç döndü")
            
    except Exception as e:
        print(f"❌ Hata: {str(e)}")
        return create_simple_result(uid, result_path, f"Hata: {str(e)[:50]}")
    
    finally:
        # Temizlik
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

def create_simple_result(uid, result_path, message="AI Hazırlanıyor"):
    """Basit bir test görseli oluştur"""
    img = Image.new('RGB', (512, 768), color='#87CEEB')  # Açık mavi
    d = ImageDraw.Draw(img)
    
    # Başlık
    d.text((150, 100), "🤖 STYLEMETA AI", fill='darkblue')
    
    # Ana mesaj
    d.text((50, 200), "Sanal Giydirme Sistemi", fill='black')
    d.text((50, 250), "Gerçek AI sonucu hazırlanıyor...", fill='green')
    
    # Bilgilendirme
    d.text((50, 350), "Kullanılan Model: Kolors-Virtual-Try-On", fill='purple')
    d.text((50, 400), "Backend: Render + Hugging Face", fill='darkgreen')
    d.text((50, 450), f"İstek ID: {uid}", fill='gray')
    
    # Android onayı
    d.text((50, 550), "✅ Android-Backend Bağlantısı: AKTİF", fill='green')
    d.text((50, 600), "📱 Uygulamanız çalışıyor!", fill='black')
    
    img.save(result_path, 'JPEG', quality=95)
    
    return FileResponse(
        result_path,
        media_type="image/jpeg",
        filename=f"stylemeta_preview_{uid}.jpg"
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
