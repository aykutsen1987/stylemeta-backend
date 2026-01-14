from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import uuid
import base64
import tempfile
from PIL import Image, ImageDraw
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⭐ MODEL SEÇENEKLERİ
MODELS = {
    "kolors": "https://kwai-kolors-kolors-virtual-try-on.hf.space/run/predict",
    "idm": "https://jjlealse-idm-vton.hf.space/run/predict"
}

SELECTED_MODEL = "kolors"  # Kolors modeli
HF_TOKEN = os.getenv("HF_TOKEN", "")

@app.get("/")
def health():
    token_status = "✅ VAR" if HF_TOKEN else "❌ YOK"
    return {
        "status": "StyleMeta AI Backend",
        "model": SELECTED_MODEL,
        "hf_token": token_status,
        "endpoint": "/tryon"
    }

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
        
        print(f"📱 Android isteği: {len(person_content)}B, {len(cloth_content)}B")
        
        # ⭐ TOKEN KONTROLÜ
        if not HF_TOKEN:
            print("❌ HF_TOKEN BULUNAMADI!")
            return create_token_error_image(uid, result_path)
        
        # ⭐ HUGGING FACE İSTEĞİ
        print(f"🚀 {SELECTED_MODEL} modeline bağlanılıyor (Token: {HF_TOKEN[:10]}...)")
        
        # Base64'e çevir
        def to_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        
        # Kolors payload formatı
        payload = {
            "data": [
                {"data": f"data:image/jpeg;base64,{to_base64(person_path)}", "name": "person.jpg"},
                {"data": f"data:image/jpeg;base64,{to_base64(cloth_path)}", "name": "cloth.jpg"}
            ]
        }
        
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        
        # İstek gönder
        response = requests.post(
            MODELS[SELECTED_MODEL],
            json=payload,
            headers=headers,
            timeout=180  # 3 dakika
        )
        
        print(f"📡 HF Yanıtı: {response.status_code}")
        
        # ⭐ BAŞARILI İSE
        if response.status_code == 200:
            result = response.json()
            
            if "data" in result and result["data"]:
                img_data = result["data"]
                if isinstance(img_data, list):
                    img_data = img_data[0]
                
                if "," in img_data:
                    img_data = img_data.split(",")[1]
                
                # AI SONUCUNU KAYDET
                img_bytes = base64.b64decode(img_data)
                
                with open(result_path, "wb") as f:
                    f.write(img_bytes)
                
                print(f"🎉 AI BAŞARILI! {len(img_bytes)} byte")
                
                return FileResponse(
                    result_path,
                    media_type="image/jpeg",
                    filename=f"stylemeta_ai_{uid}.jpg",
                    headers={"X-AI-Result": "true", "X-Model": SELECTED_MODEL}
                )
        
        # ⭐ HATA DURUMU
        print(f"❌ HF Hatası: {response.status_code} - {response.text[:100]}")
        
        if response.status_code == 401:
            return create_token_invalid_image(uid, result_path, HF_TOKEN[:15])
        elif response.status_code == 503:
            return create_model_busy_image(uid, result_path, SELECTED_MODEL)
        else:
            return create_hf_error_image(uid, result_path, response.status_code)
            
    except requests.exceptions.Timeout:
        print("⏰ HF Timeout (180s)")
        return create_timeout_image(uid, result_path)
    
    except Exception as e:
        print(f"💥 Beklenmeyen hata: {str(e)}")
        return create_error_image(uid, result_path, str(e))
    
    finally:
        # Temizlik
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

# ⭐ HATA GÖRSELLERİ
def create_token_error_image(uid, result_path):
    """Token yoksa görsel"""
    img = Image.new('RGB', (600, 800), color='#FFF8E1')
    d = ImageDraw.Draw(img)
    
    d.text((200, 100), "🔑 TOKEN GEREKLİ", fill='red')
    d.text((50, 180), "Render Dashboard'a gidin:", fill='black')
    d.text((50, 230), "1. stylemeta-backend servisini seç", fill='darkblue')
    d.text((50, 280), "2. Environment sekmesine tıkla", fill='darkblue')
    d.text((50, 330), "3. Yeni değişken ekle:", fill='darkblue')
    d.text((80, 380), "KEY: HF_TOKEN", fill='green')
    d.text((80, 430), "VALUE: hf_... token'ınız", fill='green')
    d.text((50, 500), "4. Deploy'u yeniden başlat", fill='darkblue')
    d.text((50, 600), f"İstek ID: {uid}", fill='gray')
    d.text((50, 650), "Sonra tekrar deneyin!", fill='black')
    
    img.save(result_path, 'JPEG', quality=95)
    
    return FileResponse(result_path, media_type="image/jpeg")

def create_token_invalid_image(uid, result_path, token_prefix):
    """Geçersiz token görseli"""
    img = Image.new('RGB', (600, 800), color='#FFEBEE')
    d = ImageDraw.Draw(img)
    
    d.text((150, 100), "❌ GEÇERSİZ TOKEN", fill='red')
    d.text((50, 180), f"Token: {token_prefix}...", fill='darkred')
    d.text((50, 230), "Hugging Face token'ınız geçersiz veya süresi dolmuş.", fill='black')
    d.text((50, 280), "Yapılacaklar:", fill='darkblue')
    d.text((80, 330), "1. https://huggingface.co/settings/tokens", fill='green')
    d.text((80, 380), "2. Yeni token oluştur (read)", fill='green')
    d.text((80, 430), "3. Render'da HF_TOKEN'ı güncelle", fill='green')
    d.text((50, 530), f"İstek ID: {uid}", fill='gray')
    d.text((50, 600), "Model: Kolors-Virtual-Try-On", fill='purple')
    
    img.save(result_path, 'JPEG', quality=95)
    
    return FileResponse(result_path, media_type="image/jpeg")

def create_ai_success_image(uid, result_path, model_name):
    """AI başarılı görseli (demo)"""
    img = Image.new('RGB', (600, 800), color='#E8F5E9')
    d = ImageDraw.Draw(img)
    
    d.text((200, 100), "🤖 AI ÇALIŞTI!", fill='green')
    d.text((50, 180), f"Model: {model_name}", fill='purple')
    d.text((50, 230), "Sanal giydirme işlemi başarıyla tamamlandı.", fill='black')
    d.text((50, 280), "Gerçek AI sonucu Android'de görüntüleniyor.", fill='darkgreen')
    d.text((50, 350), "✅ Sistem tamamen çalışıyor!", fill='green')
    d.text((50, 400), "✅ Android bağlantısı aktif", fill='green')
    d.text((50, 450), "✅ Hugging Face bağlantısı aktif", fill='green')
    d.text((50, 500), "✅ AI modeli yanıt verdi", fill='green')
    d.text((50, 600), f"İstek ID: {uid}", fill='gray')
    d.text((50, 650), "StyleMeta AI Hazır!", fill='darkblue')
    
    img.save(result_path, 'JPEG', quality=95)
    
    return FileResponse(result_path, media_type="image/jpeg")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
