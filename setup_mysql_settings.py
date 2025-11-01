#!/usr/bin/env python3
"""
MySQL ayarlarını SistemAyarlar tablosuna kaydetme
"""

from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

# MySQL bağlantı bilgileri
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'Sa19977991'
MYSQL_DATABASE = 'Crandyx_CRM_DB'
MYSQL_CHARSET = 'utf8mb4'

# İlk bağlantı için .env'den (MSSQL olabilir) veya direkt MySQL
# Önce MySQL'e bağlanıp SistemAyarlar'a kayıt yapacağız
FIRST_CONNECTION_STRING = f"mysql+pymysql://{quote_plus(MYSQL_USER)}:{quote_plus(MYSQL_PASSWORD)}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"

# Şifreleme için (app.py'den aynı mantık)
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-.env')

def get_encryption_key(secret_key):
    """SECRET_KEY'den encryption key oluştur"""
    password = secret_key.encode()
    salt = password[:16] if len(password) >= 16 else password + b'0' * (16 - len(password))
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key

def encrypt_password(password, secret_key):
    """Şifreyi şifrele"""
    if not password:
        return ''
    try:
        key = get_encryption_key(secret_key)
        fernet = Fernet(key)
        encrypted = fernet.encrypt(password.encode())
        return encrypted.decode()
    except Exception as e:
        print(f"[ERROR] Sifre sifreleme hatasi: {e}")
        return password

def setup_mysql_settings():
    """MySQL ayarlarını SistemAyarlar tablosuna kaydet"""
    
    print("=" * 60)
    print("MySQL Ayarlarini SistemAyarlar'a Kaydetme")
    print("=" * 60)
    
    try:
        engine = create_engine(FIRST_CONNECTION_STRING, pool_pre_ping=True)
        
        with engine.connect() as conn:
            # SistemAyarlar tablosunu kontrol et
            print("\n[1/3] SistemAyarlar tablosu kontrol ediliyor...")
            result = conn.execute(text("SHOW TABLES LIKE 'SistemAyarlar'"))
            if not result.fetchone():
                print("[HATA] SistemAyarlar tablosu bulunamadi!")
                return False
            
            print("[OK] SistemAyarlar tablosu mevcut")
            
            # MySQL şifresini şifrele
            print("\n[2/3] Sifre sifreleniyor...")
            encrypted_password = encrypt_password(MYSQL_PASSWORD, SECRET_KEY)
            print(f"[OK] Sifre sifrelendi (uzunluk: {len(encrypted_password)})")
            
            # Ayarları kaydet
            print("\n[3/3] MySQL ayarlari kaydediliyor...")
            with conn.begin():
                settings = [
                    ('database_type', 'mysql', 'Veritabanı tipi (mysql)'),
                    ('database_mysql_host', MYSQL_HOST, 'MySQL sunucu adresi'),
                    ('database_mysql_port', str(MYSQL_PORT), 'MySQL port numarası'),
                    ('database_mysql_database', MYSQL_DATABASE, 'MySQL veritabanı adı'),
                    ('database_mysql_username', MYSQL_USER, 'MySQL kullanıcı adı'),
                    ('database_mysql_password', encrypted_password, 'MySQL şifresi (şifrelenmiş)'),
                    ('database_mysql_charset', MYSQL_CHARSET, 'MySQL charset'),
                ]
                
                for ayar_adi, deger, aciklama in settings:
                    # Mevcut ayarı kontrol et
                    check_result = conn.execute(
                        text("SELECT AyarID FROM SistemAyarlar WHERE AyarAdi = :ayar_adi"),
                        {'ayar_adi': ayar_adi}
                    )
                    existing = check_result.fetchone()
                    
                    if existing:
                        # Güncelle
                        conn.execute(
                            text("""
                                UPDATE SistemAyarlar 
                                SET AyarDegeri = :deger, Aciklama = :aciklama,
                                    GuncellemeTarihi = CURRENT_TIMESTAMP
                                WHERE AyarAdi = :ayar_adi
                            """),
                            {'deger': deger, 'aciklama': aciklama, 'ayar_adi': ayar_adi}
                        )
                        print(f"  [GUNCELLENDI] {ayar_adi}")
                    else:
                        # Yeni ekle
                        conn.execute(
                            text("""
                                INSERT INTO SistemAyarlar (AyarAdi, AyarDegeri, Aciklama, GuncellemeTarihi)
                                VALUES (:ayar_adi, :deger, :aciklama, CURRENT_TIMESTAMP)
                            """),
                            {'ayar_adi': ayar_adi, 'deger': deger, 'aciklama': aciklama}
                        )
                        print(f"  [EKLEDI] {ayar_adi}")
            
            print("\n[OK] Tum MySQL ayarlari kaydedildi!")
            
            # Kontrol et
            print("\n[KONTROL] Kaydedilen ayarlar:")
            result = conn.execute(
                text("SELECT AyarAdi, AyarDegeri, Aciklama FROM SistemAyarlar WHERE AyarAdi LIKE 'database_mysql%' OR AyarAdi = 'database_type'")
            )
            for row in result.fetchall():
                ayar_adi, deger, aciklama = row
                if 'password' in ayar_adi.lower():
                    print(f"  {ayar_adi}: [SIFRELENMIS - {len(deger)} karakter]")
                else:
                    print(f"  {ayar_adi}: {deger}")
            
            print("\n" + "=" * 60)
            print("[BASARILI] MySQL ayarlari SistemAyarlar'a kaydedildi!")
            print("=" * 60)
            print("\nSonraki adimlar:")
            print("1. Uygulamayi yeniden baslatin")
            print("2. http://localhost:5000 adresine gidin")
            print("3. admin/admin123 ile giris yapin")
            print("4. Ayarlar > Veritabani Ayarlari sayfasinda MySQL ayarlarini kontrol edin")
            
            return True
            
    except Exception as e:
        print(f"\n[HATA] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_mysql_settings()

