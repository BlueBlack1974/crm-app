"""
WhatsApp mesaj gönderme test scripti
"""
from app import create_app, db
from app.models import FirmaWhatsAppAyar, Firma
import requests
import json

app = create_app()

with app.app_context():
    print("=" * 60)
    print("WhatsApp Mesaj Gönderme Testi")
    print("=" * 60)
    
    # Firma ve WhatsApp ayarlarını al
    firma = Firma.query.first()
    if not firma:
        print("HATA: Firma bulunamadı!")
        exit(1)
    
    print(f"Firma: {firma.FirmaAdi} (ID: {firma.FirmaID})")
    
    whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=firma.FirmaID, Aktif=True).first()
    if not whatsapp_ayar:
        print("HATA: WhatsApp ayarları bulunamadı!")
        exit(1)
    
    print(f"Phone Number ID: {whatsapp_ayar.PhoneNumberID}")
    print(f"Access Token (ilk 20): {whatsapp_ayar.AccessToken[:20] if whatsapp_ayar.AccessToken else 'YOK'}...")
    print(f"Test Numarası: {whatsapp_ayar.TestNumarasi or 'Kayıtlı değil'}")
    print()
    
    # Test numarası
    test_phone = "905362438446"  # +90 536 243 84 46
    test_message = "deneme"
    
    print(f"Gönderilecek numara: {test_phone}")
    print(f"Gönderilecek mesaj: {test_message}")
    print()
    
    # API isteği
    url = f"https://graph.facebook.com/v24.0/{whatsapp_ayar.PhoneNumberID}/messages"
    headers = {
        "Authorization": f"Bearer {whatsapp_ayar.AccessToken}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "to": test_phone,
        "type": "text",
        "text": {"body": test_message}
    }
    
    print("API isteği gönderiliyor...")
    print(f"URL: {url}")
    print(f"Data: {json.dumps(data, indent=2)}")
    print()
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"Yanıt Kodu: {response.status_code}")
        print(f"Yanıt: {response.text}")
        print()
        
        if response.status_code == 200:
            result = response.json()
            print("✅ BAŞARILI! Mesaj gönderildi.")
            print(f"Mesaj ID: {result.get('messages', [{}])[0].get('id', 'Bilinmiyor')}")
        else:
            error_data = response.json()
            error_code = error_data.get('error', {}).get('code', 'Bilinmiyor')
            error_message = error_data.get('error', {}).get('message', 'Bilinmeyen hata')
            print(f"❌ HATA! (Kod: {error_code})")
            print(f"Hata mesajı: {error_message}")
            
            if error_code == 133010:
                print()
                print("💡 Çözüm önerileri:")
                print("1. Meta Business Suite'te numarayı contacts'a eklediğinizden emin olun")
                print("2. Test numarasından kendi numaranıza bir mesaj gönderin")
                print("3. 24 saat içinde o numaraya mesaj gönderebilirsiniz")
                print("4. Veya gerçek bir WhatsApp Business numarası kullanın")
                
    except Exception as e:
        print(f"❌ İstek hatası: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)

