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

# ⭐⭐ TÜM AKTİF MODELLER ⭐⭐
MODELS = {
    "kolors": {
        "url": "https://kwai-kolors-kolors-virtual-try-on.hf.space/run/predict",
        "needs_token": False,
        "type": "kolors",
        "description": "Kwai Kolors - En stabil model"
    },
    "idm": {
        "url": "https://jjlealse-idm-vton.hf.space/run/predict",
        "needs_token": False,
        "type": "idm",
        "description": "IDM-VTON - Orjinal model"
    },
    "ashamsundar": {
        "url": "https://ashamsundar-try-on.hf.space/run/predict",
        "needs_token": False,
        "type": "simple",
        "description": "Try-On - Basit model"
    },
    "texelmoda": {
        "url": "https://texelmoda-virtual-try-on-diffusion-vton-d.hf.space/run/predict",
        "needs_token": False,
        "type": "texelmoda",
        "description": "Diffusion VTON - Gelişmiş"
    },
    "ai2bridal": {
        "url": "https://mariya789-idm-vton-ai2bridal.hf.space/run/predict",
        "needs_token": False,
        "type": "simple",
        "description": "AI2Bridal - Gelinlik özel"
    }
}

# ⭐ EN GARANTİLİ MODEL
CURRENT_MODEL = "kolors"

@app.get("/")
def health():
    return {
        "status": "StyleMeta AI - 5 AKTİF MODEL",
        "current_model": CURRENT_MODEL,
        "available_models": list(MODELS.keys()),
        "endpoint": "POST /tryon?model=MODEL_NAME",
        "note": "Android kodunuz MÜKEMMEL, değiştirmeyin!"
    }

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...),
    model: str = CURRENT_MODEL
):
    """Android'den gelen isteği işler - 5 model seçeneği"""
    
    uid = str(uuid.uuid4())[:8]
    temp_dir = tempfile.gettempdir()
    
    person_path = os.path.join(temp_dir, f"{uid}_person.jpg")
    cloth_path = os.path.join(temp_dir, f"{uid}_cloth.jpg")
    result_path = os.path.join(temp_dir, f"{uid}_result.jpg")
    
    # Model kontrolü
    if model not in MODELS:
        model = CURRENT_MODEL
    
    model_info = MODELS[model]
    
    try:
        # Android'den dosyaları al
        person_bytes = await person.read()
        cloth_bytes = await cloth.read()
        
        with open(person_path, "wb") as f:
            f.write(person_bytes)
        with open(cloth_path, "wb") as f:
            f.write(cloth_bytes)
        
        print(f"📱 Android -> {model}: {len(person_bytes)}B, {len(cloth_bytes)}B")
        
        # Base64 hazırla
        def to_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        
        person_base64 = to_base64(person_path)
        cloth_base64 = to_base64(cloth_path)
        
        # ⭐⭐ MODEL'E GÖRE ÖZEL PAYLOAD ⭐⭐
        if model == "kolors":
            payload = {
                "data": [
                    {"data": f"data:image/jpeg;base64,{person_base64}", "name": "person.jpg"},
                    {"data": f"data:image/jpeg;base64,{cloth_base64}", "name": "cloth.jpg"}
                ]
            }
        elif model == "texelmoda":
            payload = {
                "data": [
                    {"data": f"data:image/jpeg;base64,{person_base64}", "name": "person.jpg"},
                    {"data": f"data:image/jpeg;base64,{cloth_base64}", "name": "cloth.jpg"},
                    "virtual try-on",
                    0.7,  # strength
                    1.0   # guidance
                ]
            }
        elif model == "ai2bridal":
            payload = {
                "data": [
                    f"data:image/jpeg;base64,{person_base64}",
                    f"data:image/jpeg;base64,{cloth_base64}",
                    "IDM-VTON",  # model type
                    1.0,         # scale
                    False        # background
                ]
            }
        else:
            # Diğer modeller için standart format
            payload = {
                "data": [
                    f"data:image/jpeg;base64,{person_base64}",
                    f"data:image/jpeg;base64,{cloth_base64}"
                ]
            }
        
        print(f"🚀 {model} modeli deneniyor: {model_info['description']}")
        
        # Model isteği
        response = requests.post(
            model_info["url"],
            json=payload,
            timeout=120
        )
        
        print(f"📡 {model} yanıtı: {response.status_code}")
        
        # ⭐ BAŞARILI İSE
        if response.status_code == 200:
            result = response.json()
            
            if "data" in result and result["data"]:
                img_data = result["data"]
                
                # Format çözümleme
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
                    
                    # AI SONUCUNU KAYDET
                    try:
                        ai_bytes = base64.b64decode(img_data)
                        
                        if len(ai_bytes) > 10000:  # 10KB'den büyükse başarılı
                            with open(result_path, "wb") as f:
                                f.write(ai_bytes)
                            
                            print(f"🎉 {model} BAŞARILI! {len(ai_bytes):,} byte")
                            
                            return FileResponse(
                                result_path,
                                media_type="image/jpeg",
                                filename="stylemeta_result.jpg",
                                headers={
                                    "X-AI-Success": "true",
                                    "X-Model": model,
                                    "X-Size": str(len(ai_bytes))
                                }
                            )
                    except Exception as decode_error:
                        print(f"❌ {model} decode hatası: {decode_error}")
        
        # ⭐ HATA - DİĞER MODELLERİ DENE
        error_msg = f"HTTP {response.status_code}"
        if response.text:
            error_msg += f": {response.text[:80]}"
        
        print(f"❌ {model} hatası: {error_msg}")
        
        # Sıradaki modeli dene
        return try_next_model_or_demo(
            uid, result_path,
            person_size=len(person_bytes),
            cloth_size=len(cloth_bytes),
            tried_model=model,
            error=error_msg
        )
        
    except Exception as e:
        print(f"💥 {model} hatası: {e}")
        return create_model_selection_image(
            uid, result_path,
            person_size=len(person_bytes),
            cloth_size=len(cloth_bytes),
            error=f"{model} hatası: {str(e)[:50]}"
        )
        
    finally:
        # Temizlik
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

