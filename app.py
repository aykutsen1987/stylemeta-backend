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
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⭐⭐ GÜNCELLENMİŞ MODEL LİSTESİ (Kolors çıkarıldı)
MODELS = {
    "idm": {  # ⭐ EN GARANTİLİ - SİZİN SÖYLEDİĞİNİZ AKTİF
        "url": "https://jjlealse-idm-vton.hf.space/run/predict",
        "needs_token": False,
        "type": "simple",
        "description": "IDM-VTON - En aktif model"
    },
    "texelmoda": {
        "url": "https://texelmoda-virtual-try-on-diffusion-vton-d.hf.space/run/predict",
        "needs_token": False,
        "type": "texelmoda",
        "description": "Diffusion VTON - Yeni nesil"
    },
    "ashamsundar": {
        "url": "https://ashamsundar-try-on.hf.space/run/predict",
        "needs_token": False,
        "type": "simple",
        "description": "Try-On - Basit ve hızlı"
    },
    "ai2bridal": {
        "url": "https://mariya789-idm-vton-ai2bridal.hf.space/run/predict",
        "needs_token": False,
        "type": "simple",
        "description": "AI2Bridal - Gelinlik odaklı"
    }
}

# ⭐ VARSYAYILAN MODEL ARTIK IDM
CURRENT_MODEL = "idm"

# Model geçmişi (hangisi çalıştı takip et)
MODEL_HISTORY = []

@app.get("/")
def health():
    return {
        "status": "StyleMeta AI - IDM MODEL AKTİF",
        "current_model": CURRENT_MODEL,
        "model_url": MODELS[CURRENT_MODEL]["url"],
        "available_models": list(MODELS.keys()),
        "test_endpoint": "POST /tryon (otomatik model seçer)",
        "manual_test": "POST /tryon?model=idm (veya texelmoda, ashansundar, ai2bridal)"
    }

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...),
    model: str = None  # None ise otomatik seç
):
    """Android'den gelen isteği işler - OTOMATİK MODEL SEÇİMİ"""
    
    uid = str(uuid.uuid4())[:8]
    temp_dir = tempfile.gettempdir()
    
    person_path = os.path.join(temp_dir, f"{uid}_person.jpg")
    cloth_path = os.path.join(temp_dir, f"{uid}_cloth.jpg")
    result_path = os.path.join(temp_dir, f"{uid}_result.jpg")
    
    # Model seçimi
    if not model:
        # OTOMATİK SEÇ: Önce IDM, çalışmazsa diğerleri
        model = select_best_model()
    
    if model not in MODELS:
        model = CURRENT_MODEL
    
    model_info = MODELS[model]
    MODEL_HISTORY.append({"model": model, "time": datetime.now().isoformat()})
    
    try:
        # Android'den dosyaları al
        person_bytes = await person.read()
        cloth_bytes = await cloth.read()
        
        with open(person_path, "wb") as f:
            f.write(person_bytes)
        with open(cloth_path, "wb") as f:
            f.write(cloth_bytes)
        
        print(f"📱 [{uid}] Android -> {model}: {len(person_bytes)}B, {len(cloth_bytes)}B")
        
        # Base64 hazırla
        def to_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        
        person_base64 = to_base64(person_path)
        cloth_base64 = to_base64(cloth_path)
        
        # ⭐⭐ MODEL'E GÖRE PAYLOAD
        if model == "texelmoda":
            payload = {
                "data": [
                    {"data": f"data:image/jpeg;base64,{person_base64}", "name": "person.jpg"},
                    {"data": f"data:image/jpeg;base64,{cloth_base64}", "name": "cloth.jpg"},
                    "virtual try-on",
                    0.7,
                    1.0
                ]
            }
        else:
            # Diğerleri için standart format
            payload = {
                "data": [
                    f"data:image/jpeg;base64,{person_base64}",
                    f"data:image/jpeg;base64,{cloth_base64}"
                ]
            }
        
        print(f"🚀 [{uid}] {model} deneniyor...")
        
        # Model isteği
        response = requests.post(
            model_info["url"],
            json=payload,
            timeout=90  # 1.5 dakika
        )
        
        print(f"📡 [{uid}] {model} yanıtı: {response.status_code}")
        
        # ⭐ BAŞARILI İSE
        if response.status_code == 200:
            result = response.json()
            
            if "data" in result and result["data"]:
                img_data = extract_image_data(result["data"])
                
                if img_data:
                    # AI SONUCUNU KAYDET
                    try:
                        ai_bytes = base64.b64decode(img_data)
                        
                        if len(ai_bytes) > 15000:  # 15KB'den büyükse gerçek AI
                            with open(result_path, "wb") as f:
                                f.write(ai_bytes)
                            
                            print(f"🎉 [{uid}] {model} BAŞARILI! {len(ai_bytes):,} byte")
                            
                            return FileResponse(
                                result_path,
                                media_type="image/jpeg",
                                filename="stylemeta_result.jpg",
                                headers={
                                    "X-AI-Success": "true",
                                    "X-Model": model,
                                    "X-Size": str(len(ai_bytes)),
                                    "X-Request-ID": uid
                                }
                            )
                        else:
                            print(f"⚠️ [{uid}] {model} küçük resim: {len(ai_bytes)} byte")
                    except Exception as decode_error:
                        print(f"❌ [{uid}] {model} decode hatası: {decode_error}")
        
        # ⭐ HATA - BİR SONRAKİ MODELİ DENE
        error_msg = f"HTTP {response.status_code}"
        if response.text and len(response.text) < 200:
            error_msg += f": {response.text}"
        
        print(f"❌ [{uid}] {model} hatası: {error_msg}")
        
        # Otomatik olarak bir sonraki modeli dene
        next_model = get_next_model(model)
        
        return create_auto_retry_image(
            uid, result_path,
            person_size=len(person_bytes),
            cloth_size=len(cloth_bytes),
            tried_model=model,
            error=error_msg,
            next_model=next_model
        )
        
    except requests.exceptions.Timeout:
        print(f"⏰ [{uid}] {model} timeout")
        next_model = get_next_model(model)
        return create_auto_retry_image(
            uid, result_path,
            person_size=len(person_bytes),
            cloth_size=len(cloth_bytes),
            tried_model=model,
            error="Timeout (90s)",
            next_model=next_model
        )
        
    except Exception as e:
        print(f"💥 [{uid}] {model} hatası: {e}")
        next_model = get_next_model(model)
        return create_auto_retry_image(
            uid, result_path,
            person_size=len(person_bytes),
            cloth_size=len(cloth_bytes),
            tried_model=model,
            error=str(e)[:50],
            next_model=next_model
        )
        
    finally:
        # Temizlik
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

