import smtplib
import ssl
from email.mime.text import MIMEText
from flask import current_app
from app.models import FirmaEmailAyar

def send_email_simple(to_email: str, subject: str, body: str) -> bool:
    host = current_app.config['SMTP_HOST']
    user = current_app.config['SMTP_USER']
    password = current_app.config['SMTP_PASS']
    port = current_app.config['SMTP_PORT']
    use_tls = current_app.config['SMTP_USE_TLS']
    from_email = current_app.config['FROM_EMAIL'] or user

    if not host or not user or not password or not to_email:
        return False

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    try:
        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port) as server:
                server.starttls(context=context)
                server.login(user, password)
                server.sendmail(from_email, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                server.login(user, password)
                server.sendmail(from_email, [to_email], msg.as_string())
        return True
    except Exception as e:
        # Sadece debug modunda hata mesajı yazdır
        if current_app.debug:
            print(f"E-posta gönderilemedi: {e}")
        return False

def send_email_with_firma_settings(firma_id: int, to_email: str, subject: str, body: str, from_name: str = None) -> bool:
    """Firma ayarlarını kullanarak e-posta gönder"""
    try:
        # Firma e-posta ayarlarını al
        email_ayar = FirmaEmailAyar.query.filter_by(FirmaID=firma_id, Aktif=True).first()
        
        if not email_ayar:
            # Sadece debug modunda hata mesajı yazdır
            if current_app.debug:
                print(f"Firma {firma_id} için aktif e-posta ayarı bulunamadı")
            return False
        
        # Gönderen bilgilerini ayarla
        from_email = email_ayar.VarsayilanGonderenEmail or email_ayar.KullaniciAdi
        from_name = from_name or email_ayar.VarsayilanGonderenAdi or "CRM Sistemi"
        
        # E-posta mesajını oluştur
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{from_email}>"
        msg['To'] = to_email
        
        # SMTP bağlantısı ve gönderim
        if email_ayar.SSL_Kullan:
            context = ssl.create_default_context()
            with smtplib.SMTP(email_ayar.SMTP_Sunucu, email_ayar.SMTP_Port) as server:
                server.starttls(context=context)
                server.login(email_ayar.KullaniciAdi, email_ayar.Sifre)
                server.sendmail(from_email, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(email_ayar.SMTP_Sunucu, email_ayar.SMTP_Port) as server:
                server.login(email_ayar.KullaniciAdi, email_ayar.Sifre)
                server.sendmail(from_email, [to_email], msg.as_string())
        
        # Sadece debug modunda başarı mesajı yazdır
        if current_app.debug:
            print(f"E-posta başarıyla gönderildi: {to_email}")
        return True
        
    except Exception as e:
        # Sadece debug modunda hata mesajı yazdır
        if current_app.debug:
            print(f"E-posta gönderilemedi (firma ayarları): {e}")
        return False