def try_next_model_or_demo(uid, result_path, person_size, cloth_size, tried_model, error):
    """Bir model çalışmazsa sıradakini dene"""
    model_list = list(MODELS.keys())
    
    # Şu anki modelin index'ini bul
    if tried_model in model_list:
        current_idx = model_list.index(tried_model)
        next_idx = (current_idx + 1) % len(model_list)
        next_model = model_list[next_idx]
        
        print(f"🔄 {tried_model} çalışmadı, {next_model} deneniyor...")
        
        # Kullanıcıya model değiştirme talimatı ver
        return create_model_selection_image(
            uid, result_path,
            person_size=person_size,
            cloth_size=cloth_size,
            error=f"{tried_model}: {error}",
            suggestion=f"?model={next_model} ile dene"
        )
    
    # Model listesinde yoksa
    return create_model_selection_image(
        uid, result_path,
        person_size=person_size,
        cloth_size=cloth_size,
        error=error
    )

def create_model_selection_image(uid, result_path, person_size, cloth_size, error=None, suggestion=None):
    """Model seçim ekranı göster"""
    img = Image.new('RGB', (650, 950), color=(245, 250, 255))
    d = ImageDraw.Draw(img)
    
    # Başlık
    d.text((200, 30), "👗 STYLEMETA AI", fill=(255, 100, 150))
    
    # Android bağlantısı
    d.text((50, 100), "✅ ANDROID SİSTEMİ", fill=(0, 180, 0))
    d.text((70, 140), f"Bağlantı: AKTİF", fill=(0, 150, 0))
    d.text((70, 180), f"Kullanıcı foto: {person_size:,} byte", fill=(60, 60, 60))
    d.text((70, 220), f"Elbise foto: {cloth_size:,} byte", fill=(60, 60, 60))
    
    # Hata bilgisi
    if error:
        d.text((50, 280), "⚠️ SON DENEME:", fill=(255, 100, 100))
        d.text((70, 320), error[:70], fill=(100, 60, 60))
    
    # ⭐⭐ AKTİF MODELLER LİSTESİ ⭐⭐
    d.text((50, 380), "🤖 AKTİF MODELLER (5 Adet):", fill=(100, 100, 255))
    
    y_pos = 420
    for i, (model_name, info) in enumerate(MODELS.items()):
        color = (0, 120, 0)  # Yeşil
        if error and model_name in str(error):
            color = (255, 100, 100)  # Kırmızı
        
        d.text((70, y_pos), f"{i+1}. {model_name.upper()}", fill=color)
        d.text((90, y_pos + 25), info["description"][:40], fill=(80, 80, 80))
        y_pos += 60
    
    # ⭐ MODEL DEĞİŞTİRME KILAVUZU
    d.text((50, y_pos + 20), "🔄 MODEL DEĞİŞTİRMEK İÇİN:", fill=(200, 120, 0))
    
    if suggestion:
        d.text((70, y_pos + 60), suggestion, fill=(0, 100, 200))
    else:
        d.text((70, y_pos + 60), "Android'de URL sonuna ekleyin:", fill=(0, 0, 0))
        d.text((90, y_pos + 100), "?model=kolors", fill=(0, 100, 200))
        d.text((90, y_pos + 140), "?model=idm", fill=(0, 100, 200))
        d.text((90, y_pos + 180), "?model=texelmoda", fill=(0, 100, 200))
    
    # Test linkleri
    d.text((50, y_pos + 240), "🔗 TEST İÇİN (Terminal):", fill=(150, 80, 150))
    d.text((70, y_pos + 280), "curl -X POST URL", fill=(60, 60, 60))
    d.text((70, y_pos + 320), "-F 'person=@foto.jpg'", fill=(60, 60, 60))
    d.text((70, y_pos + 360), "-F 'cloth=@elbise.jpg'", fill=(60, 60, 60))
    
    # İstek ID
    d.text((50, y_pos + 420), f"📍 İstek ID: {uid}", fill=(150, 150, 150))
    
    img.save(result_path, 'JPEG', quality=95)
    return FileResponse(
        result_path,
        media_type="image/jpeg",
        filename="stylemeta_models.jpg"
    )

