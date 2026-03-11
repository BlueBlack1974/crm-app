"""
MySQL şifresini göster (SistemAyarlar tablosundan)
"""
import os
import sys
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Flask uygulamasını import et
from app import app, db, SistemAyar, decrypt_password

def show_mysql_password():
    """MySQL şifresini göster"""
    with app.app_context():
        try:
            # MySQL ayarlarını al
            mysql_password_setting = SistemAyar.query.filter_by(AyarAdi='database_mysql_password').first()
            
            if not mysql_password_setting or not mysql_password_setting.AyarDegeri:
                print("[HATA] MySQL sifresi SistemAyarlar'da bulunamadi!")
                print("\n[BILGI] Sifreyi ayarlamak icin:")
                print("   1. Uygulamaya giris yapin")
                print("   2. Ayarlar > Veritabani Ayarlari sayfasina gidin")
                print("   3. MySQL ayarlarini girin ve kaydedin")
                return
            
            # Şifreyi deşifrele
            encrypted_password = mysql_password_setting.AyarDegeri
            decrypted_password = decrypt_password(encrypted_password)
            
            # Diğer MySQL ayarlarını da göster
            mysql_host = SistemAyar.query.filter_by(AyarAdi='database_mysql_host').first()
            mysql_port = SistemAyar.query.filter_by(AyarAdi='database_mysql_port').first()
            mysql_database = SistemAyar.query.filter_by(AyarAdi='database_mysql_database').first()
            mysql_username = SistemAyar.query.filter_by(AyarAdi='database_mysql_username').first()
            
            print("=" * 60)
            print("MySQL Bağlantı Bilgileri")
            print("=" * 60)
            print(f"Sunucu:     {mysql_host.AyarDegeri if mysql_host else 'BULUNAMADI'}")
            print(f"Port:       {mysql_port.AyarDegeri if mysql_port else '3306 (varsayılan)'}")
            print(f"Veritabanı: {mysql_database.AyarDegeri if mysql_database else 'BULUNAMADI'}")
            print(f"Kullanıcı:  {mysql_username.AyarDegeri if mysql_username else 'BULUNAMADI'}")
            print(f"Şifre:      {decrypted_password}")
            print("=" * 60)
            
            # Bağlantı string'i oluştur
            if all([mysql_host, mysql_database, mysql_username]):
                host = mysql_host.AyarDegeri
                port = mysql_port.AyarDegeri if mysql_port and mysql_port.AyarDegeri else '3306'
                database = mysql_database.AyarDegeri
                username = mysql_username.AyarDegeri
                
                print("\n[BAGLANTI] Baglanti String'i:")
                print(f"mysql+pymysql://{username}:{decrypted_password}@{host}:{port}/{database}?charset=utf8mb4")
            
        except Exception as e:
            print(f"[HATA] Hata: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    show_mysql_password()

