from app.models import FirmaSMSAyar

def send_sms_with_firma_settings(firma_id: int, phone_number: str, message: str) -> bool:
    """Firma ayarlarını kullanarak SMS gönder"""
    try:
        # Firma SMS ayarlarını al
        sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=firma_id, Aktif=True).first()
        
        if not sms_ayar:
            print(f"Firma {firma_id} için aktif SMS ayarı bulunamadı")
            return False
        
        # Telefon numarası normalizasyonu: çoğu sağlayıcı için 90XXXXXXXXXX
        # Corvass için esnek format gerekir; orijinali ayrıca iletelim
        original_phone_input = phone_number
        phone_number = ''.join(filter(str.isdigit, phone_number))
        if not phone_number.startswith('90'):
            phone_number = '90' + phone_number
        
        # SMS firmasına göre gönderim
        if sms_ayar.SMSFirmasi == 'netgsm':
            return send_sms_netgsm(sms_ayar, phone_number, message)
        elif sms_ayar.SMSFirmasi == 'iletimerkezi':
            return send_sms_iletimerkezi(sms_ayar, phone_number, message)
        elif sms_ayar.SMSFirmasi == 'mesajnet':
            return send_sms_mesajnet(sms_ayar, phone_number, message)
        elif sms_ayar.SMSFirmasi == 'corvass':
            return send_sms_corvass(sms_ayar, original_phone_input, message)
        elif sms_ayar.SMSFirmasi == 'custom':
            return send_sms_custom(sms_ayar, phone_number, message)
        else:
            print(f"Desteklenmeyen SMS firması: {sms_ayar.SMSFirmasi}")
            return False
            
    except Exception as e:
        print(f"SMS gönderilemedi (firma ayarları): {e}")
        return False

def send_sms_netgsm(sms_ayar, phone_number: str, message: str) -> bool:
    """NetGSM API ile SMS gönder"""
    try:
        import requests
        
        url = "https://api.netgsm.com.tr/sms/send/get"
        params = {
            'usercode': sms_ayar.KullaniciAdi,
            'password': sms_ayar.Sifre,
            'gsmno': phone_number,
            'message': message,
            'msgheader': sms_ayar.GondericiAdi or 'CRM'
        }
        
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            result = response.text.strip()
            if result.startswith('00'):
                print(f"NetGSM SMS başarıyla gönderildi: {phone_number}")
                return True
            else:
                print(f"NetGSM SMS hatası: {result}")
                return False
        else:
            print(f"NetGSM API hatası: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"NetGSM SMS gönderim hatası: {e}")
        return False

def send_sms_iletimerkezi(sms_ayar, phone_number: str, message: str) -> bool:
    """İleti Merkezi API ile SMS gönder"""
    try:
        import requests
        
        url = "https://api.iletimerkezi.com/v1/send-sms"
        headers = {
            'Authorization': f'Bearer {sms_ayar.API_Key}',
            'Content-Type': 'application/json'
        }
        data = {
            'recipients': [phone_number],
            'message': message,
            'sender': sms_ayar.GondericiAdi or 'CRM'
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print(f"İleti Merkezi SMS başarıyla gönderildi: {phone_number}")
                return True
            else:
                print(f"İleti Merkezi SMS hatası: {result}")
                return False
        else:
            print(f"İleti Merkezi API hatası: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"İleti Merkezi SMS gönderim hatası: {e}")
        return False

def send_sms_mesajnet(sms_ayar, phone_number: str, message: str) -> bool:
    """MesajNet API ile SMS gönder"""
    try:
        import requests
        
        url = "https://api.mesajnet.com/sms/send"
        data = {
            'username': sms_ayar.KullaniciAdi,
            'password': sms_ayar.Sifre,
            'number': phone_number,
            'message': message,
            'sender': sms_ayar.GondericiAdi or 'CRM'
        }
        
        response = requests.post(url, data=data, timeout=30)
        if response.status_code == 200:
            result = response.text.strip()
            if 'success' in result.lower() or 'ok' in result.lower():
                print(f"MesajNet SMS başarıyla gönderildi: {phone_number}")
                return True
            else:
                print(f"MesajNet SMS hatası: {result}")
                return False
        else:
            print(f"MesajNet API hatası: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"MesajNet SMS gönderim hatası: {e}")
        return False

def send_sms_corvass(sms_ayar, phone_number: str, message: str) -> bool:
    """Corvass API ile SMS gönder"""
    try:
        import requests
        import json
        
        url = sms_ayar.API_URL or "https://api.corvass.net/v1/sms/send"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {sms_ayar.API_Key}'
        }
        
        data = {
            'to': phone_number,
            'message': message,
            'from': sms_ayar.GondericiAdi or 'CRM'
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            print(f"Corvass SMS başarıyla gönderildi: {phone_number}")
            return True
        else:
            print(f"Corvass API hatası: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Corvass SMS gönderim hatası: {e}")
        return False

def send_sms_custom(sms_ayar, phone_number: str, message: str) -> bool:
    """Özel API ile SMS gönder (Generic Implementation)"""
    try:
        import requests
        
        if not sms_ayar.API_URL:
            print("Custom SMS için API URL tanımlı değil")
            return False
            
        # Basit GET isteği örneği - Özelleştirilebilir
        params = {
            'user': sms_ayar.KullaniciAdi,
            'pass': sms_ayar.Sifre,
            'to': phone_number,
            'msg': message,
            'header': sms_ayar.GondericiAdi
        }
        
        response = requests.get(sms_ayar.API_URL, params=params, timeout=30)
        if response.status_code == 200:
            print(f"Custom SMS başarıyla gönderildi: {phone_number}")
            return True
        else:
            print(f"Custom API hatası: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Custom SMS gönderim hatası: {e}")
        return False