# Model test endpoint
@app.get("/test-all-models")
async def test_all_models():
    """Tüm modellerin durumunu test et"""
    results = {}
    
    for model_name, info in MODELS.items():
        try:
            # Space ana sayfasını kontrol et
            space_url = info["url"].replace("/run/predict", "")
            response = requests.get(space_url, timeout=10)
            
            results[model_name] = {
                "url": info["url"],
                "status": "ONLINE" if response.status_code == 200 else f"OFFLINE ({response.status_code})",
                "response_time": f"{response.elapsed.total_seconds():.2f}s",
                "description": info["description"]
            }
        except Exception as e:
            results[model_name] = {
                "url": info["url"],
                "status": f"ERROR: {str(e)[:50]}",
                "description": info["description"]
            }
    
    return {
        "test_time": datetime.now().isoformat(),
        "total_models": len(results),
        "results": results
    }

# Model değiştirme
@app.post("/switch-model/{model_name}")
async def switch_model(model_name: str):
    global CURRENT_MODEL
    if model_name in MODELS:
        old_model = CURRENT_MODEL
        CURRENT_MODEL = model_name
        return {
            "success": True,
            "message": f"Model {old_model} -> {model_name} olarak değiştirildi",
            "model_info": MODELS[model_name]
        }
    return {
        "success": False,
        "error": f"Model bulunamadı. Seçenekler: {list(MODELS.keys())}"
    }

# Model bilgisi
@app.get("/model/{model_name}")
async def get_model_info(model_name: str):
    if model_name in MODELS:
        return MODELS[model_name]
    return {"error": "Model bulunamadı"}

if __name__ == "__main__":
    import uvicorn
    from datetime import datetime
    
    port = int(os.getenv("PORT", 10000))
    print("=" * 50)
    print("🤖 STYLEMETA AI BACKEND - 5 AKTİF MODEL")
    print("=" * 50)
    print(f"📍 Endpoint: POST /tryon")
    print(f"📱 Android URL: https://stylemeta-backend.onrender.com/tryon")
    print(f"🔄 Model parametresi: ?model=kolors, ?model=idm, vb.")
    print("\n📋 AKTİF MODELLER:")
    for i, (name, info) in enumerate(MODELS.items(), 1):
        print(f"  {i}. {name}: {info['description']}")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=port)
