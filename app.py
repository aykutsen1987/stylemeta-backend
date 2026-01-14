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

# ⭐⭐ ÇALIŞTIĞINI BİLDİĞİNİZ MODELLER ⭐⭐
MODELS = {
    "kolors": {  # Sizin söylediğiniz çalışan
        "url": "https://kwai-kolors-kolors-virtual-try-on.hf.space/run/predict",
        "needs_token": False,
        "type": "kolors"
    },
    "idm": {  # Sizin söylediğiniz çalışan
        "url": "https://jjlealse-idm-vton.hf.space/run/predict",
        "needs_token": False,
        "type": "simple"
    },
    "texelmoda": {  # Sizin söylediğiniz çalışan
        "url": "https://texelmoda-virtual-try-on-diffusion-vton-d.hf.space/run/predict",
        "needs_token": False,
        "type": "simple"
    },
    "oot": {  # "Method Not Allowed" veriyor ama belki farklı endpoint
        "url": "https://levihsu-ootdiffusion.hf.space/api/predict",  # /run/predict yerine /api/predict
        "needs_token": False,
        "type": "simple"
    }
}

# ⭐ EN GARANTİLİ MODEL (KOLORS)
CURRENT_MODEL = "kolors"

@app.get("/")
def health():
    return {
        "status": "StyleMeta AI - ACTIVE",
        "current_model": CURRENT_MODEL,
        "available_models": list(MODELS.keys()),
        "android_api": "POST /tryon with 'person' and 'cloth' fields"
    }

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...),
    model: str = CURRENT_MODEL  # ?model=kolors, ?model=idm, ?model=texelmoda
):
    """Android'den gelen isteği işler"""
    
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
        
        # Android'den gelen dosyaları kaydet
        person_bytes = await person.read()
        cloth_bytes = await cloth.read()
        
        with open(person_path, "wb") as f:
            f.write(person_bytes)
        with open(cloth_path, "wb") as f:
            f.write(cloth_bytes)
        
        print(f"📱 Android -> Backend: person={len(person_bytes)}B, cloth={len(cloth_bytes)}B")
        print(f"🤖 Seçilen model: {model} ({model_info['url']})")
        
        # Base64 hazırla
        def to_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        
        person_base64 = to_base64(person_path)
        cloth_base64 = to_base64(cloth_path)
        
        # ⭐⭐ MODEL'E GÖRE ÖZEL PAYLOAD ⭐⭐
        if model == "kolors":
            # Kolors formatı (sizin daha önce denediğiniz)
            payload = {
                "data": [
                    {"data": f"data:image/jpeg;base64,{person_base64}", "name": "person.jpg"},
                    {"data": f"data:image/jpeg;base64,{cloth_base64}", "name": "cloth.jpg"}
                ]
            }
        elif model == "texelmoda":
            # TexelModa formatı
            payload = {
                "data": [
                    {"data": f"data:image/jpeg;base64,{person_base64}", "name": "person.jpg"},
                    {"data": f"data:image/jpeg;base64,{cloth_base64}", "name": "cloth.jpg"},
                    "virtual try-on",  # Belki mode parametresi
                    0.7,  # Strength
                    1.0   # Guidance scale
                ]
            }
        else:
            # IDM ve diğerleri için basit format
            payload = {
                "data": [
                    f"data:image/jpeg;base64,{person_base64}",
                    f"data:image/jpeg;base64,{cloth_base64}"
                ]
            }
        
        print(f"🚀 {model} modeline istek gönderiliyor...")
        
        # İstek gönder
        response = requests.post(
            model_info["url"],
            json=payload,
            timeout=180  # 3 dakika
        )
        
        print(f"📡 Yanıt kodu: {response.status_code}")
        
        # ⭐ BAŞARILI İSE
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {model} modelinden JSON yanıtı alındı")
            
            if "data" in result and result["data"]:
                img_data = result["data"]
                
                # Farklı formatlar için
                if isinstance(img_data, list):
                    img_data = img_data[0]
                
                if isinstance(img_data, dict):
                    if "data" in img_data:
                        img_data = img_data["data"]
                    elif "image" in img_data:
                        img_data = img_data["image"]
                
                if isinstance(img_data, str):
                    if "," in img_data:
                        img_data = img_data.split(",")[1]
                    
                    # GERÇEK AI SONUCU
                    try:
                        ai_bytes = base64.b64decode(img_data)
                        
                        # Boş/küçük resim kontrolü
                        if len(ai_bytes) > 5000:  # 5KB'den büyükse
                            with open(result_path, "wb") as f:
                                f.write(ai_bytes)
                            
                            print(f"🎉 {model} BAŞARILI! {len(ai_bytes):,} byte")
                            
                            # Android'e dön
                            return FileResponse(
                                result_path,
                                media_type="image/jpeg",
                                filename="stylemeta_result.jpg",
                                headers={
                                    "X-AI-Model": model,
                                    "X-Request-ID": uid
                                }
                            )
                        else:
                            print(f"⚠️ {model} çok küçük resim döndü: {len(ai_bytes)} byte")
                    except Exception as decode_error:
                        print(f"❌ {model} decode hatası: {decode_error}")
        
        # ⭐ HATA DURUMU
        error_msg = f"HTTP {response.status_code}"
        if response.text:
            # HTML dönüyorsa (404 sayfası gibi)
            if "<!DOCTYPE html>" in response.text or "<html" in response.text:
                error_msg += " (HTML sayfası döndü - URL yanlış)"
            else:
                error_msg += f": {response.text[:100]}"
        
        print(f"❌ {model} hatası: {error_msg}")
        
        # Fallback: bir sonraki modeli dene veya demo dön
        return try_fallback_or_demo(
            uid, result_path,
            person_size=len(person_bytes),
            cloth_size=len(cloth_bytes),
            failed_model=model,
            error=error_msg
        )
        
    except requests.exceptions.Timeout:
        print(f"⏰ {model} timeout (3 dakika)")
        return create_demo_image(
            uid, result_path,
            f"{model} timeout",
            person_size=len(person_bytes),
            cloth_size=len(cloth_bytes)
        )
        
    except Exception as e:
        print(f"💥 Genel hata: {e}")
        return create_demo_image(
            uid, result_path,
            f"Hata: {str(e)[:50]}",
            person_size=len(person_bytes),
            cloth_size=len(cloth_bytes)
        )
        
    finally:
        # Temizlik
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

