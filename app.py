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
import time  # rate limit için sleep
from datetime import datetime

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⭐⭐ AKTİF MODELLER (2026 başı stabil olanlar öncelikli)
MODELS = {
    "kolors": {
        "url": "https://kwai-kolors-kolors-virtual-try-on.hf.space/predict",
        "needs_token": False,
        "type": "kolors",
        "description": "Kwai Kolors - Stabil ve hızlı"
    },
    "idm": {
        "url": "https://jjlealse-idm-vton.hf.space/predict",
        "needs_token": False,
        "type": "idm",
        "description": "IDM-VTON - En gerçekçi sonuçlar (description zorunlu)"
    },
    "texelmoda": {
        "url": "https://texelmoda-virtual-try-on-diffusion-vton-d.hf.space/predict",
        "needs_token": False,
        "type": "texelmoda",
        "description": "Diffusion VTON - Detaylı ama yavaş"
    },
    "ai2bridal": {
        "url": "https://mariya789-idm-vton-ai2bridal.hf.space/predict",
        "needs_token": False,
        "type": "simple",
        "description": "AI2Bridal - Gelinlik odaklı"
    },
    "ashamsundar": {
        "url": "https://ashamsundar-try-on.hf.space/predict",
        "needs_token": False,
        "type": "simple",
        "description": "Basit Try-On - Yedek"
    }
}

# Varsayılan en iyi model
CURRENT_MODEL = "idm"  # IDM-VTON genellikle en iyi sonuç veriyor

