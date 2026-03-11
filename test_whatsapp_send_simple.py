"""
WhatsApp mesaj gönderme test scripti - Basit versiyon
"""
import requests
import json

# WhatsApp ayarları (veritabanından alın veya buraya yazın)
PHONE_NUMBER_ID = "961201477065970"
ACCESS_TOKEN = "EAAKxU2froBUBQBKz5SrgKcVrZCtToSFYqT8MofaDEv2g9tALWZBxc4JWHWMiaY6UZAtAN42YYG6CADljva24q4VJgdrnz8UAiNb0JOJdBx3AV8jZAMeCfXCW54qnkx5YuScDP62jTWRPP2pq6lAlW4ay0bc9G8MgANs3PBu7NEjZB709R20U9uLMkbzXrwpm6JmkOE3MaNl4fceGooFDEDi7gk1g7Wy6d5ZBXEmoqk"

# Test numarası ve mesaj
TEST_PHONE = "905362438446"  # +90 536 243 84 46
TEST_MESSAGE = "deneme"

print("=" * 60)
print("WhatsApp Mesaj Gönderme Testi")
print("=" * 60)
print(f"Phone Number ID: {PHONE_NUMBER_ID}")
print(f"Gönderilecek numara: {TEST_PHONE}")
print(f"Gönderilecek mesaj: {TEST_MESSAGE}")
print()

# API isteği
url = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

data = {
    "messaging_product": "whatsapp",
    "to": TEST_PHONE,
    "type": "text",
    "text": {"body": TEST_MESSAGE}
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

