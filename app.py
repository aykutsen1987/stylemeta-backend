from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import uuid
import tempfile
from PIL import Image, ImageDraw, ImageFont
import io

app = FastAPI()

# ✅ CRITICAL: Android için CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ✅ Android'den gelen multipart field isimleri
# "person" ve "cloth" - KODUNUZLA BİREBİR AYNI!
print("✅ Backend hazır: /tryon endpoint'i 'person' ve 'cloth' bekliyor")

@app.get("/")
def health():
    return {"status": "StyleMeta backend çalışıyor", "endpoint": "/tryon"}

@app.post("/tryon")
async def try_on_endpoint(
    person: UploadFile = File(..., description="Kullanıcı fotoğrafı"),
    cloth: UploadFile = File(..., description="Elbise fotoğrafı")
):
    """
    Android'den gelen isteği işler
    Field isimleri: "person" ve "cloth" (ApiService.kt ile aynı)
    """
    
    print(f"📱 Android'den istek alındı!")
    print(f"   - Person: {person.filename} ({person.content_type})")
    print(f"   - Cloth: {cloth.filename} ({cloth.content_type})")
    
    # Geçici dosya yolları
    temp_dir = tempfile.gettempdir()
    uid = str(uuid.uuid4())[:8]
    
    person_path = os.path.join(temp_dir, f"{uid}_person.jpg")
    cloth_path = os.path.join(temp_dir, f"{uid}_cloth.jpg")
    result_path = os.path.join(temp_dir, f"{uid}_result.jpg")
    
    try:
        # 1. DOSYALARI KAYDET
        print(f"💾 Dosyalar kaydediliyor...")
        
        # Person dosyasını kaydet
        person_content = await person.read()
        with open(person_path, "wb") as f:
            f.write(person_content)
        print(f"   ✅ Person: {len(person_content)} bytes")
        
        # Cloth dosyasını kaydet
        cloth_content = await cloth.read()
        with open(cloth_path, "wb") as f:
            f.write(cloth_content)
        print(f"   ✅ Cloth: {len(cloth_content)} bytes")
        
        # 2. TEST MODU: Hemen cevap dön (Android test için)
        # Hugging Face'e bağlanmadan önce çalıştığını doğrula
        
        # Basit bir test görseli oluştur
        img_width, img_height = 512, 768
        
        # Person resmini yükle (boyut kontrolü)
        try:
            person_img = Image.open(io.BytesIO(person_content))
            p_width, p_height = person_img.size
            print(f"   📐 Person boyutu: {p_width}x{p_height}")
        except:
            print("   ⚠️ Person resmi açılamadı")
            person_img = None
        
        # Test görseli oluştur
        result_img = Image.new('RGB', (img_width, img_height), color='#f0f8ff')
        draw = ImageDraw.Draw(result_img)
        
        # Basit çizimler
        draw.rectangle([50, 50, img_width-50, img_height-50], outline='blue', width=3)
        
        # Metinler
        draw.text((img_width//2 - 100, 100), "STYLEMETA AI", fill='darkblue')
        draw.text((img_width//2 - 150, 150), "Virtual Try-On Result", fill='green')
        draw.text((img_width//2 - 200, 200), "Android Backend Bağlantısı BAŞARILI", fill='red')
        
        if person_img:
            # Küçük thumbnail ekle
            thumb = person_img.resize((100, 150))
            result_img.paste(thumb, (50, 300))
            draw.text((50, 460), "Kullanıcı", fill='black')
        
        draw.text((img_width//2 - 100, 500), f"ID: {uid}", fill='gray')
        draw.text((50, 550), "Backend: stylemeta-backend.onrender.com", fill='darkgreen')
        draw.text((50, 600), "Endpoint: /tryon", fill='darkgreen')
        draw.text((50, 650), f"Files: {person.filename}, {cloth.filename}", fill='darkgreen')
        
        # Sonucu kaydet
        result_img.save(result_path, 'JPEG', quality=95)
        print(f"   ✅ Test görseli oluşturuldu: {result_path}")
        
        # 3. Android'e JPEG olarak dön
        print(f"   📤 Android'e JPEG gönderiliyor...")
        
        return FileResponse(
            result_path,
            media_type="image/jpeg",
            filename=f"tryon_result_{uid}.jpg",
            headers={
                "X-Android-Compatible": "true",
                "X-Result-ID": uid
            }
        )
        
    except Exception as e:
        print(f"   ❌ HATA: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Hata durumunda hata görseli oluştur
        error_img = Image.new('RGB', (400, 200), color='#ffcccc')
        draw = ImageDraw.Draw(error_img)
        draw.text((20, 50), "HATA OLUŞTU", fill='red')
        draw.text((20, 100), str(e)[:50], fill='black')
        error_img.save(result_path, 'JPEG')
        
        return FileResponse(
            result_path,
            media_type="image/jpeg",
            filename="error_result.jpg"
        )
    
    finally:
        # Temizlik
        import time
        time.sleep(1)  # Android'in dosyayı alması için bekle
        
        for path in [person_path, cloth_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"   🧹 Temizlendi: {os.path.basename(path)}")
                except:
                    pass

# ✅ OPTIONS endpoint'i (CORS için gerekli)
@app.options("/tryon")
async def options_tryon():
    return {"message": "CORS allowed"}

# Render için port ayarı
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