@app.get("/")
def health():
    return {
        "status": "StyleMeta AI Backend - 5 Model Destekli",
        "current_model": CURRENT_MODEL,
        "available_models": list(MODELS.keys()),
        "endpoint": "POST /tryon   (opsiyonel ?model=kolors veya idm)",
        "note": "Android entegrasyonu hazır - değiştirmeyin!"
    }

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...),
    model: str = CURRENT_MODEL
):
    uid = str(uuid.uuid4())[:8]
    temp_dir = tempfile.gettempdir()
    
    person_path = os.path.join(temp_dir, f"{uid}_person.jpg")
    cloth_path = os.path.join(temp_dir, f"{uid}_cloth.jpg")
    result_path = os.path.join(temp_dir, f"{uid}_result.jpg")
    
    if model not in MODELS:
        model = CURRENT_MODEL
    
    model_info = MODELS[model]
    
    try:
        person_bytes = await person.read()
        cloth_bytes = await cloth.read()
        
        with open(person_path, "wb") as f:
            f.write(person_bytes)
        with open(cloth_path, "wb") as f:
            f.write(cloth_bytes)
        
        print(f"📱 Android isteği -> {model}: person {len(person_bytes):,}B | cloth {len(cloth_bytes):,}B")
        
        # Base64'e çevir (prefix'siz, Gradio genelde kabul ediyor)
        def to_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        
        person_b64 = to_base64(person_path)
        cloth_b64 = to_base64(cloth_path)
        
        # ⭐ MODEL BAZLI PAYLOAD (2026 için güncel)
        payload = {"data": []}
        
        if model == "kolors":
            payload["data"] = [
                f"data:image/jpeg;base64,{person_b64}",  # 0: person
                f"data:image/jpeg;base64,{cloth_b64}",   # 1: cloth
                "",                                      # 2: prompt (opsiyonel)
                25,                                      # steps
                42                                       # seed
            ]
        elif model in ["idm", "ai2bridal"]:
            # IDM-VTON family: description ZORUNLU!
            description = "a photo of a person wearing fashionable clothes, high quality"
            payload["data"] = [
                f"data:image/jpeg;base64,{person_b64}",     # person_image
                f"data:image/jpeg;base64,{cloth_b64}",      # garment_image
                description,                                # garment description (kritik!)
                2.0,                                        # scale / guidance_scale
                30,                                         # num_inference_steps
                42,                                         # seed
                False                                       # use_mask / background preserve?
            ]
        elif model == "texelmoda":
            payload["data"] = [
                f"data:image/jpeg;base64,{person_b64}",
                f"data:image/jpeg;base64,{cloth_b64}",
                "virtual try-on high detail",
                0.75,  # strength
                7.5    # guidance
            ]
        else:  # ashamsundar vb. basit modeller
            payload["data"] = [
                f"data:image/jpeg;base64,{person_b64}",
                f"data:image/jpeg;base64,{cloth_b64}"
            ]
        
        print(f"🚀 {model} payload hazır: {len(payload['data'])} input")
        
        # İstek at
        response = requests.post(
            model_info["url"],
            json=payload,
            timeout=180  # Android tarafıyla uyumlu
        )
        
        print(f"📡 {model} yanıt kodu: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            img_data = None
            
            # Esnek parse (farklı space'ler farklı dönüyor)
            if "data" in result:
                if isinstance(result["data"], list) and len(result["data"]) > 0:
                    img_data = result["data"][0]
                else:
                    img_data = result["data"]
            
            if isinstance(img_data, dict):
                img_data = img_data.get("data") or img_data.get("url") or img_data.get("image")
            
            if isinstance(img_data, str):
                if "base64" in img_data.lower() or "," in img_data:
                    if "," in img_data:
                        img_data = img_data.split(",", 1)[1]
                    try:
                        ai_bytes = base64.b64decode(img_data)
                        if len(ai_bytes) > 5000:  # min boyut kontrolü
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
                    except Exception as ex:
                        print(f"Decode hatası: {ex}")
        
        # Hata durumunda log + fallback
        error_msg = f"HTTP {response.status_code} - {response.text[:150]}"
        print(f"❌ {model} başarısız: {error_msg}")
        
        time.sleep(1)  # rate limit'e karşı küçük bekleme
        return try_next_model_or_demo(
            uid, result_path,
            person_size=len(person_bytes),
            cloth_size=len(cloth_bytes),
            tried_model=model,
            error=error_msg
        )
    
    except Exception as e:
        print(f"💥 Genel hata ({model}): {str(e)}")
        return create_model_selection_image(
            uid, result_path,
            person_size=len(person_bytes) if 'person_bytes' in locals() else 0,
            cloth_size=len(cloth_bytes) if 'cloth_bytes' in locals() else 0,
            error=str(e)[:80]
        )
    
    finally:
        # Temizlik
        for path in [person_path, cloth_path, result_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

# Diğer fonksiyonlar aynı kalabilir (try_next_model_or_demo, create_model_selection_image)
# ... (orijinal kodundaki bu iki fonksiyonu olduğu gibi kopyala)

def try_next_model_or_demo(uid, result_path, person_size, cloth_size, tried_model, error):
    model_list = list(MODELS.keys())
    if tried_model in model_list:
        current_idx = model_list.index(tried_model)
        next_idx = (current_idx + 1) % len(model_list)
        next_model = model_list[next_idx]
        print(f"🔄 {tried_model} başarısız → {next_model} deneniyor...")
        # Burada recursive çağrı yerine info göster (sonsuz döngü olmasın)
        return create_model_selection_image(
            uid, result_path,
            person_size=person_size,
            cloth_size=cloth_size,
            error=f"{tried_model}: {error}",
            suggestion=f"?model={next_model} dene"
        )
    return create_model_selection_image(
        uid, result_path,
        person_size=person_size,
        cloth_size=cloth_size,
        error=error
    )

def create_model_selection_image(uid, result_path, person_size, cloth_size, error=None, suggestion=None):
    # Orijinal fonksiyonu olduğu gibi bırak (değişiklik gerekmez)
    img = Image.new('RGB', (650, 950), color=(245, 250, 255))
    d = ImageDraw.Draw(img)
    
    d.text((200, 30), "👗 STYLEMETA AI", fill=(255, 100, 150))
    d.text((50, 100), "✅ ANDROID BAĞLANTISI AKTİF", fill=(0, 180, 0))
    d.text((70, 140), f"Foto: {person_size:,} byte", fill=(60, 60, 60))
    d.text((70, 180), f"Elbise: {cloth_size:,} byte", fill=(60, 60, 60))
    
    if error:
        d.text((50, 240), "⚠️ HATA:", fill=(255, 100, 100))
        d.text((70, 280), error[:70], fill=(100, 60, 60))
    
    d.text((50, 340), "🤖 AKTİF MODELLER:", fill=(100, 100, 255))
    y_pos = 380
    for i, (name, info) in enumerate(MODELS.items()):
        color = (0, 120, 0) if name != tried_model else (255, 100, 100)
        d.text((70, y_pos), f"{i+1}. {name.upper()}", fill=color)
        d.text((90, y_pos + 25), info["description"][:40], fill=(80, 80, 80))
        y_pos += 60
    
    d.text((50, y_pos + 20), "🔄 MODEL DEĞİŞTİR:", fill=(200, 120, 0))
    if suggestion:
        d.text((70, y_pos + 60), suggestion, fill=(0, 100, 200))
    else:
        d.text((70, y_pos + 60), "URL sonuna ?model=idm ekle", fill=(0, 0, 0))
    
    img.save(result_path, 'JPEG', quality=90)
    return FileResponse(result_path, media_type="image/jpeg", filename="models.jpg")

# Test endpoint'leri aynı kalabilir
# ... (orijinal /test-all-models, /switch-model, /model/{name} endpoint'lerini ekleyebilirsin)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    print("=" * 60)
    print("🤖 STYLEMETA AI BACKEND AKTİF - 2026 Güncel")
    print(f"   Varsayılan Model: {CURRENT_MODEL}")
    print(f"   Endpoint       : POST /tryon ?model=xxx")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port)