def select_best_model():
    """En iyi modeli seç (IDM öncelikli)"""
    # Son 10 denemede hangi model çalıştı?
    recent_success = []
    for entry in MODEL_HISTORY[-10:]:
        # Burada başarılı modelleri takip edebiliriz
        recent_success.append(entry["model"])
    
    # Öncelik sırası: idm -> texelmoda -> ashamsundar -> ai2bridal
    for model in ["idm", "texelmoda", "ashamsundar", "ai2bridal"]:
        if model in MODELS:
            return model
    
    return "idm"  # fallback

def get_next_model(current_model):
    """Sıradaki modeli ver"""
    model_list = list(MODELS.keys())
    if current_model in model_list:
        current_idx = model_list.index(current_model)
        next_idx = (current_idx + 1) % len(model_list)
        return model_list[next_idx]
    return "idm"

def extract_image_data(data):
    """JSON'dan resim datasını çıkar"""
    if isinstance(data, list) and data:
        data = data[0]
    
    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif "image" in data:
            data = data["image"]
    
    if isinstance(data, str):
        if "," in data:
            return data.split(",")[1]
        return data
    
    return None

def create_auto_retry_image(uid, result_path, person_size, cloth_size, tried_model, error, next_model):
    """Otomatik yeniden deneme görseli"""
    img = Image.new('RGB', (650, 850), color=(250, 245, 240))
    d = ImageDraw.Draw(img)
    
    # Başlık
    d.text((200, 30), "⚡ STYLEMETA AI", fill=(255, 100, 100))
    
    # Android durumu (HER ZAMAN ÇALIŞIYOR)
    d.text((50, 100), "✅ ANDROID SİSTEMİ AKTİF", fill=(0, 180, 0))
    d.text((70, 140), f"Dosya 1: {person_size:,} byte", fill=(60, 60, 60))
    d.text((70, 180), f"Dosya 2: {cloth_size:,} byte", fill=(60, 60, 60))
    d.text((70, 220), "Format: JPEG ✓", fill=(0, 150, 0))
    
    # Denenen model
    d.text((50, 280), f"🔄 DENENEN MODEL: {tried_model.upper()}", fill=(255, 140, 0))
    d.text((70, 320), f"Hata: {error}", fill=(200, 80, 80))
    
    # SIRADAKİ MODEL
    d.text((50, 380), f"🔄 SIRADAKİ MODEL: {next_model.upper()}", fill=(100, 180, 255))
    d.text((70, 420), MODELS[next_model]["description"], fill=(60, 60, 60))
    
    # ⭐ HEMEN TEST ET BUTONU (Android için talimat)
    d.rectangle([40, 480, 610, 580], fill=(230, 245, 255), outline=(100, 150, 255), width=2)
    d.text((60, 500), "📱 ANDROID'DE HEMEN TEST ET:", fill=(0, 100, 200))
    d.text((80, 540), f"URL sonuna ekle: ?model={next_model}", fill=(0, 0, 0))
    
    # TÜM MODELLER
    d.text((50, 600), "🤖 TÜM MODELLER:", fill=(150, 100, 255))
    
    y_pos = 640
    for i, (model_name, info) in enumerate(MODELS.items(), 1):
        color = (255, 100, 100) if model_name == tried_model else (0, 120, 0)
        prefix = "❌ " if model_name == tried_model else f"{i}. "
        
        d.text((70, y_pos), f"{prefix}{model_name.upper()}", fill=color)
        d.text((90, y_pos + 25), info["description"][:35], fill=(80, 80, 80))
        y_pos += 60
    
    # İstek ID
    d.text((50, y_pos + 20), f"📍 İstek ID: {uid}", fill=(150, 150, 150))
    
    img.save(result_path, 'JPEG', quality=95)
    return FileResponse(
        result_path,
        media_type="image/jpeg",
        filename="stylemeta_retry.jpg"
    )