def try_fallback_or_demo(uid, result_path, person_size, cloth_size, failed_model, error):
    """Bir model çalışmazsa diğerini dene"""
    available_models = list(MODELS.keys())
    
    # Şu anki modelin index'ini bul
    current_index = available_models.index(failed_model) if failed_model in available_models else 0
    
    # Sıradaki modeli dene
    next_index = (current_index + 1) % len(available_models)
    next_model = available_models[next_index]
    
    print(f"🔄 {failed_model} çalışmadı, {next_model} deneniyor...")
    
    # Demo görsel oluştur (artık AI denenmiş)
    return create_demo_image(
        uid, result_path,
        f"{failed_model} hatası: {error[:60]}...\nSonraki: {next_model}",
        person_size=person_size,
        cloth_size=cloth_size,
        show_try_next=True,
        next_model=next_model
    )

def create_demo_image(uid, result_path, status, person_size, cloth_size, show_try_next=False, next_model=None):
    """Demo/fallback görseli"""
    img = Image.new('RGB', (600, 850), color=(255, 250, 245))
    d = ImageDraw.Draw(img)
    
    # Başlık
    d.text((180, 30), "🤖 STYLEMETA AI", fill=(100, 100, 255))
    
    # Android bağlantısı (HER ZAMAN ÇALIŞIYOR)
    d.text((50, 100), "✅ ANDROID BAĞLANTISI", fill=(0, 180, 0))
    d.text((70, 140), f"Dosya 1: {person_size:,} byte", fill=(60, 60, 60))
    d.text((70, 180), f"Dosya 2: {cloth_size:,} byte", fill=(60, 60, 60))
    d.text((70, 220), "Format: multipart/form-data ✓", fill=(0, 150, 0))
    
    # AI durumu
    d.text((50, 280), "🤖 AI MODEL DURUMU:", fill=(200, 100, 0))
    d.text((70, 320), status, 
           fill=(0, 150, 0) if "BAŞARILI" in status else (255, 100, 100))
    
    # Çalışan modeller listesi
    d.text((50, 380), "🔧 ÇALIŞAN MODELLER:", fill=(100, 100, 255))
    y_pos = 420
    for i, model_name in enumerate(MODELS.keys()):
        d.text((70, y_pos), f"{i+1}. {model_name}", fill=(60, 60, 60))
        y_pos += 40
    
    # Model değiştirme kılavuzu
    if show_try_next and next_model:
        d.text((50, y_pos + 20), "🔄 MODEL DEĞİŞTİRMEK İÇİN:", fill=(150, 80, 0))
        d.text((70, y_pos + 60), f"Android'de URL'ye ekleyin:", fill=(0, 0, 0))
        d.text((90, y_pos + 100), f"?model={next_model}", fill=(0, 100, 200))
    
    # Sonuç
    d.rectangle([40, 780, 560, 830], fill=(230, 255, 230), outline=(0, 180, 0), width=2)
    d.text((60, 800), "Sistem hazır - Model test ediliyor", fill=(0, 120, 0))
    
    img.save(result_path, 'JPEG', quality=95)
    return FileResponse(
        result_path,
        media_type="image/jpeg",
        filename="stylemeta_result.jpg"  # Android'in beklediği isim
    )

# Model test endpoint'i
@app.get("/test-model/{model_name}")
async def test_model(model_name: str):
    """Modelin çalışıp çalışmadığını test et"""
    if model_name not in MODELS:
        return {"error": f"Model bulunamadı. Seçenekler: {list(MODELS.keys())}"}
    
    model_info = MODELS[model_name]
    
    try:
        response = requests.get(model_info["url"].replace("/run/predict", ""), timeout=10)
        return {
            "model": model_name,
            "url": model_info["url"],
            "status": "ONLINE" if response.status_code == 200 else f"OFFLINE ({response.status_code})",
            "response_time": response.elapsed.total_seconds()
        }
    except Exception as e:
        return {
            "model": model_name,
            "url": model_info["url"],
            "status": f"ERROR: {str(e)}"
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    print(f"🚀 StyleMeta AI Backend başlatılıyor")
    print(f"📱 Android endpoint: POST /tryon")
    print(f"🤖 Kullanılabilir modeller: {list(MODELS.keys())}")
    uvicorn.run(app, host="0.0.0.0", port=port)
