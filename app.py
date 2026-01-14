from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw
import requests
import os
import uuid
import base64
import tempfile
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⭐⭐ TOKEN'SİZ PUBLIC MODELLER ⭐⭐
MODELS = {
    "viton": {
        "url": "https://viton-hd.hf.space/run/predict",
        "needs_token": False,
        "payload_type": "viton"
    },
    "oot": {
        "url": "https://ootdiffusion.hf.space/run/predict",
        "needs_token": False,
        "payload_type": "simple"
    },
    "tryongan": {
        "url": "https://tryongan.hf.space/run/predict",
        "needs_token": False,
        "payload_type": "simple"
    }
}

# Varsayılan model (değiştirebilirsiniz)
CURRENT_MODEL = "viton"

@app.get("/")
def health():
    model_info = MODELS[CURRENT_MODEL]
    return {
        "status": "StyleMeta AI - TOKEN'SİZ",
        "current_model": CURRENT_MODEL,
        "token_required": model_info["needs_token"],
        "url": model_info["url"],
        "endpoint": "/tryon"
    }

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...),
    model: str = CURRENT_MODEL  # ?model=viton, ?model=oot, ?model=tryongan
):
    uid = str(uuid.uuid4())[:8]
    temp_dir = tempfile.gettempdir()
    
    person_path = os.path.join(temp_dir, f"{uid}_person.jpg")
    cloth_path = os.path.join(temp_dir, f"{uid}_cloth.jpg")
    result_path = os.path.join(temp_dir, f"{uid}_result.jpg")
    
    try:
        # Model kontrolü
        if model not in MODELS:
            model = CURRENT_MODEL
        
        model_info = MODELS[model]
        
        # Dosyaları kaydet
        person_bytes = await person.read()
        cloth_bytes = await cloth.read()
        
        with open(person_path, "wb") as f:
            f.write(person_bytes)
        with open(cloth_path, "wb") as f:
            f.write(cloth_bytes)
        
        print(f"📱 {model} modeli için istek: {len(person_bytes)}B, {len(cloth_bytes)}B")
        
        # Base64 hazırla
        def to_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        
        person_base64 = to_base64(person_path)
        cloth_base64 = to_base64(cloth_path)
        
        # ⭐⭐ MODEL'E GÖRE PAYLOAD HAZIRLA ⭐⭐
        if model_info["payload_type"] == "viton":
            # VITON-HD için özel format
            payload = {
                "data": [
                    {"data": f"data:image/jpeg;base64,{person_base64}", "name": "person.jpg"},
                    {"data": f"data:image/jpeg;base64,{cloth_base64}", "name": "cloth.jpg"},
                    "vitonhd",  # Model tipi
                    True,       # Background removal
                    True        # Multi-pose
                ]
            }
        else:
            # Diğer modeller için basit format
            payload = {
                "data": [
                    f"data:image/jpeg;base64,{person_base64}",
                    f"data:image/jpeg;base64,{cloth_base64}"
                ]
            }
        
        print(f"🚀 {model} modeline istek gönderiliyor (TOKEN'SİZ)...")
        
        # TOKEN'SİZ istek
        response = requests.post(
            model_info["url"],
            json=payload,
            timeout=180  # 3 dakika
        )
        
        print(f"📡 Yanıt: {response.status_code}")
        
        # Başarılı ise
        if response.status_code == 200:
            result = response.json()
            
            if "data" in result and result["data"]:
                img_data = result["data"]
                
                # Farklı formatlar için
                if isinstance(img_data, list):
                    img_data = img_data[0]
                
                if isinstance(img_data, dict) and "data" in img_data:
                    img_data = img_data["data"]
                
                if isinstance(img_data, str) and "," in img_data:
                    img_data = img_data.split(",")[1]
                
                try:
                    # AI SONUCU
                    ai_bytes = base64.b64decode(img_data)
                    
                    # Boş/küçük resim kontrolü
                    if len(ai_bytes) < 5000:
                        raise ValueError("AI çok küçük resim döndü")
                    
                    with open(result_path, "wb") as f:
                        f.write(ai_bytes)
                    
                    print(f"🎉 {model} BAŞARILI! {len(ai_bytes):,} byte")
                    
                    return FileResponse(
                        result_path,
                        media_type="image/jpeg",
                        filename=f"ai_{model}_{uid}.jpg"
                    )
                    
                except Exception as decode_error:
                    print(f"❌ Decode hatası: {decode_error}")
                    # Fallback: demo görsel
                    return create_demo_image(uid, result_path, model, "AI decode hatası")
        
        # Hata durumu
        error_msg = f"HTTP {response.status_code}"
        if response.text:
            error_msg += f": {response.text[:100]}"
        
        print(f"❌ {model} hatası: {error_msg}")
        
        # Fallback görsel
        return create_demo_image(
            uid, result_path, model, 
            f"Model hatası: {error_msg}",
            person_size=len(person_bytes),
            cloth_size=len(cloth_bytes)
        )
        
    except requests.exceptions.Timeout:
        print(f"⏰ {model} timeout")
        return create_demo_image(uid, result_path, model, "Timeout (3 dakika)")
        
    except Exception as e:
        print(f"💥 Genel hata: {e}")
        return create_demo_image(uid, result_path, model, f"Hata: {str(e)[:50]}")
        
    finally:
        # Temizlik
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

