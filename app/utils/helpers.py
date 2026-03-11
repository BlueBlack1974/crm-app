from flask import request

def get_client_ip():
    """Gerçek client IP adresini al (proxy arkasında çalışırken)"""
    # X-Forwarded-For header'ını kontrol et (proxy arkasında)
    x_forwarded = request.headers.get('X-Forwarded-For')
    if x_forwarded:
        ip = x_forwarded.split(',')[0].strip()
        return format_ip_for_display(ip)
    
    x_real_ip = request.headers.get('X-Real-IP')
    if x_real_ip:
        return format_ip_for_display(x_real_ip)
    
    remote_addr = request.remote_addr
    if remote_addr == '127.0.0.1':
        return "192.168.1.11"
    
    if ':' in remote_addr and len(remote_addr) > 20:
        return "192.168.1.106"
    
    return format_ip_for_display(remote_addr)

def format_ip_for_display(ip):
    """IP adresini loglama için uygun formata çevir"""
    if not ip:
        return "Unknown"
    
    if ':' in ip and len(ip) > 20:
        parts = ip.split(':')
        if len(parts) >= 8:
            first_part = ':'.join(parts[:2])
            last_part = ':'.join(parts[-2:])
            return f"{first_part}...{last_part}"
        else:
            return f"{parts[0]}...{parts[-1]}"
    
    return ip

def send_password_reset_email(recipient_email, reset_link, firma_id):
    """Firmaya ozel SMTP ayarlari uzerinden sifre sifirlama maili arka planda gonderir.
    E-posta gonderimi bir daemon thread'de calistirilir; kullaniciya aninda cevap doner.
    """
    import threading
    from app.models import FirmaEmailAyar

    # SMTP ayarlarini kontrol et (hizli, ana thread'de)
    email_settings = FirmaEmailAyar.query.filter_by(FirmaID=firma_id).first()
    if not email_settings:
        print(f"[WARN] FirmaID {firma_id} icin SMTP ayari yok. FirmaID=1 deneniyor...")
        email_settings = FirmaEmailAyar.query.filter_by(FirmaID=1).first()
        if not email_settings:
            return False, "E-Posta ayarlarınız sistemde bulunamadı. Lütfen yönetici panelinden kaydedin."

    # Ayarlari yerel degiskenlere kopyala (thread guvenli)
    smtp_server = email_settings.SMTP_Sunucu
    smtp_port   = email_settings.SMTP_Port
    ssl_aktif   = email_settings.SSL_Kullan
    kullanici   = email_settings.KullaniciAdi
    sifre       = email_settings.Sifre

    def _send():
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        try:
            msg = MIMEMultipart()
            msg['From']    = f"Crandyx CRM <{kullanici}>"
            msg['To']      = recipient_email
            msg['Subject'] = "Şifre Sıfırlama İsteği - Crandyx CRM"

            html_content = f"""
            <html>
              <body style="font-family: Arial, sans-serif; background-color: #f4f7f6; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; padding: 40px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                  <h2 style="color: #0d6efd; text-align: center;">Şifre Sıfırlama İsteğiniz Alındı</h2>
                  <p style="color: #555; font-size: 16px; line-height: 1.5;">Merhaba,</p>
                  <p style="color: #555; font-size: 16px; line-height: 1.5;">Crandyx CRM hesabınızın şifresini sıfırlamak için bir istekte bulundunuz. Eğer bu işlemi siz yapmadıysanız lütfen bu e-postayı dikkate almayın.</p>
                  <div style="text-align: center; margin: 30px 0;">
                      <a href="{reset_link}" style="background-color: #0d6efd; color: white; text-decoration: none; padding: 12px 25px; border-radius: 5px; font-weight: bold; display: inline-block;">Şifremi Sıfırla</a>
                  </div>
                  <p style="color: #999; font-size: 13px; text-align: center; margin-top: 40px;">Bu bağlantının süresi 1 saat içinde dolacaktır.</p>
                </div>
              </body>
            </html>
            """
            msg.attach(MIMEText(html_content, 'html'))

            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            if ssl_aktif:
                server.starttls()
            server.login(kullanici, sifre)
            server.send_message(msg)
            server.quit()
            print(f"[OK] Sifre sifirlama emaili {recipient_email} adresine gonderildi.")
        except Exception as e:
            error_info = str(e)
            if "535" in error_info or "Authentication" in error_info:
                error_info = "E-Posta şifresi yanlış veya Uygulama Şifresi hatalı (SMTP 535)."
            elif "111" in error_info or "Connection refused" in error_info:
                error_info = "Mail sunucusuna bağlantı reddedildi (Port veya TLS kapalı)."
            print(f"[ERROR] Email gonderme basarisiz (arka plan thread): {error_info}")

    t = threading.Thread(target=_send, daemon=True)
    t.start()
    # Kullaniciya aninda "Basarili" dondur; gonderim arka planda devam eder.
    return True, "Başarılı"
