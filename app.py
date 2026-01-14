from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFilter
import requests
import os
import uuid
import base64
import tempfile
import io

app = FastAPI(title="StyleMeta AI Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⭐ HUGGING FACE AYARLARI
HF_SPACE_URL = "https://kwai-kolors-kolors-virtual-try-on.hf.space/run/predict"
HF_TOKEN = os.getenv("HF_TOKEN", "")
AI_ENABLED = True if HF_TOKEN else False  # Token varsa AI aktif

@app.get("/")
def health():
    ai_status = "✅ AKTİF" if AI_ENABLED else "⚠️ TOKEN GEREKLİ"
    return {
        "status": "StyleMeta AI Backend",
        "ai_enabled": ai_status,
        "model": "Kolors-Virtual-Try-On",
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
        # 1. DOSYALARI KAYDET
        person_bytes = await person.read()
        cloth_bytes = await cloth.read()
        
        with open(person_path, "wb") as f:
            f.write(person_bytes)
        with open(cloth_path, "wb") as f:
            f.write(cloth_bytes)
        
        print(f"📱 İstek: person={len(person_bytes)}B, cloth={len(cloth_bytes)}B")
        
        # 2. AI AKTİF Mİ KONTROL ET
        if not AI_ENABLED:
            print("⚠️ AI pasif - test görseli dönülüyor")
            return create_demo_image(
                uid, result_path, 
                person_size=len(person_bytes),
                cloth_size=len(cloth_bytes),
                ai_status="PASİF (HF_TOKEN gerekli)"
            )
        
        # 3. HUGGING FACE AI ÇAĞRISI
        print(f"🚀 AI aktif - Hugging Face'e bağlanılıyor...")
        
        try:
            # Resimleri base64'e çevir
            def img_to_base64(path):
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode('utf-8')
            
            # Kolors modeli için payload
            payload = {
                "data": [
                    {
                        "data": f"data:image/jpeg;base64,{img_to_base64(person_path)}",
                        "name": "person.jpg"
                    },
                    {
                        "data": f"data:image/jpeg;base64,{img_to_base64(cloth_path)}",
                        "name": "cloth.jpg"
                    }
                ]
            }
            
            headers = {"Authorization": f"Bearer {HF_TOKEN}"}
            
            # AI isteği (timeout uzun tut)
            response = requests.post(
                HF_SPACE_URL,
                json=payload,
                headers=headers,
                timeout=300  # 5 dakika
            )
            
            print(f"📡 AI Yanıt: {response.status_code}")
            
            # 4. BAŞARILI AI YANITI
            if response.status_code == 200:
                result = response.json()
                
                if "data" in result and result["data"]:
                    img_data = result["data"]
                    
                    # Farklı formatlar için
                    if isinstance(img_data, list):
                        img_data = img_data[0]
                    
                    if "," in img_data:
                        img_data = img_data.split(",")[1]
                    
                    # AI sonucunu kaydet
                    ai_result_bytes = base64.b64decode(img_data)
                    
                    with open(result_path, "wb") as f:
                        f.write(ai_result_bytes)
                    
                    print(f"🎉 AI BAŞARILI! {len(ai_result_bytes)} byte")
                    
                    # Android'e AI sonucunu gönder
                    return FileResponse(
                        result_path,
                        media_type="image/jpeg",
                        filename=f"stylemeta_ai_{uid}.jpg",
                        headers={
                            "X-AI-Generated": "true",
                            "X-Model": "Kolors",
                            "X-Request-ID": uid
                        }
                    )
            
            # 5. AI HATASI - demo görsele dön
            print(f"❌ AI hatası: {response.status_code}")
            return create_demo_image(
                uid, result_path,
                person_size=len(person_bytes),
                cloth_size=len(cloth_bytes),
                ai_status=f"AI HATASI ({response.status_code})"
            )
            
        except requests.exceptions.Timeout:
            print("⏰ AI timeout (5 dakika)")
            return create_demo_image(
                uid, result_path,
                person_size=len(person_bytes),
                cloth_size=len(cloth_bytes),
                ai_status="AI TIMEOUT (çok uzun sürdü)"
            )
            
        except Exception as ai_error:
            print(f"💥 AI exception: {ai_error}")
            return create_demo_image(
                uid, result_path,
                person_size=len(person_bytes),
                cloth_size=len(cloth_bytes),
                ai_status=f"AI HATASI: {str(ai_error)[:50]}"
            )
    
    except Exception as e:
        print(f"🔥 Genel hata: {e}")
        # Acil durum görseli
        return create_error_image(uid, temp_dir, str(e))
    
    finally:
        # Temizlik
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

def create_demo_image(uid, result_path, person_size, cloth_size, ai_status="AKTİF"):
    """AI olmadan da güzel demo görsel"""
    img = Image.new('RGB', (600, 900), color=(245, 245, 250))
    d = ImageDraw.Draw(img)
    
    # Başlık
    d.text((200, 30), "👗 STYLEMETA AI", fill=(255, 107, 129))
    
    # İstek bilgileri
    d.text((50, 100), "📊 İSTEK BİLGİLERİ:", fill=(0, 0, 0))
    d.text((70, 140), f"İstek ID: {uid}", fill=(100, 100, 100))
    d.text((70, 180), f"Kullanıcı: {person_size:,} byte", fill=(50, 50, 50))
    d.text((70, 220), f"Elbise: {cloth_size:,} byte", fill=(50, 50, 50))
    
    # Sistem durumu
    d.text((50, 280), "✅ SİSTEM DURUMU:", fill=(0, 150, 0))
    d.text((70, 320), "Backend: ÇALIŞIYOR", fill=(0, 150, 0))
    d.text((70, 360), "Android: BAĞLANDI", fill=(0, 150, 0))
    d.text((70, 400), f"AI: {ai_status}", 
           fill=(0, 150, 0) if "AKTİF" in ai_status else (255, 100, 100))
    
    # AI entegrasyon bilgisi
    d.text((50, 460), "🤖 AI ENTEGRASYONU:", fill=(128, 0, 128))
    d.text((70, 500), "Model: Kolors-Virtual-Try-On", fill=(0, 0, 0))
    d.text((70, 540), "Platform: Hugging Face", fill=(0, 0, 0))
    d.text((70, 580), f"Token: {'✅ VAR' if HF_TOKEN else '❌ EKSİK'}", fill=(0, 0, 0))
    
    # Yapılacaklar (AI pasifse)
    if not HF_TOKEN or "HATASI" in ai_status:
        d.text((50, 620), "🔧 YAPILACAKLAR:", fill=(200, 100, 0))
        d.text((70, 660), "1. Hugging Face token al", fill=(0, 0, 0))
        d.text((70, 700), "2. Render'da HF_TOKEN ekle", fill=(0, 0, 0))
        d.text((70, 740), "3. Deploy'u yeniden başlat", fill=(0, 0, 0))
    
    # Sonuç
    d.rectangle([40, 780, 560, 850], fill=(230, 245, 230), outline=(0, 180, 0), width=3)
    d.text((60, 800), "✨ SİSTEM HAZIR!", fill=(0, 120, 0))
    
    img.save(result_path, 'JPEG', quality=95, optimize=True)
    return FileResponse(result_path, media_type="image/jpeg")

def create_error_image(uid, temp_dir, error_msg):
    """Hata görseli"""
    error_path = os.path.join(temp_dir, f"{uid}_error.jpg")
    img = Image.new('RGB', (400, 300), color=(255, 230, 230))
    d = ImageDraw.Draw(img)
    d.text((20, 50), "⚠️  GEÇİCİ HATA", fill=(200, 0, 0))
    d.text((20, 100), error_msg[:80], fill=(0, 0, 0))
    d.text((20, 150), f"ID: {uid}", fill=(100, 100, 100))
    img.save(error_path, 'JPEG')
    return FileResponse(error_path, media_type="image/jpeg")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    print(f"🚀 Server başlatılıyor... AI: {'AKTİF' if AI_ENABLED else 'PASİF'}")
    uvicorn.run(app, host="0.0.0.0", port=port)