def create_demo_image(uid, result_path, model_name, status, person_size=None, cloth_size=None):
    """Demo/fallback görsel"""
    img = Image.new('RGB', (600, 850), color=(255, 250, 245))
    d = ImageDraw.Draw(img)
    
    # Başlık
    d.text((180, 30), "👗 STYLEMETA AI", fill=(255, 100, 100))
    
    # Model bilgisi
    d.text((50, 100), f"🤖 MODEL: {model_name.upper()}", fill=(100, 100, 255))
    d.text((70, 140), f"Status: {status}", 
           fill=(0, 180, 0) if "BAŞARILI" in status else (255, 100, 100))
    d.text((70, 180), "Token: GEREKMEZ (Public Space)", fill=(0, 150, 0))
    
    if person_size and cloth_size:
        d.text((50, 230), "📊 ALINAN DOSYALAR:", fill=(0, 0, 0))
        d.text((70, 270), f"Kullanıcı: {person_size:,} byte", fill=(60, 60, 60))
        d.text((70, 310), f"Elbise: {cloth_size:,} byte", fill=(60, 60, 60))
    
    # Bilgilendirme
    d.text((50, 370), "✅ AVANTAJLAR:", fill=(0, 120, 0))
    d.text((70, 410), "• Token gerekmez", fill=(0, 0, 0))
    d.text((70, 450), "• Rate limit daha yüksek", fill=(0, 0, 0))
    d.text((70, 490), "• Sürekli erişim", fill=(0, 0, 0))
    
    # Model değiştirme kılavuzu
    d.text((50, 550), "🔄 MODEL DEĞİŞTİRMEK İÇİN:", fill=(150, 80, 0))
    d.text((70, 590), "Android'de istek yaparken:", fill=(0, 0, 0))
    d.text((90, 630), "URL'ye ?model=viton ekleyin", fill=(0, 100, 200))
    d.text((90, 670), "veya ?model=oot", fill=(0, 100, 200))
    
    # İstek ID
    d.text((50, 730), f"📍 İstek ID: {uid}", fill=(100, 100, 100))
    
    # Sistem durumu
    d.rectangle([40, 780, 560, 830], fill=(230, 255, 230), outline=(0, 180, 0), width=2)
    d.text((60, 800), "✨ Sistem aktif - Model test ediliyor", fill=(0, 120, 0))
    
    img.save(result_path, 'JPEG', quality=95)
    return FileResponse(result_path, media_type="image/jpeg")

# Model değiştirme endpoint'i
@app.post("/switch-model/{model_name}")
async def switch_model(model_name: str):
    global CURRENT_MODEL
    if model_name in MODELS:
        CURRENT_MODEL = model_name
        return {
            "message": f"Model {model_name} olarak değiştirildi",
            "model_info": MODELS[model_name]
        }
    return {"error": f"Geçersiz model. Seçenekler: {list(MODELS.keys())}"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    print(f"🚀 Token'siz AI başlatılıyor. Model: {CURRENT_MODEL}")
    uvicorn.run(app, host="0.0.0.0", port=port)
