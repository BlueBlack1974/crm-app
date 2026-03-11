"""
WhatsApp Business Phone Number ID'lerini bulma scripti
"""
import requests
import json

# WhatsApp ayarları
ACCESS_TOKEN = "EAAKxU2froBUBQBKz5SrgKcVrZCtToSFYqT8MofaDEv2g9tALWZBxc4JWHWMiaY6UZAtAN42YYG6CADljva24q4VJgdrnz8UAiNb0JOJdBx3AV8jZAMeCfXCW54qnkx5YuScDP62jTWRPP2pq6lAlW4ay0bc9G8MgANs3PBu7NEjZB709R20U9uLMkbzXrwpm6JmkOE3MaNl4fceGooFDEDi7gk1g7Wy6d5ZBXEmoqk"
BUSINESS_ACCOUNT_ID = "747593844354497"  # Business Account ID
CURRENT_PHONE_NUMBER_ID = "961201477065970"  # Mevcut Phone Number ID

print("=" * 60)
print("WhatsApp Business Phone Number ID'lerini Bulma")
print("=" * 60)
print(f"Business Account ID: {BUSINESS_ACCOUNT_ID}")
print(f"Mevcut Phone Number ID: {CURRENT_PHONE_NUMBER_ID}")
print()

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# 1. Business Account'tan phone number'ları listele
print("1. Business Account'tan phone number'ları listeleniyor...")
url = f"https://graph.facebook.com/v24.0/{BUSINESS_ACCOUNT_ID}/phone_numbers"
print(f"URL: {url}")
print()

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Yanıt Kodu: {response.status_code}")
    print(f"Yanıt: {response.text}")
    print()
    
    if response.status_code == 200:
        data = response.json()
        phone_numbers = data.get('data', [])
        
        if phone_numbers:
            print(f"✅ {len(phone_numbers)} phone number bulundu:")
            print()
            for i, phone in enumerate(phone_numbers, 1):
                print(f"{i}. Phone Number ID: {phone.get('id', 'N/A')}")
                print(f"   Display Phone Number: {phone.get('display_phone_number', 'N/A')}")
                print(f"   Verified Name: {phone.get('verified_name', 'N/A')}")
                print(f"   Quality Rating: {phone.get('quality_rating', 'N/A')}")
                print(f"   Code Verification Status: {phone.get('code_verification_status', 'N/A')}")
                print()
        else:
            print("⚠️ Phone number bulunamadı")
    else:
        error_data = response.json()
        error_code = error_data.get('error', {}).get('code', 'Bilinmiyor')
        error_message = error_data.get('error', {}).get('message', 'Bilinmeyen hata')
        print(f"❌ HATA! (Kod: {error_code})")
        print(f"Hata mesajı: {error_message}")
        
except Exception as e:
    print(f"❌ İstek hatası: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)

# 2. Mevcut Phone Number ID'nin detaylarını al
print("2. Mevcut Phone Number ID'nin detayları...")
url = f"https://graph.facebook.com/v24.0/{CURRENT_PHONE_NUMBER_ID}"
print(f"URL: {url}")
print()

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Yanıt Kodu: {response.status_code}")
    
    if response.status_code == 200:
        phone_data = response.json()
        print("✅ Phone Number Detayları:")
        print(json.dumps(phone_data, indent=2, ensure_ascii=False))
    else:
        print(f"Yanıt: {response.text}")
        
except Exception as e:
    print(f"❌ İstek hatası: {e}")

print()
print("=" * 60)

# 3. WhatsApp Business Account bilgilerini al
print("3. WhatsApp Business Account bilgileri...")
url = f"https://graph.facebook.com/v24.0/{BUSINESS_ACCOUNT_ID}"
print(f"URL: {url}")
print()

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Yanıt Kodu: {response.status_code}")
    
    if response.status_code == 200:
        account_data = response.json()
        print("✅ Business Account Detayları:")
        print(json.dumps(account_data, indent=2, ensure_ascii=False))
    else:
        print(f"Yanıt: {response.text}")
        
except Exception as e:
    print(f"❌ İstek hatası: {e}")

print()
print("=" * 60)

