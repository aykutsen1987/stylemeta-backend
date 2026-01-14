from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import uuid
import base64
import tempfile
from PIL import Image, ImageDraw
import io

app = FastAPI(title="StyleMeta Backend")

# CORS ayarları (aynı)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TEST MODU'nu False yapın!
TEST_MODE = False  # ⬅️ BU SATIRI DEĞİŞTİRİN!

# HF Space URL (IDM-VTON)
HF_SPACE_URL = "https://jjlealse-idm-vton.hf.space/run/predict"

@app.get("/")
def health():
    return {"status": "StyleMeta backend çalışıyor", "mode": "PRODUCTION" if not TEST_MODE else "TEST"}

@app.post("/tryon")
async def try_on(
    person: UploadFile = File(...),
    cloth: UploadFile = File(...)
):
    uid = str(uuid.uuid4())[:8]
    temp_dir = tempfile.gettempdir()
    
    person_path = os.path.join(temp_dir, f"{uid}_person.jpg")
    cloth_path = os.path.join(temp_dir, f"{uid}_cloth.jpg")
    result_path = os.path.join(temp_dir, f"{uid}_result.jpg")
    
    try:
        # 1. Dosyaları kaydet
        print(f"📱 İstek alındı. ID: {uid}")
        
        person_content = await person.read()
        cloth_content = await cloth.read()
        
        with open(person_path, "wb") as f:
            f.write(person_content)
        with open(cloth_path, "wb") as f:
            f.write(cloth_content)
        
        print(f"💾 Dosya boyutları: person={len(person_content)}B, cloth={len(cloth_content)}B")
        
        # 2. TEST MODU kontrolü
        if TEST_MODE:
            print("🧪 TEST MODU: Test görseli oluşturuluyor")
            img = Image.new('RGB', (400, 600), color='lightblue')
            d = ImageDraw.Draw(img)
            d.text((100, 250), "TEST MODE\nAndroid OK!", fill='black')
            img.save(result_path, 'JPEG')
            
            return FileResponse(
                result_path,
                media_type="image/jpeg",
                filename=f"tryon_test_{uid}.jpg"
            )
        
        # 3. HUGGING FACE ENTEGRASYONU
        print("🚀 Hugging Face'e bağlanılıyor...")
        
        # Token kontrolü
        HF_TOKEN = os.getenv("HF_TOKEN", "")
        if not HF_TOKEN:
            print("⚠️ UYARI: HF_TOKEN bulunamadı! Ortam değişkenlerini kontrol edin.")
            # Fallback: test moduna dön
            return await fallback_test_image(uid, result_path)
        
        # Base64'e çevir
        def to_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        
        # HF için payload (IDM-VTON formatı)
        payload = {
            "data": [
                f"data:image/jpeg;base64,{to_base64(person_path)}",
                f"data:image/jpeg;base64,{to_base64(cloth_path)}"
            ]
        }
        
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        
        print(f"🌐 HF Space'e istek gönderiliyor: {HF_SPACE_URL}")
        
        # Timeout'u artır (AI işlemi uzun sürebilir)
        response = requests.post(
            HF_SPACE_URL,
            json=payload,
            headers=headers,
            timeout=180  # 3 dakika
        )
        
        print(f"📡 HF Response: {response.status_code}")
        
        if response.status_code != 200:
            error_msg = f"HF Hatası ({response.status_code}): {response.text[:200]}"
            print(f"❌ {error_msg}")
            
            # HF hatasında fallback test görseli
            return await fallback_hf_error_image(uid, result_path, error_msg)
        
        # Response'u parse et
        result = response.json()
        print(f"✅ HF'den JSON yanıtı alındı")
        
        if "data" not in result or not result["data"]:
            raise HTTPException(503, detail="HF boş sonuç döndü")
        
        # Base64 resmini çıkar
        img_base64 = result["data"][0]
        if isinstance(img_base64, str) and "," in img_base64:
            img_base64 = img_base64.split(",")[1]
        
        # Decode et
        try:
            img_bytes = base64.b64decode(img_base64)
            
            # Boş resim kontrolü
            if len(img_bytes) < 5000:  # Çok küçükse hata
                print(f"⚠️ Şüpheli resim boyutu: {len(img_bytes)} bytes")
                return await fallback_small_image(uid, result_path, len(img_bytes))
            
            # Kaydet
            with open(result_path, "wb") as f:
                f.write(img_bytes)
            
            print(f"✅ AI sonucu kaydedildi: {len(img_bytes)} bytes")
            
            return FileResponse(
                result_path,
                media_type="image/jpeg",
                filename=f"stylemeta_ai_{uid}.jpg",
                headers={"X-AI-Generated": "true", "X-Request-ID": uid}
            )
            
        except Exception as decode_error:
            print(f"❌ Base64 decode hatası: {decode_error}")
            return await fallback_decode_error(uid, result_path, str(decode_error))
    
    except requests.exceptions.Timeout:
        print("⏰ HF Timeout hatası (180s aşıldı)")
        return await fallback_timeout_image(uid, result_path)
    
    except Exception as e:
        print(f"❌ Genel hata: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Hata görseli
        return await error_image_response(uid, result_path, str(e))
    
    finally:
        # Temizlik
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

# Fallback fonksiyonları
async def fallback_test_image(uid, result_path):
    """Token yoksa test görseli döner"""
    img = Image.new('RGB', (512, 768), color='#e6f7ff')
    d = ImageDraw.Draw(img)
    d.text((50, 100), "🔑 HF_TOKEN GEREKLİ", fill='red')
    d.text((50, 150), "Render Environment'a ekleyin:", fill='black')
    d.text((50, 200), "KEY: HF_TOKEN", fill='darkgreen')
    d.text((50, 250), f"VALUE: hf_... token", fill='darkgreen')
    d.text((50, 350), f"Request ID: {uid}", fill='gray')
    img.save(result_path, 'JPEG')
    
    return FileResponse(
        result_path,
        media_type="image/jpeg",
        filename=f"token_required_{uid}.jpg"
    )

async def fallback_hf_error_image(uid, result_path, error_msg):
    """HF hatasında bilgilendirici görsel"""
    img = Image.new('RGB', (512, 768), color='#fff0f0')
    d = ImageDraw.Draw(img)
    d.text((50, 100), "🤖 AI SERVİS HATASI", fill='red')
    d.text((50, 150), f"Hata: {error_msg[:50]}...", fill='black')
    d.text((50, 200), "Model: IDM-VTON (jjlealse)", fill='blue')
    d.text((50, 250), "Lütfen daha sonra tekrar deneyin", fill='darkred')
    d.text((50, 350), f"Request ID: {uid}", fill='gray')
    img.save(result_path, 'JPEG')
    
    return FileResponse(
        result_path,
        media_type="image/jpeg",
        filename=f"hf_error_{uid}.jpg"
    )

async def error_image_response(uid, result_path, error_msg):
    """Genel hata görseli"""
    img = Image.new('RGB', (400, 300), color='#ffcccc')
    d = ImageDraw.Draw(img)
    d.text((20, 50), "BACKEND HATASI", fill='red')
    d.text((20, 100), error_msg[:100], fill='black')
    d.text((20, 150), f"ID: {uid}", fill='gray')
    img.save(result_path, 'JPEG')
    
    return FileResponse(
        result_path,
        media_type="image/jpeg",
        filename="error_result.jpg"
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