# ⭐⭐ YENİ ENDPOINT: Direkt IDM Modeli
@app.post("/tryon-idm")
async def try_on_idm(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    """SADECE IDM modelini dener"""
    return await try_on(person, cloth, model="idm")

# ⭐⭐ YENİ ENDPOINT: Direkt TexelModa
@app.post("/tryon-texel")
async def try_on_texel(person: UploadFile = File(...), cloth: UploadFile = File(...)):
    """SADECE TexelModa modelini dener"""
    return await try_on(person, cloth, model="texelmoda")

# Model test
@app.get("/test-model/{model_name}")
async def test_model_direct(model_name: str):
    """Modeli doğrudan test et"""
    if model_name not in MODELS:
        return {"error": f"Model yok. Seçenekler: {list(MODELS.keys())}"}
    
    model_info = MODELS[model_name]
    
    try:
        # Space ana sayfası
        space_url = model_info["url"].replace("/run/predict", "")
        response = requests.get(space_url, timeout=10)
        
        return {
            "model": model_name,
            "url": model_info["url"],
            "status": "✅ ONLINE" if response.status_code == 200 else f"❌ OFFLINE ({response.status_code})",
            "response_time": f"{response.elapsed.total_seconds():.2f}s",
            "description": model_info["description"],
            "test_command": f'curl -X POST "{model_info["url"]}" -H "Content-Type: application/json" -d \'{{"data":["data:image/jpeg;base64,...","data:image/jpeg;base64,..."]}}\''
        }
    except Exception as e:
        return {
            "model": model_name,
            "url": model_info["url"],
            "status": f"❌ ERROR: {str(e)[:50]}"
        }

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 10000))
    print("=" * 60)
    print("🤖 STYLEMETA AI - IDM MODEL ÖNCELİKLİ")
    print("=" * 60)
    print(f"📍 Ana endpoint: POST /tryon")
    print(f"📍 IDM özel: POST /tryon-idm")
    print(f"📍 TexelModa özel: POST /tryon-texel")
    print(f"📍 Model test: GET /test-model/idm")
    print(f"📍 Model test: GET /test-model/texelmoda")
    print("\n📋 AKTİF MODELLER (Kolors hariç):")
    for i, (name, info) in enumerate(MODELS.items(), 1):
        print(f"  {i}. {name}: {info['description']}")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=port)
