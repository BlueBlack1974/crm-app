"""
Crandyx CRM - Ana Dosya
Randevu Defteri ve Kullanici Yonetimi
"""

# Python 3.13 timezone fix
import os
os.environ.setdefault('PYTHONTZPATH', '')

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel, gettext, ngettext, get_locale
from flask_wtf.csrf import CSRFProtect
_ = gettext
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, time
import os
import secrets
from dotenv import load_dotenv
from functools import wraps
import smtplib
import ssl
from email.mime.text import MIMEText
import threading
import queue
import json
import time
from collections import Counter, defaultdict
from io import BytesIO, StringIO
import csv
from sqlalchemy import or_, and_, create_engine, text
from urllib.parse import quote_plus
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd
from werkzeug.utils import secure_filename
import re
import tempfile
import warnings

load_dotenv()
app = Flask(__name__)
# SECRET_KEY - Production'da mutlaka .env dosyasında güçlü bir değer kullanılmalı
default_secret_key = 'change-this-in-.env'
secret_key = os.environ.get('SECRET_KEY', default_secret_key)

# Production ortamında varsayılan SECRET_KEY kullanılıyorsa uyar
if secret_key == default_secret_key and not os.environ.get('FLASK_DEBUG', '').lower() == 'true':
    warnings.warn(
        "SECURITY WARNING: SECRET_KEY için varsayılan değer kullanılıyor! "
        "Production ortamında güçlü bir SECRET_KEY tanımlayın.",
        UserWarning
    )

app.config['SECRET_KEY'] = secret_key

# CSRF Protection
csrf = CSRFProtect(app)

# CSRF token'ı JSON istekler için header'dan da oku
# Flask-WTF varsayılan olarak X-CSRFToken header'ını destekler

# Şifreleme için key oluştur (SECRET_KEY'den türet)
def get_encryption_key():
    """SECRET_KEY'den encryption key oluştur"""
    secret_key = app.config['SECRET_KEY']
    # SECRET_KEY'i bytes'a çevir
    password = secret_key.encode()
    # Salt oluştur (SECRET_KEY'in ilk 16 byte'ı)
    salt = password[:16] if len(password) >= 16 else password + b'0' * (16 - len(password))
    # PBKDF2 ile key türet
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key

# Encryption/Decryption fonksiyonları
def encrypt_password(password):
    """Şifreyi şifrele"""
    if not password:
        return ''
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(password.encode())
        # Fernet token'ını direkt döndür (zaten base64 encoded string)
        return encrypted.decode()
    except Exception as e:
        print(f"[ERROR] Şifre şifreleme hatası: {e}")
        return password  # Hata durumunda plaintext döndür

def decrypt_password(encrypted_password):
    """Şifreyi deşifrele"""
    if not encrypted_password:
        return ''
    try:
        # Önce şifrelenmiş mi kontrol et (gAAAAA ile başlayan Fernet token'ı)
        if encrypted_password.startswith('gAAAAA'):
            # Şifrelenmiş, deşifrele
            key = get_encryption_key()
            fernet = Fernet(key)
            # Fernet token'ını direkt decrypt et
            decrypted = fernet.decrypt(encrypted_password.encode())
            return decrypted.decode()
        else:
            # Eski plaintext şifre, direkt döndür (backward compatibility)
            return encrypted_password
    except Exception as e:
        # Deşifreleme başarısızsa, muhtemelen plaintext şifre
        print(f"[WARN] Şifre deşifreleme hatası (muhtemelen plaintext): {e}")
        return encrypted_password  # Plaintext olarak döndür

# Allow override via env; fallback to provided local credentials
_db_uri = os.environ.get('DATABASE_URL')
if not _db_uri:
    raise RuntimeError('DATABASE_URL is not set in environment (.env). Please define the SQLAlchemy URI.')
# TrustServerCertificate parametresini ekle (yoksa)
if 'TrustServerCertificate' not in _db_uri and 'trustservercertificate' not in _db_uri.lower():
    separator = '&' if '?' in _db_uri else '?'
    _db_uri = f"{_db_uri}{separator}TrustServerCertificate=yes"
app.config['SQLALCHEMY_DATABASE_URI'] = _db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# SMTP/E-posta ayarlari (env ile override edilebilir)
app.config['SMTP_HOST'] = os.environ.get('SMTP_HOST', '')
app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT', '587'))
app.config['SMTP_USER'] = os.environ.get('SMTP_USER', '')
app.config['SMTP_PASS'] = os.environ.get('SMTP_PASS', '')
app.config['SMTP_USE_TLS'] = os.environ.get('SMTP_USE_TLS', '1') == '1'
app.config['FROM_EMAIL'] = os.environ.get('FROM_EMAIL', app.config['SMTP_USER'])

# Veritabanı bağlantı yardımcı fonksiyonları
def build_mssql_uri(server, database, username, password, port=1433, driver='ODBC Driver 17 for SQL Server'):
    """MSSQL için bağlantı string'i oluştur"""
    # pyodbc için özel karakterleri encode et
    password_encoded = quote_plus(password) if password else ''
    username_encoded = quote_plus(username) if username else ''
    driver_encoded = quote_plus(driver)  # Driver adındaki boşlukları encode et
    return f"mssql+pyodbc://{username_encoded}:{password_encoded}@{server}:{port}/{database}?driver={driver_encoded}&TrustServerCertificate=yes"

def build_mysql_uri(server, database, username, password, port=3306, charset='utf8mb4'):
    """MySQL için bağlantı string'i oluştur"""
    password_encoded = quote_plus(password) if password else ''
    username_encoded = quote_plus(username) if username else ''
    return f"mysql+pymysql://{username_encoded}:{password_encoded}@{server}:{port}/{database}?charset={charset}"

def get_database_uri_from_settings(debug=True):
    """SistemAyarlar tablosundan veritabanı bağlantı bilgilerini al ve URI oluştur"""
    try:
        # Önce .env'den varsayılan bağlantı ile tabloya eriş
        if debug:
            print("[CHECK] SistemAyarlar tablosundan veritabani ayarlari okunuyor...")
        # SistemAyarlar tablosunun var olup olmadığını kontrol et
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()
            if debug:
                print(f"   [INFO] Mevcut tablolar: {', '.join(table_names)}")
            if 'SistemAyarlar' not in table_names:
                if debug:
                    print("   [WARN] SistemAyarlar tablosu bulunamadi!")
                return None
        except Exception as inspect_err:
            if debug:
                print(f"   [WARN] Tablo kontrolu sirasinda hata: {inspect_err}")
            return None
        
        db_type_setting = SistemAyar.query.filter_by(AyarAdi='database_type').first()
        if debug:
            print(f"   database_type ayarı: {db_type_setting.AyarDegeri if db_type_setting else 'BULUNAMADI'}")
        if not db_type_setting or not db_type_setting.AyarDegeri:
            if debug:
                print("   [WARN] database_type ayari bulunamadi veya bos!")
                # Tüm SistemAyarlar kayıtlarını listele (debug için)
                all_settings = SistemAyar.query.all()
                print(f"   [INFO] SistemAyarlar'da toplam {len(all_settings)} kayit var:")
                for setting in all_settings:
                    print(f"      - {setting.AyarAdi} = {setting.AyarDegeri[:50] if setting.AyarDegeri and len(setting.AyarDegeri) > 50 else (setting.AyarDegeri or 'NULL')}")
            return None
        
        db_type = db_type_setting.AyarDegeri.strip().lower()
        if debug:
            print(f"   [INFO] Veritabani tipi: {db_type}")
        
        if db_type == 'mysql':
            # MySQL ayarlarını al
            server_setting = SistemAyar.query.filter_by(AyarAdi='database_mysql_host').first()
            port_setting = SistemAyar.query.filter_by(AyarAdi='database_mysql_port').first()
            database_setting = SistemAyar.query.filter_by(AyarAdi='database_mysql_database').first()
            username_setting = SistemAyar.query.filter_by(AyarAdi='database_mysql_username').first()
            password_setting = SistemAyar.query.filter_by(AyarAdi='database_mysql_password').first()
            
            if not all([server_setting, database_setting, username_setting]):
                return None
            
            server = server_setting.AyarDegeri or 'localhost'
            port = int(port_setting.AyarDegeri) if port_setting and port_setting.AyarDegeri else 3306
            database = database_setting.AyarDegeri
            username = username_setting.AyarDegeri
            password_encrypted = password_setting.AyarDegeri if password_setting else ''
            password = decrypt_password(password_encrypted)  # Şifreyi deşifrele
            charset_setting = SistemAyar.query.filter_by(AyarAdi='database_mysql_charset').first()
            charset = charset_setting.AyarDegeri if charset_setting and charset_setting.AyarDegeri else 'utf8mb4'
            
            return build_mysql_uri(server, database, username, password, port, charset)
        
        elif db_type == 'mssql':
            # MSSQL ayarlarını al
            server_setting = SistemAyar.query.filter_by(AyarAdi='database_mssql_server').first()
            port_setting = SistemAyar.query.filter_by(AyarAdi='database_mssql_port').first()
            database_setting = SistemAyar.query.filter_by(AyarAdi='database_mssql_database').first()
            username_setting = SistemAyar.query.filter_by(AyarAdi='database_mssql_username').first()
            password_setting = SistemAyar.query.filter_by(AyarAdi='database_mssql_password').first()
            driver_setting = SistemAyar.query.filter_by(AyarAdi='database_mssql_driver').first()
            
            if debug:
                print(f"   [CHECK] MSSQL ayarlari kontrol ediliyor...")
                print(f"      server: {server_setting.AyarDegeri if server_setting else 'BULUNAMADI'}")
                print(f"      database: {database_setting.AyarDegeri if database_setting else 'BULUNAMADI'}")
                print(f"      username: {username_setting.AyarDegeri if username_setting else 'BULUNAMADI'}")
                print(f"      password: {'***' if password_setting and password_setting.AyarDegeri else 'BULUNAMADI/YOK'}")
            
            if not all([server_setting, database_setting, username_setting]):
                if debug:
                    print("   [ERROR] Eksik MSSQL ayarlari! (server, database veya username eksik)")
                return None
            
            server = server_setting.AyarDegeri or 'localhost'
            port = int(port_setting.AyarDegeri) if port_setting and port_setting.AyarDegeri else 1433
            database = database_setting.AyarDegeri
            username = username_setting.AyarDegeri
            password_encrypted = password_setting.AyarDegeri if password_setting else ''
            password = decrypt_password(password_encrypted)  # Şifreyi deşifrele
            driver = driver_setting.AyarDegeri if driver_setting and driver_setting.AyarDegeri else 'ODBC Driver 17 for SQL Server'
            
            if debug:
                print(f"   [OK] MSSQL URI olusturuluyor: {server}:{port}/{database}")
            return build_mssql_uri(server, database, username, password, port, driver)
        
        return None
    except Exception as e:
        print(f"Veritabanı ayarları okunamadı: {e}")
        return None

def export_settings_to_env(db_type=None):
    """SistemAyarlar'dan ayarları .env dosyasına kaydet
    
    Args:
        db_type: Veritabanı tipi ('mysql' veya 'mssql'). 
                 Eğer None ise SistemAyarlar'dan 'database_type' ayarını okur.
    """
    try:
        # SistemAyarlar'dan database_type ayarını oku (eğer db_type parametresi verilmemişse)
        if db_type is None:
            db_type_setting = SistemAyar.query.filter_by(AyarAdi='database_type').first()
            if not db_type_setting or not db_type_setting.AyarDegeri:
                print("[HATA] SistemAyarlar'da database_type ayari bulunamadi!")
                return
            db_type = db_type_setting.AyarDegeri.strip().lower()
            print(f"[INFO] SistemAyarlar'dan database_type okundu: {db_type}")
        
        env_lines = []
        env_lines.append("# CRM Uygulamasi - Ortam Degiskenleri")
        env_lines.append("# Bu dosya otomatik olarak SistemAyarlar'dan olusturulmustur")
        env_lines.append(f"# Aktif Veritabani Tipi: {db_type.upper()}")
        env_lines.append("")
        
        # Flask ayarları (.env'den okumaya devam et)
        env_lines.append("# Flask Ayarlari")
        env_lines.append(f"SECRET_KEY={os.environ.get('SECRET_KEY', app.config.get('SECRET_KEY', 'change-this-in-.env'))}")
        env_lines.append(f"FLASK_DEBUG={os.environ.get('FLASK_DEBUG', 'True')}")
        env_lines.append(f"FLASK_HOST={os.environ.get('FLASK_HOST', '0.0.0.0')}")
        env_lines.append(f"FLASK_PORT={os.environ.get('FLASK_PORT', '5000')}")
        env_lines.append("")
        
        # Veritabanı ayarları
        env_lines.append("# Veritabani Ayarlari")
        database_uri = None
        
        if db_type == 'mysql':
            mysql_host = SistemAyar.query.filter_by(AyarAdi='database_mysql_host').first()
            mysql_port = SistemAyar.query.filter_by(AyarAdi='database_mysql_port').first()
            mysql_database = SistemAyar.query.filter_by(AyarAdi='database_mysql_database').first()
            mysql_username = SistemAyar.query.filter_by(AyarAdi='database_mysql_username').first()
            mysql_password = SistemAyar.query.filter_by(AyarAdi='database_mysql_password').first()
            mysql_charset = SistemAyar.query.filter_by(AyarAdi='database_mysql_charset').first()
            
            if all([mysql_host, mysql_database, mysql_username, mysql_password]):
                host = mysql_host.AyarDegeri
                port = mysql_port.AyarDegeri if mysql_port else '3306'
                database = mysql_database.AyarDegeri
                username = mysql_username.AyarDegeri
                password_encrypted = mysql_password.AyarDegeri
                password = decrypt_password(password_encrypted)  # Şifreyi deşifrele
                charset = mysql_charset.AyarDegeri if mysql_charset else 'utf8mb4'
                
                # URI oluştur
                password_encoded = quote_plus(password)
                username_encoded = quote_plus(username)
                database_uri = f"mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database}?charset={charset}"
                
                env_lines.append(f"# MySQL baglantisi (Aktif)")
                env_lines.append(f"DATABASE_URL={database_uri}")
            else:
                print("[WARN] MySQL ayarlari eksik, DATABASE_URL olusturulamadi!")
                
        elif db_type == 'mssql':
            mssql_server = SistemAyar.query.filter_by(AyarAdi='database_mssql_server').first()
            mssql_port = SistemAyar.query.filter_by(AyarAdi='database_mssql_port').first()
            mssql_database = SistemAyar.query.filter_by(AyarAdi='database_mssql_database').first()
            mssql_username = SistemAyar.query.filter_by(AyarAdi='database_mssql_username').first()
            mssql_password = SistemAyar.query.filter_by(AyarAdi='database_mssql_password').first()
            mssql_driver = SistemAyar.query.filter_by(AyarAdi='database_mssql_driver').first()
            
            if all([mssql_server, mssql_database, mssql_username, mssql_password]):
                server = mssql_server.AyarDegeri
                port = mssql_port.AyarDegeri if mssql_port else '1433'
                database = mssql_database.AyarDegeri
                username = mssql_username.AyarDegeri
                password_encrypted = mssql_password.AyarDegeri
                password = decrypt_password(password_encrypted)  # Şifreyi deşifrele
                driver = mssql_driver.AyarDegeri if mssql_driver else 'ODBC Driver 17 for SQL Server'
                
                # URI oluştur
                password_encoded = quote_plus(password)
                username_encoded = quote_plus(username)
                driver_encoded = quote_plus(driver)
                database_uri = f"mssql+pyodbc://{username_encoded}:{password_encoded}@{server}:{port}/{database}?driver={driver_encoded}&TrustServerCertificate=yes"
                
                env_lines.append(f"# MSSQL Server baglantisi (Aktif)")
                env_lines.append(f"DATABASE_URL={database_uri}")
            else:
                print("[WARN] MSSQL ayarlari eksik, DATABASE_URL olusturulamadi!")
        else:
            print(f"[WARN] Gecersiz veritabani tipi: {db_type}")
        
        if not database_uri:
            print("[HATA] DATABASE_URL olusturulamadi, .env dosyasi guncellenmedi!")
            return
        
        # Diğer ayarlar (.env'den okumaya devam et)
        env_lines.append("")
        env_lines.append("# SMTP Ayarlari (istege bagli)")
        env_lines.append(f"SMTP_HOST={os.environ.get('SMTP_HOST', '')}")
        env_lines.append(f"SMTP_PORT={os.environ.get('SMTP_PORT', '587')}")
        env_lines.append(f"SMTP_USER={os.environ.get('SMTP_USER', '')}")
        env_lines.append(f"SMTP_PASS={os.environ.get('SMTP_PASS', '')}")
        env_lines.append(f"SMTP_USE_TLS={os.environ.get('SMTP_USE_TLS', '1')}")
        env_lines.append(f"FROM_EMAIL={os.environ.get('FROM_EMAIL', '')}")
        env_lines.append(f"CSC_API_KEY={os.environ.get('CSC_API_KEY', '')}")
        
        # .env dosyasına yaz
        env_content = '\n'.join(env_lines)
        env_file_path = '.env'
        
        try:
            # Mevcut .env dosyasını yedekle
            if os.path.exists(env_file_path):
                backup_path = '.env.backup'
                with open(env_file_path, 'r', encoding='utf-8') as f:
                    backup_content = f.read()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(backup_content)
                print(f"[INFO] Mevcut .env dosyasi yedeklendi: {backup_path}")
            
            # Yeni .env dosyasını yaz
            with open(env_file_path, 'w', encoding='utf-8') as f:
                f.write(env_content)
            
            print(f"[OK] .env dosyasi guncellendi: {env_file_path}")
            
            # Ortam değişkenlerini de güncelle (runtime için)
            if 'DATABASE_URL' in env_content:
                for line in env_content.split('\n'):
                    if line.startswith('DATABASE_URL='):
                        db_url = line.split('=', 1)[1].strip()
                        os.environ['DATABASE_URL'] = db_url
                        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
                        print("[OK] DATABASE_URL ortam degiskeni guncellendi")
                        break
            
        except Exception as write_err:
            print(f"[HATA] .env dosyasina yazma hatasi: {write_err}")
            raise
        
    except Exception as e:
        print(f"[HATA] .env dosyasina aktarma hatasi: {e}")
        import traceback
        traceback.print_exc()
        raise

# Initialize SQLAlchemy with app
# Önce geçici olarak .env'den bağlantı kur (SistemAyarlar tablosuna erişmek için gerekli)
db = SQLAlchemy(app)

# Uygulama başlangıcında veritabanı ayarlarını yükle
# Bu fonksiyon hem `python app.py` hem de `flask run` durumlarında çalışsın
_app_initialized = False

def initialize_database_from_settings():
    """Uygulama başlangıcında SistemAyarlar'dan veritabanı bağlantısını yükle"""
    global _app_initialized
    
    if _app_initialized:
        return  # Zaten başlatıldı
    
    print("=" * 60)
    print("[INIT] initialize_database_from_settings() cagrildi!")
    print("=" * 60)
    try:
        with app.app_context():
            # Önce SistemAyarlar tablosunun var olup olmadığını kontrol et ve oluştur
            try:
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                
                # SistemAyarlar tablosu yoksa oluştur
                if 'SistemAyarlar' not in inspector.get_table_names():
                    db.create_all()
                    print("[OK] SistemAyarlar tablosu olusturuldu.")
            except Exception as e:
                print(f"[WARN] SistemAyarlar tablosu kontrol edilemedi: {e}")
                import traceback
                traceback.print_exc()
                return  # Hata varsa devam etme
            
            # Veritabanı ayarlarını oku
            try:
                print("[CHECK] SistemAyarlar'dan veritabani ayarlari okunmaya baslaniyor...")
                db_uri_from_settings = get_database_uri_from_settings(debug=True)
                if db_uri_from_settings:
                    # Şifreyi log'da gösterme - mask'la
                    masked_uri = db_uri_from_settings
                    # Şifre kısmını mask'la (://username:password@ kısmı)
                    if '@' in masked_uri and '://' in masked_uri:
                        parts = masked_uri.split('://')
                        if len(parts) > 1:
                            auth_part = parts[1].split('@')[0] if '@' in parts[1] else ''
                            if ':' in auth_part:
                                username = auth_part.split(':')[0]
                                masked_uri = masked_uri.replace(auth_part, f'{username}:***')
                    print(f"[INFO] Veritabani ayarlari SistemAyarlar'dan yuklendi: {masked_uri[:80]}...")
                    
                    # Yeni engine oluştur (mevcut bağlantıları kapat)
                    try:
                        db.engine.dispose()
                        print("[UPDATE] Eski veritabani baglantisi kapatildi.")
                    except Exception as dispose_err:
                        print(f"[WARN] Eski baglanti kapatilirken hata: {dispose_err}")
                    
                    # Yeni URI ile engine oluştur
                    new_engine = create_engine(
                        db_uri_from_settings,
                        pool_pre_ping=True,
                        pool_recycle=300
                    )
                    
                    # SQLAlchemy'yi yeni engine ile güncelle
                    # Flask-SQLAlchemy'nin internal state'ini güncelle
                    # Önce mevcut session'ları temizle
                    try:
                        db.session.close()
                        db.session.remove()
                    except:
                        pass
                    
                    # Engine'i ve config'i güncelle
                    # Flask-SQLAlchemy 3.x'te db.engine bir property ve setter yok
                    # Bu yüzden internal engine cache'ini ve config'i güncellememiz gerekiyor
                    
                    # Önce config'i güncelle
                    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri_from_settings
                    
                    # Flask-SQLAlchemy'nin internal engine cache'ini güncelle
                    # Flask-SQLAlchemy'nin _engine attribute'unu direkt set edemiyoruz
                    # Bunun yerine get_engine metodunu override ediyoruz
                    original_get_engine = db.get_engine
                    def custom_get_engine(app=None, bind=None):
                        # Flask-SQLAlchemy'nin get_engine metodu bazen app ve bind parametreleri alır
                        return new_engine
                    db.get_engine = custom_get_engine
                    
                    # Flask-SQLAlchemy'nin internal _engine attribute'unu da güncelle (eğer varsa)
                    # Ama önce eski engine'i dispose et
                    try:
                        if hasattr(db, '_engine'):
                            # Eski engine'i dispose et
                            try:
                                old_engine = db._engine
                                if old_engine:
                                    old_engine.dispose()
                            except:
                                pass
                            # Yeni engine'i set et (bu çalışmayabilir ama deneyelim)
                            db._engine = new_engine
                    except:
                        pass
                    
                    # Flask-SQLAlchemy'nin engine_for dict'ini de temizle
                    if hasattr(db, '_engine_for'):
                        db._engine_for = {}
                        db._engine_for[None] = new_engine
                    
                    # Flask-SQLAlchemy'nin session yapısını yeniden başlat
                    # Flask-SQLAlchemy 3.x için daha kapsamlı güncelleme
                    try:
                        from sqlalchemy.orm import scoped_session, sessionmaker
                        from sqlalchemy.orm import Session
                        
                        # Mevcut binding'leri temizle
                        db.Model.metadata.bind = new_engine
                        # Tabloları kontrol et (oluşturma değil, sadece binding)
                        
                        # Flask-SQLAlchemy'nin get_engine metodunu override et (zaten yukarıda yaptık)
                        # Bu Flask-SQLAlchemy 3.x için kritik
                        # Yukarıda zaten get_engine override edildi, burada tekrar yapmaya gerek yok
                        
                        # Session maker'ı da güncelle (eğer varsa)
                        if hasattr(db, '_make_session_factory'):
                            def new_session_factory():
                                return sessionmaker(bind=new_engine, class_=Session)()
                            db._make_session_factory = new_session_factory
                        
                        # Session registry'yi güncelle
                        # Flask-SQLAlchemy 3.x için session yapısını yeniden oluştur
                        try:
                            # Mevcut session'ı kapat ve temizle
                            db.session.close()
                            db.session.remove()
                            
                            # Flask-SQLAlchemy'nin internal session maker'ını güncelle
                            # Flask-SQLAlchemy 3.x'te session, scoped_session kullanır
                            # Ancak doğrudan registry'yi değiştirmek yerine, 
                            # engine'i değiştirdiğimiz için Flask-SQLAlchemy otomatik olarak yeni engine'i kullanmalı
                            # Ancak güvence için get_engine metodunu override ettik
                            
                            # Eğer Flask-SQLAlchemy'nin session registry'si varsa, onu da güncelle
                            if hasattr(db.session, 'registry'):
                                try:
                                    # Eski registry'yi kapat
                                    old_registry = db.session.registry
                                    if hasattr(old_registry, 'close_all'):
                                        old_registry.close_all()
                                except:
                                    pass
                                
                                # Yeni registry oluştur - ama Flask-SQLAlchemy bunu kendi yönetir
                                # Bu yüzden sadece engine'i değiştirmek yeterli olmalı
                                
                        except Exception as session_update_err:
                            print(f"[WARN] Session registry guncellenirken hata: {session_update_err}")
                            # Devam et, engine güncellemesi yeterli olabilir
                        
                        print("[OK] Veritabani baglantisi SistemAyarlar'dan guncellendi.")
                        print(f"   [LINK] Yeni URI: {db_uri_from_settings[:60]}...")
                        print("   [OK] SQLAlchemy engine, session registry ve metadata guncellendi.")
                    except Exception as session_err:
                        print(f"[WARN] Engine guncellenirken hata: {session_err}")
                        import traceback
                        traceback.print_exc()
                        # Yine de devam et
                    
                    # Bağlantıyı test et
                    try:
                        with new_engine.connect() as conn:
                            result = conn.execute(text("SELECT 1 as test"))
                            row = result.fetchone()
                            if row and row[0] == 1:
                                print("[OK] Veritabani baglantisi basariyla test edildi!")
                            else:
                                print("[WARN] Veritabani baglanti testi beklenmeyen sonuc dondurdu.")
                    except Exception as test_err:
                        print(f"[ERROR] Veritabani baglanti testi basarisiz: {test_err}")
                        import traceback
                        traceback.print_exc()
                        # Test başarısızsa eski bağlantıya geri dön
                        print("[WARN] SistemAyarlar baglantisi basarisiz, .env baglantisina geri donuluyor...")
                        # Eski URI'yi geri yükle
                        old_uri = _db_uri  # Başlangıçta kaydedilen .env URI'si
                        app.config['SQLALCHEMY_DATABASE_URI'] = old_uri
                        old_engine = create_engine(
                            old_uri,
                            pool_pre_ping=True,
                            pool_recycle=300
                        )
                        # Eski engine'i geri yükle (get_engine override'ını da geri al)
                        def restore_get_engine(app=None, bind=None):
                            # Flask-SQLAlchemy'nin get_engine metodu bazen app ve bind parametreleri alır
                            return old_engine
                        db.get_engine = restore_get_engine
                        if hasattr(db, '_engine_for'):
                            db._engine_for = {}
                            db._engine_for[None] = old_engine
                        if hasattr(db, '_engine'):
                            try:
                                db._engine = old_engine
                            except:
                                pass
                else:
                    print("[INFO] SistemAyarlar'da veritabani ayari yok, .env'deki ayarlar kullaniliyor.")
            except Exception as read_err:
                print(f"[WARN] SistemAyarlar'dan veritabani ayarlari okunamadi: {read_err}")
                import traceback
                traceback.print_exc()
    except Exception as e:
        print(f"[ERROR] Veritabani ayarlari yuklenirken hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Gerçek bağlantı tipini kontrol et ve SistemAyarlar'ı senkronize et
        try:
            with app.app_context():
                current_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                if current_uri:
                    # Gerçek bağlantı tipini belirle
                    if 'mssql' in current_uri.lower():
                        gercek_tip = 'mssql'
                    elif 'mysql' in current_uri.lower():
                        gercek_tip = 'mysql'
                    else:
                        gercek_tip = None
                    
                    if gercek_tip:
                        # SistemAyarlar'daki database_type değerini kontrol et ve güncelle
                        try:
                            db_type_setting = SistemAyar.query.filter_by(AyarAdi='database_type').first()
                            if db_type_setting:
                                mevcut_tip = db_type_setting.AyarDegeri.strip().lower() if db_type_setting.AyarDegeri else None
                                if mevcut_tip != gercek_tip:
                                    print(f"[SYNC] SistemAyarlar database_type guncelleniyor: {mevcut_tip} -> {gercek_tip}")
                                    db_type_setting.AyarDegeri = gercek_tip
                                    db.session.commit()
                                    print(f"[OK] SistemAyarlar database_type senkronize edildi: {gercek_tip}")
                            else:
                                # database_type ayarı yoksa oluştur
                                print(f"[SYNC] SistemAyarlar database_type olusturuluyor: {gercek_tip}")
                                yeni_ayar = SistemAyar(
                                    AyarAdi='database_type',
                                    AyarDegeri=gercek_tip,
                                    Aciklama='Veritabani tipi (mssql veya mysql) - otomatik guncellenir'
                                )
                                db.session.add(yeni_ayar)
                                db.session.commit()
                                print(f"[OK] SistemAyarlar database_type olusturuldu: {gercek_tip}")
                        except Exception as sync_err:
                            print(f"[WARN] SistemAyarlar senkronizasyonu basarisiz: {sync_err}")
                            # Devam et, kritik değil
        except Exception as sync_err:
            print(f"[WARN] Gercek baglanti tipi kontrol edilemedi: {sync_err}")
        
        _app_initialized = True
        print("=" * 60)
        print("[OK] initialize_database_from_settings() tamamlandi!")
        print("=" * 60 + "\n")

# Asenkron loglama sistemi
log_queue = queue.Queue()

def background_logger():
    """Arka planda log kayıtlarını veritabanına yazan thread"""
    with app.app_context():
        while True:
            try:
                log_data = log_queue.get(timeout=1)
                if log_data is None:  # Shutdown signal
                    break
                db.session.add(log_data)
                db.session.commit()
            except queue.Empty:
                # Timeout - bu normal, devam et
                continue
            except Exception as e:
                print(f"Log yazma hatası: {e}")
                try:
                    db.session.rollback()
                except:
                    pass

# Background thread başlat
log_thread = threading.Thread(target=background_logger, daemon=True)
log_thread.start()

# IP adresi alma yardımcı fonksiyonu
def get_client_ip():
    """Gerçek client IP adresini al (proxy arkasında çalışırken)"""
    # X-Forwarded-For header'ını kontrol et (proxy arkasında)
    x_forwarded = request.headers.get('X-Forwarded-For')
    if x_forwarded:
        # İlk IP adresini al (client IP)
        ip = x_forwarded.split(',')[0].strip()
        return format_ip_for_display(ip)
    
    # X-Real-IP header'ını kontrol et (nginx gibi)
    x_real_ip = request.headers.get('X-Real-IP')
    if x_real_ip:
        return format_ip_for_display(x_real_ip)
    
    # Localhost'ta test için gerçek IP kullan
    remote_addr = request.remote_addr
    if remote_addr == '127.0.0.1':
        # Gerçek IP adresinizi kullan (Wi-Fi IP'si)
        return "192.168.1.11"
    
    # IPv6 adresi ise IPv4'e çevirmeye çalış
    if ':' in remote_addr and len(remote_addr) > 20:
        # Arkadaşınızın IPv4 adresini kullan (test için)
        return "192.168.1.106"
    
    return format_ip_for_display(remote_addr)

def format_ip_for_display(ip):
    """IP adresini loglama için uygun formata çevir"""
    if not ip:
        return "Unknown"
    
    # IPv6 adreslerini kısalt ama göster
    if ':' in ip and len(ip) > 20:
        # IPv6 adresini kısalt: ilk 2 segment + son 2 segment
        parts = ip.split(':')
        if len(parts) >= 8:
            # İlk 2 ve son 2 segmenti al
            first_part = ':'.join(parts[:2])
            last_part = ':'.join(parts[-2:])
            return f"{first_part}...{last_part}"
        else:
            return f"{parts[0]}...{parts[-1]}"
    
    return ip

# Loglama yardımcı fonksiyonları
def log_user_action(action_type, table_name, record_id=None, old_data=None, new_data=None, detail=None):
    """Kullanıcı işlemini asenkron olarak logla"""
    try:
        if 'user_id' not in session:
            return
    except RuntimeError:
        # Session context yoksa (test ortamı gibi) loglama yapma
        return
    
    log_data = KullaniciLog(
        KullaniciID=session['user_id'],
        IslemTipi=action_type,
        TabloAdi=table_name,
        KayitID=record_id,
        EskiVeri=json.dumps(old_data, ensure_ascii=False) if old_data else None,
        YeniVeri=json.dumps(new_data, ensure_ascii=False) if new_data else None,
        IslemDetayi=detail,
        IPAdresi=get_client_ip(),
        UserAgent=request.headers.get('User-Agent', '')
    )
    log_queue.put(log_data)

def log_user_action_decorator(action_type, table_name, record_id_param=None, detail_func=None):
    """Loglama decorator'ı"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            
            # Record ID'yi al
            record_id = None
            if record_id_param and record_id_param in kwargs:
                record_id = kwargs[record_id_param]
            
            # Detay fonksiyonu varsa çalıştır
            detail = None
            if detail_func:
                try:
                    detail = detail_func(result, *args, **kwargs)
                except:
                    pass
            
            # Logla
            log_user_action(action_type, table_name, record_id, detail=detail)
            
            return result
        return decorated_function
    return decorator

def get_record_info(log):
    """Log için record bilgisini hazırla"""
    try:
        if not log.KayitID:
            return None
            
        if log.TabloAdi == 'Randevu':
            randevu = Randevu.query.filter_by(RandevuID=log.KayitID, FirmaID=log.kullanici.FirmaID).first()
            if randevu:
                tarih_str = randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M')
                musteri_adi = f"{randevu.MusteriAdi or ''} {randevu.MusteriSoyadi or ''}".strip()
                if musteri_adi:
                    return f"{tarih_str} - {musteri_adi} ({randevu.RandevuBaslik})"
                else:
                    return f"{tarih_str} - {randevu.RandevuBaslik}"
            else:
                return f"ID: {log.KayitID}"
                
        elif log.TabloAdi == 'Musteri':
            musteri = Musteri.query.filter_by(MusteriID=log.KayitID, FirmaID=log.kullanici.FirmaID).first()
            if musteri:
                musteri_adi = f"{musteri.Ad or ''} {musteri.Soyad or ''}".strip()
                if musteri_adi and musteri.Telefon:
                    return f"{musteri_adi} ({musteri.Telefon})"
                elif musteri_adi:
                    return musteri_adi
                elif musteri.Telefon:
                    return musteri.Telefon
                else:
                    return f"ID: {log.KayitID}"
            else:
                return f"ID: {log.KayitID}"
                
        elif log.TabloAdi == 'Kullanici':
            kullanici = Kullanici.query.filter_by(KullaniciID=log.KayitID, FirmaID=log.kullanici.FirmaID).first()
            if kullanici:
                kullanici_adi = f"{kullanici.Ad or ''} {kullanici.Soyad or ''}".strip()
                if kullanici_adi:
                    return f"{kullanici_adi} ({kullanici.KullaniciAdi})"
                else:
                    return kullanici.KullaniciAdi
            else:
                return f"ID: {log.KayitID}"
                
        elif log.TabloAdi == 'Sistem':
            # Sistem logları için detay bilgisini kullan
            if log.IslemDetayi:
                return log.IslemDetayi[:50] + "..." if len(log.IslemDetayi) > 50 else log.IslemDetayi
            else:
                return "Sistem İşlemi"
                
        else:
            # Diğer tablolar için sadece ID göster
            return f"ID: {log.KayitID}"
            
    except Exception:
        # Hata durumunda sadece ID göster
        return f"ID: {log.KayitID}" if log.KayitID else None

# Babel konfigürasyonu
app.config['LANGUAGES'] = {
    'tr': 'Türkçe',
    'en': 'English',
    'fr': 'Français',
    'de': 'Deutsch'
}
app.config['BABEL_DEFAULT_LOCALE'] = 'tr'
app.config['BABEL_DEFAULT_TIMEZONE'] = 'Europe/Istanbul'

def get_locale():
    # Önce session'dan dil tercihini kontrol et
    if 'language' in session:
        return session['language']
    # Sonra request header'ından
    return app.config['BABEL_DEFAULT_LOCALE']

# Babel'i başlat
babel = Babel(app)
babel.init_app(app, locale_selector=get_locale)

# Parola karmaşıklık kontrolü
import re
def is_password_strong(password: str) -> bool:
    if not password or len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True

# Flask uygulaması ilk request'te başlatılsın (flask run için)
@app.before_request
def ensure_app_initialized():
    """İlk request'te veritabanı ayarlarını yükle (flask run için)"""
    global _app_initialized
    if not _app_initialized:
        print("\n" + "=" * 60)
        print("[WEB] Ilk request geldi - SistemAyarlar yukleniyor...")
        print("=" * 60 + "\n")
        initialize_database_from_settings()

@app.before_request
def enforce_password_change():
    # Zorunlu parola değişimi: giriş yapılmışsa ve bayrak açıksa, sadece izinli endpointlere erişsin
    if 'user_id' in session and session.get('must_change_password'):
        allowed = set(['sifre_degistir', 'logout', 'set_language', 'static'])
        if request.endpoint not in allowed:
            return redirect(url_for('sifre_degistir'))

# Yardımcı: İstek JSON/AJAX mi?
def _wants_json_response():
    """Return True only for AJAX/JSON API requests.
    - Prefer explicit XHR header
    - Or when content-type/body is JSON
    - Or when client clearly prefers JSON over HTML
    """
    try:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return True
        if request.is_json:
            return True
        accepts = request.accept_mimetypes or {}
        # Only treat as JSON if JSON is strictly preferred over HTML
        json_q = accepts['application/json'] if 'application/json' in accepts else 0
        html_q = accepts['text/html'] if 'text/html' in accepts else 0
        return json_q > html_q
    except Exception:
        return False

# Login gerekli decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if _wants_json_response():
                return jsonify({"success": False, "message": "Oturum gerekli"}), 401
            return redirect(url_for('login'))
        
        # Aktif oturum kontrolü (tek oturum) - tüm isteklerde kontrol et
        if True:
            user_id = session.get('user_id')
            session_token = session.get('session_token')
            if user_id and session_token:
                try:
                    # 1) Kaydı bu token ile bulmaya çalış
                    aktif_oturum = AktifOturum.query.filter_by(
                        KullaniciID=user_id,
                        SessionToken=session_token
                    ).first()
                    if not aktif_oturum:
                        # 2) Bu kullanıcı için herhangi bir aktif kayıt var mı?
                        mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
                        if mevcut_kayit is None:
                            # Kayıt yoksa otomatik yeniden oluştur (tarayıcı çerezi duruyor ama DB kaydı silinmiş olabilir)
                            # Önce mevcut kaydı kontrol et - UNIQUE constraint hatasını önle
                            mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
                            if mevcut_kayit:
                                # Mevcut kaydı güncelle
                                mevcut_kayit.SessionToken = session_token
                                mevcut_kayit.ClientIP = get_client_ip()
                                mevcut_kayit.UserAgent = request.headers.get('User-Agent', '')
                                mevcut_kayit.SonGorulmeZamani = datetime.now()
                                try:
                                    db.session.commit()
                                except Exception as commit_error:
                                    print(f"Oturum güncelleme hatası: {commit_error}")
                                    db.session.rollback()
                            else:
                                # Yeni kayıt oluştur
                                try:
                                    yeni = AktifOturum(
                                        KullaniciID=user_id,
                                        SessionToken=session_token,
                                        ClientIP=get_client_ip(),
                                        UserAgent=request.headers.get('User-Agent', '')
                                    )
                                    db.session.add(yeni)
                                    db.session.commit()
                                except Exception as db_error:
                                    # UNIQUE constraint hatası - race condition olabilir
                                    db.session.rollback()
                                    # Tekrar kontrol et ve güncelle
                                    mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
                                    if mevcut_kayit:
                                        mevcut_kayit.SessionToken = session_token
                                        mevcut_kayit.ClientIP = get_client_ip()
                                        mevcut_kayit.UserAgent = request.headers.get('User-Agent', '')
                                        mevcut_kayit.SonGorulmeZamani = datetime.now()
                                        try:
                                            db.session.commit()
                                        except Exception as commit_error:
                                            print(f"Oturum güncelleme hatası (2. deneme): {commit_error}")
                                            db.session.rollback()
                                    else:
                                        print(f"Oturum kaydı oluşturma hatası: {db_error}")
                        else:
                            # Mevcut kayıt var ama token farklı
                            # Aynı IP ve User-Agent ise güncelle (race condition olabilir)
                            if mevcut_kayit.ClientIP == get_client_ip() and mevcut_kayit.UserAgent == request.headers.get('User-Agent', ''):
                                # Aynı cihaz, token'ı güncelle
                                mevcut_kayit.SessionToken = session_token
                                mevcut_kayit.SonGorulmeZamani = datetime.now()
                                try:
                                    db.session.commit()
                                except:
                                    db.session.rollback()
                            else:
                                # Başka bir cihazda aktif oturum var: engelle
                                session.clear()
                                if _wants_json_response():
                                    return jsonify({"success": False, "message": "Oturum sonlandırıldı"}), 401
                                flash('Oturumunuz başka bir cihazdan sonlandırıldı. Lütfen tekrar giriş yapın.', 'error')
                                return redirect(url_for('login'))
                except Exception as e:
                    print(f"Oturum kontrolü hatası: {e}")
                    session.clear()
                    if _wants_json_response():
                        return jsonify({"success": False, "message": "Oturum kontrol hatası"}), 401
                    flash('Oturum kontrolünde hata oluştu. Lütfen tekrar giriş yapın.', 'error')
                    return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

# Admin gerekli decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if _wants_json_response():
                return jsonify({"success": False, "message": "Oturum gerekli"}), 401
            return redirect(url_for('login'))
        
        # Aktif oturum kontrolü (tek oturum) - tüm isteklerde kontrol et
        if True:
            user_id = session.get('user_id')
            session_token = session.get('session_token')
            if user_id and session_token:
                try:
                    aktif_oturum = AktifOturum.query.filter_by(
                        KullaniciID=user_id,
                        SessionToken=session_token
                    ).first()
                    if not aktif_oturum:
                        session.clear()
                        if _wants_json_response():
                            return jsonify({"success": False, "message": "Oturum sonlandırıldı"}), 401
                        flash('Oturumunuz başka bir cihazdan sonlandırıldı. Lütfen tekrar giriş yapın.', 'error')
                        return redirect(url_for('login'))
                except Exception as e:
                    print(f"Oturum kontrolü hatası: {e}")
                    session.clear()
                    if _wants_json_response():
                        return jsonify({"success": False, "message": "Oturum kontrol hatası"}), 401
                    flash('Oturum kontrolünde hata oluştu. Lütfen tekrar giriş yapın.', 'error')
                    return redirect(url_for('login'))
        
        if not session.get('is_admin', False) and not session.get('ayarlar_modulu', False):
            flash('Bu sayfaya erişim yetkiniz yok!', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Sadece admin gerekli decorator (ayarlar modülü yetkisi yeterli değil)
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if _wants_json_response():
                return jsonify({"success": False, "message": "Oturum gerekli"}), 401
            return redirect(url_for('login'))
        
        # Aktif oturum kontrolü (tek oturum) - tüm isteklerde kontrol et
        if True:
            user_id = session.get('user_id')
            session_token = session.get('session_token')
            if user_id and session_token:
                try:
                    aktif_oturum = AktifOturum.query.filter_by(
                        KullaniciID=user_id,
                        SessionToken=session_token
                    ).first()
                    if not aktif_oturum:
                        session.clear()
                        if _wants_json_response():
                            return jsonify({"success": False, "message": "Oturum sonlandırıldı"}), 401
                        flash('Oturumunuz başka bir cihazdan sonlandırıldı. Lütfen tekrar giriş yapın.', 'error')
                        return redirect(url_for('login'))
                except Exception as e:
                    print(f"Oturum kontrolü hatası: {e}")
                    session.clear()
                    if _wants_json_response():
                        return jsonify({"success": False, "message": "Oturum kontrol hatası"}), 401
                    flash('Oturum kontrolünde hata oluştu. Lütfen tekrar giriş yapın.', 'error')
                    return redirect(url_for('login'))
        
        if not session.get('is_admin', False):
            flash('Bu sayfaya erişim yetkiniz yok!', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Database Models
class Firma(db.Model):
    __tablename__ = 'Firmalar'
    
    FirmaID = db.Column(db.Integer, primary_key=True)
    FirmaAdi = db.Column(db.NVARCHAR(100), nullable=False)
    FirmaKodu = db.Column(db.NVARCHAR(20), unique=True, nullable=False)
    Adres = db.Column(db.NVARCHAR(200))
    Telefon = db.Column(db.NVARCHAR(20))
    Email = db.Column(db.NVARCHAR(100))
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    def __repr__(self):
        return f'<Firma {self.FirmaAdi}>'

class Kullanici(db.Model):
    __tablename__ = 'Kullanicilar'
    
    KullaniciID = db.Column(db.Integer, primary_key=True)
    KullaniciAdi = db.Column(db.NVARCHAR(50), unique=True, nullable=False)
    Sifre = db.Column(db.NVARCHAR(255), nullable=False)
    Ad = db.Column(db.NVARCHAR(50), nullable=False)
    Soyad = db.Column(db.NVARCHAR(50), nullable=False)
    Email = db.Column(db.NVARCHAR(100), unique=True, nullable=False)
    Telefon = db.Column(db.NVARCHAR(20))
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    Admin = db.Column(db.Boolean, default=False)
    Aktif = db.Column(db.Boolean, default=True)
    RaporlarModulu = db.Column(db.Boolean, default=True)  # Raporlar modülüne erişim
    AyarlarModulu = db.Column(db.Boolean, default=False)  # Ayarlar modülüne erişim
    LogModulu = db.Column(db.Boolean, default=False)      # Log modülüne erişim
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    # İlişkiler
    firma = db.relationship('Firma', backref='kullanicilar')
    
    def __repr__(self):
        return f'<Kullanici {self.KullaniciAdi}>'


class AktifOturum(db.Model):
    __tablename__ = 'AktifOturumlar'
    
    # MSSQL ve MySQL uyumluluğu için:
    # Her iki veritabanında da aynı kolon isimleri kullanılıyor:
    # AktifOturumID, ClientIP, GirisZamani, SonGorulmeZamani
    
    # Primary key
    AktifOturumID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    SessionToken = db.Column(db.String(255), nullable=False, unique=True)
    
    # IP ve UserAgent
    ClientIP = db.Column(db.String(50), nullable=True)
    UserAgent = db.Column(db.Text, nullable=True)
    
    # Tarih kolonları
    GirisZamani = db.Column(db.DateTime, default=lambda: datetime.now(), nullable=False)
    SonGorulmeZamani = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now(), nullable=False)

    kullanici = db.relationship('Kullanici', backref='aktif_oturum', uselist=False)

    def __repr__(self):
        return f'<AktifOturum {self.KullaniciID}>'

class KullaniciLog(db.Model):
    __tablename__ = 'KullaniciLoglari'

    LogID = db.Column(db.Integer, primary_key=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    IslemTipi = db.Column(db.NVARCHAR(30), nullable=False)  # 'CREATE', 'UPDATE', 'DELETE', 'VIEW', 'CANCEL', 'LOGIN', 'LOGOUT'
    TabloAdi = db.Column(db.NVARCHAR(30), nullable=False)   # 'Randevu', 'Musteri', 'Rapor', 'Kullanici', 'Sistem'
    KayitID = db.Column(db.Integer)                         # İlgili kaydın ID'si (varsa)
    EskiVeri = db.Column(db.UnicodeText)                    # JSON format - değişiklik öncesi
    YeniVeri = db.Column(db.UnicodeText)                    # JSON format - değişiklik sonrası
    IslemDetayi = db.Column(db.NVARCHAR(500))               # İnsan okunabilir açıklama
    IPAdresi = db.Column(db.NVARCHAR(45))
    UserAgent = db.Column(db.NVARCHAR(500))
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), nullable=False)

    kullanici = db.relationship('Kullanici', backref='loglar')

    def __repr__(self):
        return f'<KullaniciLog {self.LogID} - {self.IslemTipi} - {self.TabloAdi}>'

class YetkiTipi(db.Model):
    __tablename__ = 'YetkiTipleri'
    
    YetkiID = db.Column(db.Integer, primary_key=True)
    YetkiAdi = db.Column(db.NVARCHAR(50), nullable=False)
    YetkiAciklamasi = db.Column(db.NVARCHAR(200))
    Aktif = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<YetkiTipi {self.YetkiAdi}>'

class KullaniciYetki(db.Model):
    __tablename__ = 'KullaniciYetkileri'
    
    KullaniciYetkiID = db.Column(db.Integer, primary_key=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    YetkiID = db.Column(db.Integer, db.ForeignKey('YetkiTipleri.YetkiID'), nullable=False)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # İlişkiler
    kullanici = db.relationship('Kullanici', backref='kullanici_yetkileri')
    yetki_tipi = db.relationship('YetkiTipi', backref='kullanici_yetkileri')
    
    __table_args__ = (db.UniqueConstraint('KullaniciID', 'YetkiID', name='uq_kullanici_yetki'),)
    
    def __repr__(self):
        return f'<KullaniciYetki {self.KullaniciID}-{self.YetkiID}>'

class Randevu(db.Model):
    __tablename__ = 'Randevular'
    
    RandevuID = db.Column(db.Integer, primary_key=True)
    RandevuBaslik = db.Column(db.NVARCHAR(100), nullable=False)
    RandevuAciklamasi = db.Column(db.NVARCHAR(500))
    RandevuTarihi = db.Column(db.DateTime, nullable=False)
    RandevuSuresi = db.Column(db.Integer, default=60)
    MusteriID = db.Column(db.Integer, db.ForeignKey('Musteriler.MusteriID'), nullable=True)
    MusteriAdi = db.Column(db.NVARCHAR(100))
    MusteriSoyadi = db.Column(db.NVARCHAR(100))
    MusteriTelefon = db.Column(db.NVARCHAR(20))
    MusteriEmail = db.Column(db.NVARCHAR(100))
    Durum = db.Column(db.NVARCHAR(20), default='Beklemede')
    IslemID = db.Column(db.Integer, db.ForeignKey('RandevuIslemler.IslemID'), nullable=True)
    OlusturanKullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    DefterID = db.Column(db.Integer, db.ForeignKey('RandevuDefterAyarlar.AyarID'), nullable=True)
    GorevID = db.Column(db.Integer, db.ForeignKey('Todos.TodoID'), nullable=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    # İlişkiler
    olusturan_kullanici = db.relationship('Kullanici', backref='olusturulan_randevular')
    firma = db.relationship('Firma', backref='randevular')
    musteri = db.relationship('Musteri', backref='randevular')
    islem = db.relationship('RandevuIslem', backref='randevular')
    defter = db.relationship('RandevuDefterAyar', backref='randevular')
    bildirimler = db.relationship('Bildirim', foreign_keys='Bildirim.IlgiliRandevuID', cascade='all, delete-orphan')
    hatirlatmalar = db.relationship('RandevuHatirlatma', cascade='all, delete-orphan')
    yetkiler = db.relationship('RandevuYetki', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Randevu {self.RandevuBaslik}>'

class RandevuYetki(db.Model):
    __tablename__ = 'RandevuYetkileri'
    
    RandevuYetkiID = db.Column(db.Integer, primary_key=True)
    RandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'), nullable=False)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    GoruntulemeYetkisi = db.Column(db.Boolean, default=True)
    DuzenlemeYetkisi = db.Column(db.Boolean, default=False)
    SilmeYetkisi = db.Column(db.Boolean, default=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # İlişkiler
    randevu = db.relationship('Randevu', overlaps="yetkiler")
    kullanici = db.relationship('Kullanici', backref='randevu_yetkileri')
    
    __table_args__ = (db.UniqueConstraint('RandevuID', 'KullaniciID', name='uq_randevu_kullanici'),)
    
    def __repr__(self):
        return f'<RandevuYetki {self.RandevuID}-{self.KullaniciID}>'

# Randevu Defteri Ayarlari Modeli
class RandevuDefterAyar(db.Model):
    __tablename__ = 'RandevuDefterAyarlar'

    AyarID = db.Column(db.Integer, primary_key=True)
    DefterAdi = db.Column(db.NVARCHAR(100), nullable=False, default='Varsayilan Defter')
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    CalismaGunleri = db.Column(db.NVARCHAR(50), default='1,2,3,4,5')  # 1=Mon ... 7=Sun
    BaslangicSaati = db.Column(db.NVARCHAR(5), default='09:00')
    BitisSaati = db.Column(db.NVARCHAR(5), default='18:00')
    SlotDakika = db.Column(db.Integer, default=30)
    Aktif = db.Column(db.Boolean, default=True)

    firma = db.relationship('Firma', backref='defter_ayarlar')

    def __repr__(self):
        return f'<RandevuDefterAyar {self.AyarID}-{self.DefterAdi}>'

# Randevu Defteri Bloklama: Belirli tarih/saat araliklarini kapatma
class RandevuDefterBlok(db.Model):
    __tablename__ = 'RandevuDefterBloklar'

    BlokID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    DefterID = db.Column(db.Integer, db.ForeignKey('RandevuDefterAyarlar.AyarID'), nullable=True)  # None: tüm defterler
    BaslangicTarih = db.Column(db.Date, nullable=False)
    BitisTarih = db.Column(db.Date, nullable=True)  # null ise tek gün
    SaatBaslangic = db.Column(db.NVARCHAR(5), nullable=True)  # 'HH:MM'
    SaatBitis = db.Column(db.NVARCHAR(5), nullable=True)
    Aciklama = db.Column(db.NVARCHAR(200), nullable=True)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())

    firma = db.relationship('Firma')
    defter = db.relationship('RandevuDefterAyar')

# Randevu Referanslari
class RandevuReferans(db.Model):
    __tablename__ = 'RandevuReferanslari'

    ReferansID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    Ad = db.Column(db.NVARCHAR(100), nullable=False)
    Aktif = db.Column(db.Boolean, default=True)

    firma = db.relationship('Firma', backref='randevu_referanslar')

    def __repr__(self):
        return f'<RandevuReferans {self.ReferansID}-{self.Ad}>'

# Randevu İşlemleri
class RandevuIslem(db.Model):
    __tablename__ = 'RandevuIslemler'
    
    IslemID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    DefterID = db.Column(db.Integer, db.ForeignKey('RandevuDefterAyarlar.AyarID'), nullable=True)
    IslemAdi = db.Column(db.NVARCHAR(100), nullable=False)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # İlişkiler
    firma = db.relationship('Firma', backref='randevu_islemleri')
    defter = db.relationship('RandevuDefterAyar', backref='randevu_islemleri')
    
    def __repr__(self):
        return f'<RandevuIslem {self.IslemID}: {self.IslemAdi}>'

# Bildirimler
class Bildirim(db.Model):
    __tablename__ = 'Bildirimler'

    BildirimID = db.Column(db.Integer, primary_key=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    Metin = db.Column(db.NVARCHAR(300), nullable=False)
    Okundu = db.Column(db.Boolean, default=False)
    Tip = db.Column(db.NVARCHAR(30), default='genel')
    IlgiliRandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'))
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())

    kullanici = db.relationship('Kullanici')
    firma = db.relationship('Firma')
    randevu = db.relationship('Randevu', foreign_keys=[IlgiliRandevuID], overlaps="bildirimler")

    def __repr__(self):
        return f'<Bildirim {self.BildirimID} kullanici={self.KullaniciID}>'

# Randevu Hatirlatma
class RandevuHatirlatma(db.Model):
    __tablename__ = 'RandevuHatirlatmalar'

    HatirlatmaID = db.Column(db.Integer, primary_key=True)
    RandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'), nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    RecipientEmail = db.Column(db.NVARCHAR(200))
    MinutesBefore = db.Column(db.Integer, default=60)
    Gonderildi = db.Column(db.Boolean, default=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GonderimTarihi = db.Column(db.DateTime)

    randevu = db.relationship('Randevu', overlaps="hatirlatmalar")

    def __repr__(self):
        return f'<RandevuHatirlatma {self.HatirlatmaID} randevu={self.RandevuID}>'

# Randevu SMS Hatirlatma
class RandevuSMSHatirlatma(db.Model):
    __tablename__ = 'RandevuSMSHatirlatmalar'

    HatirlatmaID = db.Column(db.Integer, primary_key=True)
    RandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'), nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    RecipientPhone = db.Column(db.NVARCHAR(20))
    MinutesBefore = db.Column(db.Integer, default=1440)
    Gonderildi = db.Column(db.Boolean, default=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GonderimTarihi = db.Column(db.DateTime)

    randevu = db.relationship('Randevu')

    def __repr__(self):
        return f'<RandevuSMSHatirlatma {self.HatirlatmaID} randevu={self.RandevuID}>'

# E-posta Ayarları
class FirmaEmailAyar(db.Model):
    __tablename__ = 'FirmaEmailAyarlari'
    
    EmailAyarID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    SMTP_Sunucu = db.Column(db.NVARCHAR(200), nullable=False)
    SMTP_Port = db.Column(db.Integer, nullable=False)
    KullaniciAdi = db.Column(db.NVARCHAR(200), nullable=False)
    Sifre = db.Column(db.NVARCHAR(200), nullable=False)
    SSL_Kullan = db.Column(db.Boolean, default=True)
    VarsayilanGonderenAdi = db.Column(db.NVARCHAR(200))
    VarsayilanGonderenEmail = db.Column(db.NVARCHAR(200))
    # Varsayılan e-posta içerik ayarları
    VarsayilanEmailKonu = db.Column(db.NVARCHAR(200))
    VarsayilanEmailMetni = db.Column(db.NVARCHAR(max))
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='email_ayarlar')
    
    def __repr__(self):
        return f'<FirmaEmailAyar {self.EmailAyarID} firma={self.FirmaID}>'

# SMS Ayarları
class FirmaSMSAyar(db.Model):
    __tablename__ = 'FirmaSMSAyarlari'
    
    SMSAyarID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    SMSFirmasi = db.Column(db.NVARCHAR(50), nullable=False)  # 'netgsm', 'iletimerkezi', 'mesajnet', 'custom'
    API_Key = db.Column(db.NVARCHAR(500))
    API_Secret = db.Column(db.NVARCHAR(500))
    KullaniciAdi = db.Column(db.NVARCHAR(200))
    Sifre = db.Column(db.NVARCHAR(200))
    GondericiAdi = db.Column(db.NVARCHAR(20))
    API_URL = db.Column(db.NVARCHAR(500))
    # Varsayılan SMS metni
    VarsayilanSMSMetni = db.Column(db.NVARCHAR(1000))
    # Zamanlama seçenekleri
    SMSGonderOnCreate = db.Column(db.Boolean, default=False)
    SMSGonder24SaatOnce = db.Column(db.Boolean, default=False)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='sms_ayarlar')
    
    def __repr__(self):
        return f'<FirmaSMSAyar {self.SMSAyarID} firma={self.FirmaID}>'

# WhatsApp Ayarları
class FirmaWhatsAppAyar(db.Model):
    __tablename__ = 'FirmaWhatsAppAyarlari'
    
    WhatsAppAyarID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    AccessToken = db.Column(db.Text, nullable=True)
    PhoneNumberID = db.Column(db.String(50), nullable=True)
    BusinessAccountID = db.Column(db.String(50), nullable=True)
    WebhookVerifyToken = db.Column(db.String(100), nullable=True)
    # Varsayılan mesaj şablonları
    RandevuOlusturmaMesaji = db.Column(db.Text, nullable=True)
    RandevuHatirlatmaMesaji = db.Column(db.Text, nullable=True)
    RandevuIptalMesaji = db.Column(db.Text, nullable=True)
    # Zamanlama seçenekleri
    MesajGonderOnCreate = db.Column(db.Boolean, default=False)
    MesajGonder24SaatOnce = db.Column(db.Boolean, default=False)
    MesajGonder1SaatOnce = db.Column(db.Boolean, default=False)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='whatsapp_ayarlar')
    
    def __repr__(self):
        return f'<FirmaWhatsAppAyar {self.WhatsAppAyarID} firma={self.FirmaID}>'

# Sistem Ayarları (Veritabanı Konfigürasyonu)
class SistemAyar(db.Model):
    __tablename__ = 'SistemAyarlar'
    
    AyarID = db.Column(db.Integer, primary_key=True)
    AyarAdi = db.Column(db.String(100), unique=True, nullable=False)  # 'database_type', 'database_mssql_url', 'database_mysql_url'
    AyarDegeri = db.Column(db.Text, nullable=True)  # JSON veya string değer
    Aciklama = db.Column(db.NVARCHAR(500))
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    def __repr__(self):
        return f'<SistemAyar {self.AyarAdi}={self.AyarDegeri}>'

# Müşteri Kategorileri
class MusteriKategori(db.Model):
    __tablename__ = 'MusteriKategorileri'

    KategoriID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    KategoriAdi = db.Column(db.NVARCHAR(100), nullable=False)
    Renk = db.Column(db.NVARCHAR(20), default='#007bff')
    Aciklama = db.Column(db.NVARCHAR(500))
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())

    firma = db.relationship('Firma', backref='musteri_kategoriler')

    def __repr__(self):
        return f'<MusteriKategori {self.KategoriID} {self.KategoriAdi}>'

# Müşteriler
class Musteri(db.Model):
    __tablename__ = 'Musteriler'

    MusteriID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    MusteriAdi = db.Column(db.NVARCHAR(100), nullable=False)
    MusteriSoyadi = db.Column(db.NVARCHAR(100), nullable=False)
    Telefon = db.Column(db.NVARCHAR(20))
    Email = db.Column(db.NVARCHAR(200))
    # Adres bilgileri - 4 ayrı alan
    Ulke = db.Column(db.NVARCHAR(100), default='Türkiye')
    Sehir = db.Column(db.NVARCHAR(100))
    Ilce = db.Column(db.NVARCHAR(100))
    Adres = db.Column(db.NVARCHAR(500))
    DogumTarihi = db.Column(db.Date)
    Yas = db.Column(db.Integer)  # Yaş alanı
    Cinsiyet = db.Column(db.NVARCHAR(10))  # 'Erkek', 'Kadın'
    KategoriID = db.Column(db.Integer, db.ForeignKey('MusteriKategorileri.KategoriID'))
    Notlar = db.Column(db.NVARCHAR(1000))
    ProfilFotografi = db.Column(db.NVARCHAR(500))
    Aktif = db.Column(db.Boolean, default=True)
    OlusturanKullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'))
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now())

    firma = db.relationship('Firma', backref='musteriler')
    kategori = db.relationship('MusteriKategori', backref='musteriler')
    olusturan_kullanici = db.relationship('Kullanici', backref='olusturulan_musteriler', foreign_keys=[OlusturanKullaniciID])

    @property
    def tam_adi(self):
        return f"{self.MusteriAdi} {self.MusteriSoyadi}"

    def __repr__(self):
        return f'<Musteri {self.MusteriID} {self.tam_adi}>'

# Görev Durumları
class TodoDurum(db.Model):
    __tablename__ = 'TodoDurumlar'
    
    DurumID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    DurumAdi = db.Column(db.NVARCHAR(50), nullable=False)
    DurumAciklamasi = db.Column(db.NVARCHAR(200))
    Renk = db.Column(db.NVARCHAR(7), default='#007bff')  # Hex renk kodu
    Sira = db.Column(db.Integer, default=0)  # Sıralama için
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # İlişkiler
    firma = db.relationship('Firma', backref='todo_durumlar', lazy=True)
    
    def __repr__(self):
        return f'<TodoDurum {self.DurumAdi}>'

class Todo(db.Model):
    __tablename__ = 'Todos'
    
    TodoID = db.Column(db.Integer, primary_key=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    Baslik = db.Column(db.NVARCHAR(200), nullable=False)
    Aciklama = db.Column(db.Text)
    Oncelik = db.Column(db.Enum('Düşük', 'Orta', 'Yüksek', name='oncelik_enum'), default='Orta')
    DurumID = db.Column(db.Integer, db.ForeignKey('TodoDurumlar.DurumID'), nullable=True)  # Yeni alan
    Tip = db.Column(db.Enum('Kisisel', 'Randevu', name='todo_tip_enum'), default='Kisisel')  # Yeni alan
    BitisTarihi = db.Column(db.DateTime)
    HatirlatmaTarihi = db.Column(db.DateTime)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    TamamlanmaTarihi = db.Column(db.DateTime)
    # Müşteri bilgileri
    MusteriAdi = db.Column(db.NVARCHAR(100))
    MusteriSoyadi = db.Column(db.NVARCHAR(100))
    MusteriTelefon = db.Column(db.NVARCHAR(20))
    MusteriEmail = db.Column(db.NVARCHAR(100))
    # Randevu alanları
    RandevuTarihi = db.Column(db.Date)
    RandevuSaati = db.Column(db.NVARCHAR(10))  # HH:MM formatında
    RandevuDefteriID = db.Column(db.Integer, db.ForeignKey('RandevuDefterAyarlar.AyarID'), nullable=True)
    RandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'), nullable=True)
    AtananKullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=True)
    
    # İlişkiler
    kullanici = db.relationship('Kullanici', foreign_keys=[KullaniciID], backref='todos', lazy=True)
    atanan_kullanici = db.relationship('Kullanici', foreign_keys=[AtananKullaniciID], backref='atanan_todos', lazy=True)
    durum = db.relationship('TodoDurum', backref='todos', lazy=True)
    
    def __repr__(self):
        return f'<Todo {self.Baslik}>'

# E-posta gonderim yardimcisi
def send_email_simple(to_email: str, subject: str, body: str) -> bool:
    host = app.config['SMTP_HOST']
    user = app.config['SMTP_USER']
    password = app.config['SMTP_PASS']
    port = app.config['SMTP_PORT']
    use_tls = app.config['SMTP_USE_TLS']
    from_email = app.config['FROM_EMAIL'] or user

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
        if app.debug:
            print(f"E-posta gönderilemedi: {e}")
        return False

def send_email_with_firma_settings(firma_id: int, to_email: str, subject: str, body: str, from_name: str = None) -> bool:
    """Firma ayarlarını kullanarak e-posta gönder"""
    try:
        # Firma e-posta ayarlarını al
        email_ayar = FirmaEmailAyar.query.filter_by(FirmaID=firma_id, Aktif=True).first()
        
        if not email_ayar:
            # Sadece debug modunda hata mesajı yazdır
            if app.debug:
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
        if app.debug:
            print(f"E-posta başarıyla gönderildi: {to_email}")
        return True
        
    except Exception as e:
        # Sadece debug modunda hata mesajı yazdır
        if app.debug:
            print(f"E-posta gönderilemedi (firma ayarları): {e}")
        return False

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

def send_sms_custom(sms_ayar, phone_number: str, message: str) -> bool:
    """Özel API ile SMS gönder"""
    try:
        import requests
        
        if not sms_ayar.API_URL:
            print("Özel API URL tanımlanmamış")
            return False
        
        # Özel API için genel POST isteği
        data = {
            'phone': phone_number,
            'message': message,
            'sender': sms_ayar.GondericiAdi or 'CRM'
        }
        
        # API Key varsa ekle
        if sms_ayar.API_Key:
            data['api_key'] = sms_ayar.API_Key
        if sms_ayar.API_Secret:
            data['api_secret'] = sms_ayar.API_Secret
        
        response = requests.post(sms_ayar.API_URL, json=data, timeout=30)
        if response.status_code == 200:
            print(f"Özel API SMS başarıyla gönderildi: {phone_number}")
            return True
        else:
            print(f"Özel API SMS hatası: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Özel API SMS gönderim hatası: {e}")
        return False

def send_sms_corvass(sms_ayar, phone_number: str, message: str) -> bool:
    """Corvass API ile SMS gönder

    Not: API entegrasyonu sağlayıcı dökümantasyonuna göre değişebilir. Burada
    genel bir REST POST akışı uygulanmıştır. `API_URL` tanımlıysa o kullanılır,
    yoksa varsayılan bir uç noktaya istek gönderilir.
    """
    try:
        import requests

        api_url = (sms_ayar.API_URL or '').strip() or 'https://api.corvass.com/sms/send'

        # Corvass beklenen şema
        payload = {
            'Authentication': {
                'apikey': sms_ayar.API_Key or '',
                'apisecret': sms_ayar.API_Secret or ''
            },
            'message': message,
            'msisdnArray': [phone_number],
            'originator': sms_ayar.GondericiAdi or 'Corvass.NET',
            # İsteğe bağlı alanlar: gönderilmemişse sağlayıcı defaults kullanır
            # 'senddate': 'YYYY-MM-DD HH:mm:ss',
            # 'tags': [],
            # 'description': '',
            # 'messageType': 'B',
            # 'recipientType': 'TACIR'
        }

        headers = { 'Content-Type': 'application/json' }

        response = requests.post(api_url, json=payload, headers=headers, timeout=30)

        # Yanıtı ayrıntılı logla
        try:
            resp_json = response.json()
        except Exception:
            resp_json = {'raw': response.text}

        if 200 <= response.status_code < 300:
            # Corvass tarafı 200 içinde de hata kodu döndürebilir
            status_val = str(resp_json.get('status') or resp_json.get('result') or '').lower()
            success = 'success' in status_val or resp_json.get('success') is True
            if success:
                print(f"Corvass SMS OK: tel={phone_number} resp={resp_json}")
                return True
            else:
                print(f"Corvass SMS 200 ama başarısız: resp={resp_json}")
                return False
        else:
            print(f"Corvass SMS HTTP hata: {response.status_code} resp={resp_json}")
            return False

    except Exception as e:
        print(f"Corvass SMS gönderim hatası: {e}")
        return False

# Country State City API entegrasyonu
import requests
import json

# API Base URL
CSC_API_BASE = "https://api.countrystatecity.in/v1"

# API Key (ücretsiz tier için)
CSC_API_KEY = os.environ.get("CSC_API_KEY", "")  # https://countrystatecity.in/ adresinden alın

def _csc_headers():
    """CountryStateCity API için header üretir ve anahtardaki boşluk/çevresel boşlukları temizler."""
    key = (CSC_API_KEY or "").strip().replace(" ", "")
    return {"X-CSCAPI-KEY": key}

def get_countries():
    """Tüm ülkeleri getir"""
    try:
        headers = _csc_headers()
        url = f"{CSC_API_BASE}/countries"
        response = requests.get(url, headers=headers, timeout=10)
        if app.debug:
            print(f"CSC GET {url} -> {response.status_code}")
        if response.status_code == 200:
            countries = response.json()
            return [{"iso2": country["iso2"], "name": country["name"]} for country in countries]
        else:
            # Fallback: Statik liste
            if app.debug:
                try:
                    print(f"CSC countries non-200: {response.status_code} body={response.text[:200]}")
                except Exception:
                    pass
            return get_fallback_countries()
    except Exception as e:
        if app.debug:
            print(f"API hatası (ülkeler): {e}")
        return get_fallback_countries()

def get_states(country_iso2):
    """Belirli bir ülkenin eyaletlerini/şehirlerini getir"""
    try:
        headers = _csc_headers()
        url = f"{CSC_API_BASE}/countries/{country_iso2}/states"
        response = requests.get(url, headers=headers, timeout=10)
        if app.debug:
            print(f"CSC GET {url} -> {response.status_code}")
        if response.status_code == 200:
            states = response.json()
            return [{"iso2": state["iso2"], "name": state["name"]} for state in states]
        else:
            # Fallback: Statik veriler
            if app.debug:
                try:
                    print(f"CSC states non-200: {response.status_code} body={response.text[:200]}")
                except Exception:
                    pass
            return get_fallback_states(country_iso2)
    except Exception as e:
        if app.debug:
            print(f"API hatası (eyaletler): {e}")
        # Fallback: Statik veriler
        return get_fallback_states(country_iso2)

def get_cities(country_iso2, state_iso2=None):
    """Belirli bir ülke/eyaletin şehirlerini getir"""
    try:
        headers = _csc_headers()
        if state_iso2:
            url = f"{CSC_API_BASE}/countries/{country_iso2}/states/{state_iso2}/cities"
        else:
            url = f"{CSC_API_BASE}/countries/{country_iso2}/cities"
        
        response = requests.get(url, headers=headers, timeout=10)
        if app.debug:
            print(f"CSC GET {url} -> {response.status_code}")
        if response.status_code == 200:
            cities = response.json()
            return [{"name": city["name"]} for city in cities]
        else:
            # Fallback: Statik veriler
            if app.debug:
                try:
                    print(f"CSC cities non-200: {response.status_code} body={response.text[:200]}")
                except Exception:
                    pass
            return get_fallback_cities(country_iso2, state_iso2)
    except Exception as e:
        if app.debug:
            print(f"API hatası (şehirler): {e}")
        # Fallback: Statik veriler
        return get_fallback_cities(country_iso2, state_iso2)

def get_fallback_countries():
    """API çalışmazsa kullanılacak statik ülke listesi"""
    return [
        {"iso2": "TR", "name": "Turkey"},
        {"iso2": "US", "name": "United States"},
        {"iso2": "DE", "name": "Germany"},
        {"iso2": "FR", "name": "France"},
        {"iso2": "GB", "name": "United Kingdom"},
        {"iso2": "IT", "name": "Italy"},
        {"iso2": "ES", "name": "Spain"},
        {"iso2": "NL", "name": "Netherlands"},
        {"iso2": "BE", "name": "Belgium"},
        {"iso2": "AT", "name": "Austria"},
        {"iso2": "CH", "name": "Switzerland"},
        {"iso2": "CA", "name": "Canada"},
        {"iso2": "AU", "name": "Australia"},
        {"iso2": "JP", "name": "Japan"},
        {"iso2": "CN", "name": "China"},
        {"iso2": "KR", "name": "South Korea"},
        {"iso2": "RU", "name": "Russia"},
        {"iso2": "UA", "name": "Ukraine"},
        {"iso2": "PL", "name": "Poland"},
        {"iso2": "CZ", "name": "Czech Republic"},
        {"iso2": "HU", "name": "Hungary"},
        {"iso2": "RO", "name": "Romania"},
        {"iso2": "BG", "name": "Bulgaria"},
        {"iso2": "GR", "name": "Greece"},
        {"iso2": "PT", "name": "Portugal"},
        {"iso2": "SE", "name": "Sweden"},
        {"iso2": "NO", "name": "Norway"},
        {"iso2": "DK", "name": "Denmark"},
        {"iso2": "FI", "name": "Finland"},
        {"iso2": "IS", "name": "Iceland"},
        {"iso2": "IE", "name": "Ireland"},
        {"iso2": "NZ", "name": "New Zealand"},
        {"iso2": "BR", "name": "Brazil"},
        {"iso2": "AR", "name": "Argentina"},
        {"iso2": "MX", "name": "Mexico"},
        {"iso2": "ZA", "name": "South Africa"},
        {"iso2": "EG", "name": "Egypt"},
        {"iso2": "SA", "name": "Saudi Arabia"},
        {"iso2": "AE", "name": "United Arab Emirates"},
        {"iso2": "IL", "name": "Israel"},
        {"iso2": "IN", "name": "India"},
        {"iso2": "PK", "name": "Pakistan"},
        {"iso2": "BD", "name": "Bangladesh"},
        {"iso2": "TH", "name": "Thailand"},
        {"iso2": "VN", "name": "Vietnam"},
        {"iso2": "ID", "name": "Indonesia"},
        {"iso2": "MY", "name": "Malaysia"},
        {"iso2": "SG", "name": "Singapore"},
        {"iso2": "PH", "name": "Philippines"}
    ]

def get_fallback_states(country_iso2):
    """API çalışmazsa kullanılacak statik eyalet/şehir listesi"""
    if country_iso2 == "TR":
        # Türkiye illeri
        return [
            {"iso2": "01", "name": "Adana"}, {"iso2": "02", "name": "Adıyaman"}, {"iso2": "03", "name": "Afyonkarahisar"},
            {"iso2": "04", "name": "Ağrı"}, {"iso2": "05", "name": "Amasya"}, {"iso2": "06", "name": "Ankara"},
            {"iso2": "07", "name": "Antalya"}, {"iso2": "08", "name": "Artvin"}, {"iso2": "09", "name": "Aydın"},
            {"iso2": "10", "name": "Balıkesir"}, {"iso2": "11", "name": "Bilecik"}, {"iso2": "12", "name": "Bingöl"},
            {"iso2": "13", "name": "Bitlis"}, {"iso2": "14", "name": "Bolu"}, {"iso2": "15", "name": "Burdur"},
            {"iso2": "16", "name": "Bursa"}, {"iso2": "17", "name": "Çanakkale"}, {"iso2": "18", "name": "Çankırı"},
            {"iso2": "19", "name": "Çorum"}, {"iso2": "20", "name": "Denizli"}, {"iso2": "21", "name": "Diyarbakır"},
            {"iso2": "22", "name": "Edirne"}, {"iso2": "23", "name": "Elazığ"}, {"iso2": "24", "name": "Erzincan"},
            {"iso2": "25", "name": "Erzurum"}, {"iso2": "26", "name": "Eskişehir"}, {"iso2": "27", "name": "Gaziantep"},
            {"iso2": "28", "name": "Giresun"}, {"iso2": "29", "name": "Gümüşhane"}, {"iso2": "30", "name": "Hakkâri"},
            {"iso2": "31", "name": "Hatay"}, {"iso2": "32", "name": "Isparta"}, {"iso2": "33", "name": "Mersin"},
            {"iso2": "34", "name": "İstanbul"}, {"iso2": "35", "name": "İzmir"}, {"iso2": "36", "name": "Kars"},
            {"iso2": "37", "name": "Kastamonu"}, {"iso2": "38", "name": "Kayseri"}, {"iso2": "39", "name": "Kırklareli"},
            {"iso2": "40", "name": "Kırşehir"}, {"iso2": "41", "name": "Kocaeli"}, {"iso2": "42", "name": "Konya"},
            {"iso2": "43", "name": "Kütahya"}, {"iso2": "44", "name": "Malatya"}, {"iso2": "45", "name": "Manisa"},
            {"iso2": "46", "name": "Kahramanmaraş"}, {"iso2": "47", "name": "Mardin"}, {"iso2": "48", "name": "Muğla"},
            {"iso2": "49", "name": "Muş"}, {"iso2": "50", "name": "Nevşehir"}, {"iso2": "51", "name": "Niğde"},
            {"iso2": "52", "name": "Ordu"}, {"iso2": "53", "name": "Rize"}, {"iso2": "54", "name": "Sakarya"},
            {"iso2": "55", "name": "Samsun"}, {"iso2": "56", "name": "Siirt"}, {"iso2": "57", "name": "Sinop"},
            {"iso2": "58", "name": "Sivas"}, {"iso2": "59", "name": "Tekirdağ"}, {"iso2": "60", "name": "Tokat"},
            {"iso2": "61", "name": "Trabzon"}, {"iso2": "62", "name": "Tunceli"}, {"iso2": "63", "name": "Şanlıurfa"},
            {"iso2": "64", "name": "Uşak"}, {"iso2": "65", "name": "Van"}, {"iso2": "66", "name": "Yozgat"},
            {"iso2": "67", "name": "Zonguldak"}, {"iso2": "68", "name": "Aksaray"}, {"iso2": "69", "name": "Bayburt"},
            {"iso2": "70", "name": "Karaman"}, {"iso2": "71", "name": "Kırıkkale"}, {"iso2": "72", "name": "Batman"},
            {"iso2": "73", "name": "Şırnak"}, {"iso2": "74", "name": "Bartın"}, {"iso2": "75", "name": "Ardahan"},
            {"iso2": "76", "name": "Iğdır"}, {"iso2": "77", "name": "Yalova"}, {"iso2": "78", "name": "Karabük"},
            {"iso2": "79", "name": "Kilis"}, {"iso2": "80", "name": "Osmaniye"}, {"iso2": "81", "name": "Düzce"}
        ]
    elif country_iso2 == "US":
        # Amerika eyaletleri (önemli olanlar)
        return [
            {"iso2": "CA", "name": "California"}, {"iso2": "NY", "name": "New York"}, {"iso2": "TX", "name": "Texas"},
            {"iso2": "FL", "name": "Florida"}, {"iso2": "IL", "name": "Illinois"}, {"iso2": "PA", "name": "Pennsylvania"},
            {"iso2": "OH", "name": "Ohio"}, {"iso2": "GA", "name": "Georgia"}, {"iso2": "NC", "name": "North Carolina"},
            {"iso2": "MI", "name": "Michigan"}, {"iso2": "NJ", "name": "New Jersey"}, {"iso2": "VA", "name": "Virginia"},
            {"iso2": "WA", "name": "Washington"}, {"iso2": "AZ", "name": "Arizona"}, {"iso2": "MA", "name": "Massachusetts"},
            {"iso2": "TN", "name": "Tennessee"}, {"iso2": "IN", "name": "Indiana"}, {"iso2": "MO", "name": "Missouri"},
            {"iso2": "MD", "name": "Maryland"}, {"iso2": "WI", "name": "Wisconsin"}
        ]
    elif country_iso2 == "DE":
        # Almanya eyaletleri
        return [
            {"iso2": "BW", "name": "Baden-Württemberg"}, {"iso2": "BY", "name": "Bayern"}, {"iso2": "BE", "name": "Berlin"},
            {"iso2": "BB", "name": "Brandenburg"}, {"iso2": "HB", "name": "Bremen"}, {"iso2": "HH", "name": "Hamburg"},
            {"iso2": "HE", "name": "Hessen"}, {"iso2": "MV", "name": "Mecklenburg-Vorpommern"}, {"iso2": "NI", "name": "Niedersachsen"},
            {"iso2": "NW", "name": "Nordrhein-Westfalen"}, {"iso2": "RP", "name": "Rheinland-Pfalz"}, {"iso2": "SL", "name": "Saarland"},
            {"iso2": "SN", "name": "Sachsen"}, {"iso2": "ST", "name": "Sachsen-Anhalt"}, {"iso2": "SH", "name": "Schleswig-Holstein"},
            {"iso2": "TH", "name": "Thüringen"}
        ]
    else:
        return []

def get_fallback_cities(country_iso2, state_iso2=None):
    """API çalışmazsa kullanılacak statik şehir listesi"""
    if country_iso2 == "TR" and state_iso2:
        # Türkiye ilçeleri (sadece büyük şehirler için)
        city_data = {
            "01": [  # Adana
                {"name": "Seyhan"}, {"name": "Çukurova"}, {"name": "Yüreğir"}, {"name": "Sarıçam"},
                {"name": "Ceyhan"}, {"name": "Kozan"}, {"name": "İmamoğlu"}, {"name": "Karaisalı"},
                {"name": "Karataş"}, {"name": "Pozantı"}, {"name": "Saimbeyli"}, {"name": "Tufanbeyli"},
                {"name": "Yumurtalık"}, {"name": "Aladağ"}, {"name": "Feke"}
            ],
            "34": [  # İstanbul
                {"name": "Adalar"}, {"name": "Arnavutköy"}, {"name": "Ataşehir"}, {"name": "Avcılar"},
                {"name": "Bağcılar"}, {"name": "Bahçelievler"}, {"name": "Bakırköy"}, {"name": "Başakşehir"},
                {"name": "Bayrampaşa"}, {"name": "Beşiktaş"}, {"name": "Beykoz"}, {"name": "Beylikdüzü"},
                {"name": "Beyoğlu"}, {"name": "Büyükçekmece"}, {"name": "Çatalca"}, {"name": "Çekmeköy"},
                {"name": "Esenler"}, {"name": "Esenyurt"}, {"name": "Eyüpsultan"}, {"name": "Fatih"},
                {"name": "Gaziosmanpaşa"}, {"name": "Güngören"}, {"name": "Kadıköy"}, {"name": "Kağıthane"},
                {"name": "Kartal"}, {"name": "Küçükçekmece"}, {"name": "Maltepe"}, {"name": "Pendik"},
                {"name": "Sancaktepe"}, {"name": "Sarıyer"}, {"name": "Silivri"}, {"name": "Sultanbeyli"},
                {"name": "Sultangazi"}, {"name": "Şile"}, {"name": "Şişli"}, {"name": "Tuzla"},
                {"name": "Ümraniye"}, {"name": "Üsküdar"}, {"name": "Zeytinburnu"}
            ],
            "06": [  # Ankara
                {"name": "Akyurt"}, {"name": "Altındağ"}, {"name": "Ayaş"}, {"name": "Bala"},
                {"name": "Beypazarı"}, {"name": "Çamlıdere"}, {"name": "Çankaya"}, {"name": "Çubuk"},
                {"name": "Elmadağ"}, {"name": "Etimesgut"}, {"name": "Evren"}, {"name": "Gölbaşı"},
                {"name": "Güdül"}, {"name": "Haymana"}, {"name": "Kalecik"}, {"name": "Kazan"},
                {"name": "Keçiören"}, {"name": "Kızılcahamam"}, {"name": "Mamak"}, {"name": "Nallıhan"},
                {"name": "Polatlı"}, {"name": "Pursaklar"}, {"name": "Sincan"}, {"name": "Şereflikoçhisar"},
                {"name": "Yenimahalle"}
            ],
            "35": [  # İzmir
                {"name": "Aliağa"}, {"name": "Balçova"}, {"name": "Bayındır"}, {"name": "Bayraklı"},
                {"name": "Bergama"}, {"name": "Beydağ"}, {"name": "Bornova"}, {"name": "Buca"},
                {"name": "Çeşme"}, {"name": "Çiğli"}, {"name": "Dikili"}, {"name": "Foça"},
                {"name": "Gaziemir"}, {"name": "Güzelbahçe"}, {"name": "Karabağlar"}, {"name": "Karaburun"},
                {"name": "Karşıyaka"}, {"name": "Kemalpaşa"}, {"name": "Kınık"}, {"name": "Kiraz"},
                {"name": "Konak"}, {"name": "Menderes"}, {"name": "Menemen"}, {"name": "Narlıdere"},
                {"name": "Ödemiş"}, {"name": "Seferihisar"}, {"name": "Selçuk"}, {"name": "Tire"},
                {"name": "Torbalı"}, {"name": "Urla"}
            ],
            "07": [  # Antalya
                {"name": "Muratpaşa"}, {"name": "Kepez"}, {"name": "Konyaaltı"}, {"name": "Aksu"},
                {"name": "Döşemealtı"}, {"name": "Manavgat"}, {"name": "Alanya"}, {"name": "Serik"},
                {"name": "Kemer"}, {"name": "Gazipaşa"}, {"name": "Korkuteli"}, {"name": "Kumluca"},
                {"name": "Finike"}, {"name": "Kaş"}, {"name": "Elmalı"}, {"name": "Demre"},
                {"name": "Gündoğmuş"}, {"name": "İbradı"}
            ],
            "16": [  # Bursa
                {"name": "Osmangazi"}, {"name": "Yıldırım"}, {"name": "Nilüfer"}, {"name": "İnegöl"},
                {"name": "Gemlik"}, {"name": "Karacabey"}, {"name": "Mustafakemalpaşa"}, {"name": "Mudanya"},
                {"name": "Gürsu"}, {"name": "Kestel"}, {"name": "Yenişehir"}, {"name": "Orhangazi"},
                {"name": "Orhaneli"}, {"name": "Keles"}, {"name": "Harmancık"}, {"name": "Büyükorhan"}
            ]
        }
        return city_data.get(state_iso2, [])
    elif country_iso2 == "US" and state_iso2:
        # Amerika şehirleri (önemli eyaletler için)
        city_data = {
            "CA": [  # California
                {"name": "Los Angeles"}, {"name": "San Diego"}, {"name": "San Jose"}, {"name": "San Francisco"},
                {"name": "Fresno"}, {"name": "Sacramento"}, {"name": "Long Beach"}, {"name": "Oakland"},
                {"name": "Bakersfield"}, {"name": "Anaheim"}, {"name": "Santa Ana"}, {"name": "Riverside"},
                {"name": "Stockton"}, {"name": "Irvine"}, {"name": "Chula Vista"}, {"name": "Fremont"},
                {"name": "San Bernardino"}, {"name": "Modesto"}, {"name": "Fontana"}, {"name": "Oxnard"}
            ],
            "NY": [  # New York
                {"name": "New York City"}, {"name": "Buffalo"}, {"name": "Rochester"}, {"name": "Yonkers"},
                {"name": "Syracuse"}, {"name": "Albany"}, {"name": "New Rochelle"}, {"name": "Mount Vernon"},
                {"name": "Schenectady"}, {"name": "Utica"}, {"name": "White Plains"}, {"name": "Hempstead"},
                {"name": "Troy"}, {"name": "Niagara Falls"}, {"name": "Binghamton"}, {"name": "Freeport"},
                {"name": "Valley Stream"}, {"name": "Long Beach"}, {"name": "Rome"}, {"name": "Ithaca"}
            ],
            "TX": [  # Texas
                {"name": "Houston"}, {"name": "San Antonio"}, {"name": "Dallas"}, {"name": "Austin"},
                {"name": "Fort Worth"}, {"name": "El Paso"}, {"name": "Arlington"}, {"name": "Corpus Christi"},
                {"name": "Plano"}, {"name": "Lubbock"}, {"name": "Laredo"}, {"name": "Garland"},
                {"name": "Irving"}, {"name": "Amarillo"}, {"name": "Grand Prairie"}, {"name": "Brownsville"},
                {"name": "Pasadena"}, {"name": "Mesquite"}, {"name": "McKinney"}, {"name": "McAllen"}
            ],
            "FL": [  # Florida
                {"name": "Jacksonville"}, {"name": "Miami"}, {"name": "Tampa"}, {"name": "Orlando"},
                {"name": "St. Petersburg"}, {"name": "Hialeah"}, {"name": "Tallahassee"}, {"name": "Fort Lauderdale"},
                {"name": "Port St. Lucie"}, {"name": "Cape Coral"}, {"name": "Pembroke Pines"}, {"name": "Hollywood"},
                {"name": "Miramar"}, {"name": "Gainesville"}, {"name": "Coral Springs"}, {"name": "Miami Gardens"},
                {"name": "Clearwater"}, {"name": "Palm Bay"}, {"name": "West Palm Beach"}, {"name": "Pompano Beach"}
            ]
        }
        return city_data.get(state_iso2, [])
    elif country_iso2 == "DE" and state_iso2:
        # Almanya şehirleri (önemli eyaletler için)
        city_data = {
            "BY": [  # Bayern
                {"name": "München"}, {"name": "Nürnberg"}, {"name": "Augsburg"}, {"name": "Regensburg"},
                {"name": "Würzburg"}, {"name": "Ingolstadt"}, {"name": "Fürth"}, {"name": "Erlangen"},
                {"name": "Bayreuth"}, {"name": "Bamberg"}, {"name": "Aschaffenburg"}, {"name": "Landshut"},
                {"name": "Kempten"}, {"name": "Rosenheim"}, {"name": "Schweinfurt"}, {"name": "Passau"},
                {"name": "Hof"}, {"name": "Freising"}, {"name": "Straubing"}, {"name": "Dachau"}
            ],
            "NW": [  # Nordrhein-Westfalen
                {"name": "Köln"}, {"name": "Düsseldorf"}, {"name": "Dortmund"}, {"name": "Essen"},
                {"name": "Duisburg"}, {"name": "Bochum"}, {"name": "Wuppertal"}, {"name": "Bielefeld"},
                {"name": "Bonn"}, {"name": "Münster"}, {"name": "Gelsenkirchen"}, {"name": "Mönchengladbach"},
                {"name": "Aachen"}, {"name": "Krefeld"}, {"name": "Oberhausen"}, {"name": "Hagen"},
                {"name": "Hamm"}, {"name": "Mülheim"}, {"name": "Leverkusen"}, {"name": "Solingen"}
            ],
            "BW": [  # Baden-Württemberg
                {"name": "Stuttgart"}, {"name": "Mannheim"}, {"name": "Karlsruhe"}, {"name": "Freiburg"},
                {"name": "Heidelberg"}, {"name": "Heilbronn"}, {"name": "Ulm"}, {"name": "Pforzheim"},
                {"name": "Reutlingen"}, {"name": "Esslingen"}, {"name": "Tübingen"}, {"name": "Ludwigsburg"},
                {"name": "Konstanz"}, {"name": "Villingen-Schwenningen"}, {"name": "Aalen"}, {"name": "Sindelfingen"},
                {"name": "Schwäbisch Gmünd"}, {"name": "Friedrichshafen"}, {"name": "Offenburg"}, {"name": "Göppingen"}
            ]
        }
        return city_data.get(state_iso2, [])
    else:
        return []

# Dakikada bir calisan basit hatirlatma is parcacigi
def reminder_worker():
    with app.app_context():
        while True:
            try:
                now = datetime.now()
                
                # Sadece gelecekteki randevular için hatırlatma kontrol et (24 saat içinde)
                future_limit = now + timedelta(hours=24)
                
                # Gonderilmemis ve epostasi olan hatirlatmalari getir
                # Sadece gelecekteki randevular için kontrol et
                pending = db.session.query(RandevuHatirlatma).join(Randevu).filter(
                    RandevuHatirlatma.Gonderildi == False,
                    RandevuHatirlatma.RecipientEmail != None,
                    RandevuHatirlatma.RecipientEmail != '',
                    Randevu.RandevuTarihi >= now,  # Gelecekteki randevular
                    Randevu.RandevuTarihi <= future_limit  # 24 saat içindeki randevular
                ).all()

                # SMS hatirlatmalarini da kontrol et
                pending_sms = db.session.query(RandevuSMSHatirlatma).join(Randevu).filter(
                    RandevuSMSHatirlatma.Gonderildi == False,
                    RandevuSMSHatirlatma.RecipientPhone != None,
                    RandevuSMSHatirlatma.RecipientPhone != '',
                    Randevu.RandevuTarihi >= now,
                    Randevu.RandevuTarihi <= future_limit
                ).all()

                # Eğer gönderilecek hiçbir hatırlatma yoksa, bekle
                if not pending and not pending_sms:
                    import time
                    time.sleep(60)
                    continue

                for h in pending:
                    r = h.randevu
                    if not r:
                        continue
                    # Ne zaman gonderilmeli?
                    target_send_time = r.RandevuTarihi - timedelta(minutes=h.MinutesBefore)
                    # UTC varsayimi: RandevuTarihi zaten naive ise karşılaştırma naive-naive
                    if target_send_time <= now and not h.Gonderildi:
                        subject = f"Randevu Hatırlatma - {r.RandevuTarihi.strftime('%d.%m.%Y %H:%M')}"
                        body = (
                            f"Merhaba,\n\n"
                            f"{r.RandevuTarihi.strftime('%d.%m.%Y %H:%M')} tarihinde bir randevunuz bulunmaktadır.\n"
                            f"Referans: {r.RandevuBaslik}\n"
                            f"Süre: {r.RandevuSuresi or 60} dk\n\n"
                            f"Bu bir otomatik bilgilendirmedir."
                        )
                        # Önce firma ayarlarını kullan, yoksa genel ayarları kullan
                        ok = send_email_with_firma_settings(r.FirmaID, h.RecipientEmail, subject, body)
                        if not ok:
                            # Firma ayarları başarısız olursa genel ayarları dene
                            ok = send_email_simple(h.RecipientEmail, subject, body)
                        if ok:
                            h.Gonderildi = True
                            h.GonderimTarihi = datetime.now()
                            db.session.commit()

                # SMS hatirlatmalarini isleme
                for s in pending_sms:
                    r = s.randevu
                    if not r:
                        continue
                    target_send_time = r.RandevuTarihi - timedelta(minutes=s.MinutesBefore)
                    if target_send_time <= now and not s.Gonderildi:
                        # Firma SMS ayar metnini kullan
                        sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=s.FirmaID, Aktif=True).first()
                        sms_text = (sms_ayar.VarsayilanSMSMetni if sms_ayar and sms_ayar.VarsayilanSMSMetni else
                                    "Merhaba {MUSTERI_ADI}, {RANDEVU_TARIH} tarihindeki randevunuzu hatırlatırız.")
                        try:
                            defter_adi = r.defter.DefterAdi if r.defter else ''
                        except Exception:
                            defter_adi = ''
                        # Ad + Soyad birlestir
                        try:
                            if r.musteri and r.musteri.MusteriSoyadi:
                                full_name = f"{r.musteri.MusteriAdi} {r.musteri.MusteriSoyadi}".strip()
                            else:
                                full_name = (r.MusteriAdi or '').strip()
                        except Exception:
                            full_name = (r.MusteriAdi or '').strip()

                        sms_text = sms_text.replace('{MUSTERI_ADI}', full_name or '-')\
                                           .replace('{RANDEVU_TARIH}', r.RandevuTarihi.strftime('%d.%m.%Y %H:%M'))\
                                           .replace('{DEFTER_ADI}', defter_adi)

                        ok = send_sms_with_firma_settings(s.FirmaID, s.RecipientPhone, sms_text)
                        if ok:
                            s.Gonderildi = True
                            s.GonderimTarihi = datetime.now()
                            db.session.commit()
            except Exception as e:
                print(f"Hatirlatma isci hatasi: {e}")
            finally:
                # 60 saniye bekle
                import time
                time.sleep(60)

# API: Ülke/Şehir/İlçe verileri
@app.route('/api/countries')
@login_required
def api_countries():
    """Tüm ülkeleri getir"""
    try:
        countries = get_countries()
        return jsonify(countries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/states/<country_iso2>')
def api_states(country_iso2):
    """Belirli bir ülkenin eyaletlerini/şehirlerini getir"""
    try:
        states = get_states(country_iso2)
        return jsonify(states)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cities/<country_iso2>')
@app.route('/api/cities/<country_iso2>/<state_iso2>')
def api_cities(country_iso2, state_iso2=None):
    """Belirli bir ülke/eyaletin şehirlerini getir"""
    try:
        cities = get_cities(country_iso2, state_iso2)
        return jsonify(cities)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API: Bildirimler
@app.route('/api/bildirimler')
@login_required
def api_bildirimler():
    # Only return unread notifications (hatırlatma bildirimleri hariç)
    unread_q = Bildirim.query.filter(
        Bildirim.KullaniciID == session['user_id'], 
        Bildirim.Okundu == False,
        Bildirim.Tip != 'todo_reminder'  # Hatırlatma bildirimlerini hariç tut
    )
    unread = unread_q.count()
    items = unread_q.order_by(Bildirim.OlusturmaTarihi.desc()).limit(50).all()

    data = [
        {
            'id': b.BildirimID,
            'metin': b.Metin,
            'okundu': b.Okundu,
            'tip': b.Tip,
            'randevu_id': b.IlgiliRandevuID,
            'tarih': b.OlusturmaTarihi.strftime('%d.%m.%Y %H:%M')
        }
        for b in items
    ]
    return jsonify({'success': True, 'items': data, 'unread': unread})

@app.route('/api/bildirimler/okundu', methods=['POST'])
@login_required
def api_bildirim_okundu():
    ids = request.json.get('ids', []) if request.is_json else []
    if not isinstance(ids, list):
        return jsonify({'success': False, 'message': 'ids listesi bekleniyor'}), 400
    Bildirim.query.filter(Bildirim.KullaniciID==session['user_id'], Bildirim.BildirimID.in_(ids)).update({'Okundu': True}, synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/bildirimler/sil', methods=['POST'])
@login_required
def api_bildirim_sil():
    ids = request.json.get('ids', []) if request.is_json else []
    if not isinstance(ids, list):
        return jsonify({'success': False, 'message': 'ids listesi bekleniyor'}), 400
    
    try:
        # Belirtilen ID'lerdeki bildirimleri sil
        Bildirim.query.filter(
            Bildirim.BildirimID.in_(ids),
            Bildirim.KullaniciID == session['user_id']
        ).delete(synchronize_session=False)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/bildirimler/tumunu-sil', methods=['POST'])
@login_required
def api_bildirim_tumunu_sil():
    try:
        # Kullanıcının tüm bildirimlerini sil
        Bildirim.query.filter_by(KullaniciID=session['user_id']).delete()
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/today-reminders')
@login_required
def api_today_reminders():
    """Bugünkü hatırlatmaları getir"""
    try:
        bugun = datetime.now().date()
        
        # Bugün hatırlatma tarihi olan ve tamamlanmamış todoları bul (SQL Server için CAST kullan)
        reminders = Todo.query.filter(
            db.cast(Todo.HatirlatmaTarihi, db.Date) == bugun,
            Todo.KullaniciID == session['user_id']
        ).all()
        
        # Tamamlanmamış todoları filtrele
        reminders = [todo for todo in reminders if not todo.durum or todo.durum.DurumAdi != 'Tamamlandı']
        
        reminder_data = []
        for todo in reminders:
            # Görev olup olmadığını (durum bağlılığına göre) belirle
            gorev_mi = True if todo.DurumID else False
            # Durum rengi yoksa önceliğe göre renk ata
            default_color = '#ffc107'
            if not (todo.durum and getattr(todo.durum, 'Renk', None)):
                if todo.Oncelik == 'Yüksek':
                    default_color = '#dc3545'
                elif todo.Oncelik == 'Orta':
                    default_color = '#ffc107'
                elif todo.Oncelik == 'Düşük':
                    default_color = '#28a745'

            reminder_data.append({
                'id': todo.TodoID,
                'baslik': todo.Baslik,
                'aciklama': todo.Aciklama,
                'hatirlatma_tarihi': todo.HatirlatmaTarihi.strftime('%d.%m.%Y'),
                'durum': todo.durum.DurumAdi if todo.durum else 'Durum Yok',
                'durum_rengi': (todo.durum.Renk if todo.durum and getattr(todo.durum, 'Renk', None) else default_color),
                'gorev_mi': gorev_mi,
                'oncelik': todo.Oncelik
            })
        
        return jsonify({
            'success': True,
            'reminders': reminder_data,
            'count': len(reminder_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/clear-session', methods=['POST'])
def api_clear_session():
    """Tarayıcı kapanma durumunda oturumu temizle"""
    try:
        if 'user_id' in session:
            user_id = session.get('user_id')
            token = session.get('session_token')
            kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
            if kayit and (not token or kayit.SessionToken == token):
                db.session.delete(kayit)
                db.session.commit()
    except Exception:
        db.session.rollback()
    return '', 204  # No content response

@app.route('/api/update-last-seen', methods=['POST'])
def api_update_last_seen():
    """Son görülme zamanını güncelle"""
    try:
        if 'user_id' in session:
            user_id = session.get('user_id')
            token = session.get('session_token')
            kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
            if kayit and (not token or kayit.SessionToken == token):
                kayit.SonGorulmeZamani = datetime.now()
                db.session.commit()
    except Exception:
        db.session.rollback()
    return '', 204  # No content response

# Yardimci: Kullanici ve randevu ayni firmada mi?
def _assert_same_firm_for_permission(kullanici_id: int, randevu_id: int) -> bool:
    kull = Kullanici.query.get(kullanici_id)
    rand = Randevu.query.get(randevu_id)
    if not kull or not rand:
        return False
    return kull.FirmaID == rand.FirmaID

@app.route('/api/session/check')
def api_session_check():
    """Session'ın aktif olup olmadığını kontrol et"""
    if 'user_id' in session:
        return jsonify({"success": True, "authenticated": True}), 200
    else:
        return jsonify({"success": False, "authenticated": False}), 401

@app.route('/set_language/<language>')
def set_language(language=None):
    if language and language in app.config['LANGUAGES']:
        session['language'] = language
        # Babel locale'ini manuel olarak güncelle
        from flask_babel import refresh
        refresh()
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Her giriş ekranı açılışında olası bekleyen durumları temizle
    if request.method == 'GET':
        for key in list(session.keys()):
            if key.startswith('pending_'):
                session.pop(key, None)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Kullanıcı adı ve şifre gereklidir!', 'error')
            return render_template('login.html')
        
        # Kullanici kontrolu
        user = Kullanici.query.filter_by(KullaniciAdi=username, Aktif=True).first()
        
        # Şifre kontrolü - hash'lenmiş şifreyi kontrol et
        if user and user.Sifre and check_password_hash(user.Sifre, password):
            # Eski oturumları temizle (24 saatten eski)
            eski_oturumlar = AktifOturum.query.filter(
                AktifOturum.SonGorulmeZamani < datetime.now() - timedelta(hours=24)
            ).all()
            for oturum in eski_oturumlar:
                db.session.delete(oturum)
            db.session.commit()
            
            # Tek-oturum kontrolü
            mevcut = AktifOturum.query.filter_by(KullaniciID=user.KullaniciID).first()
            if mevcut:
                # Mevcut oturum varsa, kullanıcıya seçenek sun
                session['pending_user_id'] = user.KullaniciID
                session['pending_username'] = user.KullaniciAdi
                session['pending_user_name'] = f"{user.Ad} {user.Soyad}"
                session['pending_firma_id'] = user.FirmaID
                session['pending_is_admin'] = user.Admin
                session['pending_raporlar_modulu'] = user.RaporlarModulu
                session['pending_ayarlar_modulu'] = user.AyarlarModulu
                session['pending_log_modulu'] = user.LogModulu
                
                # Firma bilgisini al
                firma = Firma.query.filter_by(FirmaID=user.FirmaID).first()
                session['pending_firma_adi'] = firma.FirmaAdi if firma else 'Bilinmeyen Firma'
                
                # Session'ı kaydet
                session.permanent = True
                
                flash('Bu kullanıcı zaten giriş yapmış. Mevcut oturumu kapatıp yeni giriş yapmak istiyor musunuz?', 'warning')
                return render_template('login.html', show_force_logout=True)

            # Firma bilgisini al
            firma = Firma.query.filter_by(FirmaID=user.FirmaID).first()
            
            session['user_id'] = user.KullaniciID
            session['username'] = user.KullaniciAdi
            session['user_name'] = f"{user.Ad} {user.Soyad}"
            session['firma_id'] = user.FirmaID
            session['firma_adi'] = firma.FirmaAdi if firma else 'Bilinmeyen Firma'
            session['is_admin'] = user.Admin
            session['raporlar_modulu'] = user.RaporlarModulu
            session['ayarlar_modulu'] = user.AyarlarModulu
            session['log_modulu'] = user.LogModulu

            # Oturum kaydı oluştur - önce mevcut kaydı kontrol et
            token = secrets.token_hex(16)
            session['session_token'] = token
            
            # Mevcut kaydı kontrol et
            mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user.KullaniciID).first()
            if mevcut_kayit:
                # Mevcut kaydı güncelle
                mevcut_kayit.SessionToken = token
                mevcut_kayit.ClientIP = get_client_ip()
                mevcut_kayit.UserAgent = request.headers.get('User-Agent', '')
                mevcut_kayit.SonGorulmeZamani = datetime.now()
                mevcut_kayit.GirisZamani = datetime.now()  # Yeni giriş zamanı
            else:
                # Yeni kayıt oluştur
                kayit = AktifOturum(
                    KullaniciID=user.KullaniciID,
                    SessionToken=token,
                    ClientIP=get_client_ip(),
                    UserAgent=request.headers.get('User-Agent', '')
                )
                db.session.add(kayit)
            db.session.commit()
            
            # Zorunlu parola değişimi: 123 ise yönlendir
            if user.Sifre and check_password_hash(user.Sifre, '123'):
                session['must_change_password'] = True
                flash('Lütfen güvenlik için şifrenizi değiştirin.', 'warning')
                return redirect(url_for('sifre_degistir'))
            flash('Başarıyla giriş yaptınız!', 'success')
            
            # Giriş işlemi loglanmıyor
            
            return redirect(url_for('dashboard'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'error')
    
    return render_template('login.html')

@app.route('/force-logout', methods=['POST'])
def force_logout():
    """Mevcut oturumu kapat ve yeni giriş yap"""
    # Form verilerinden veya session'dan al
    user_id = request.form.get('pending_user_id') or session.get('pending_user_id')
    
    if not user_id:
        flash('Geçersiz işlem - Pending user ID bulunamadı', 'error')
        return redirect(url_for('login'))
    
    # Tüm aktif oturumları kapat (güvenlik için)
    mevcut_oturumlar = AktifOturum.query.filter_by(KullaniciID=user_id).all()
    
    for oturum in mevcut_oturumlar:
        db.session.delete(oturum)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('Oturum kapatma hatası', 'error')
        return redirect(url_for('login'))
    
    # Pending verileri form'dan veya session'dan al
    pending_user_id = request.form.get('pending_user_id') or session.get('pending_user_id')
    pending_username = request.form.get('pending_username') or session.get('pending_username')
    pending_user_name = request.form.get('pending_user_name') or session.get('pending_user_name')
    pending_firma_id = request.form.get('pending_firma_id') or session.get('pending_firma_id')
    pending_firma_adi = request.form.get('pending_firma_adi') or session.get('pending_firma_adi')
    pending_is_admin = request.form.get('pending_is_admin') or session.get('pending_is_admin')
    pending_raporlar_modulu = request.form.get('pending_raporlar_modulu') or session.get('pending_raporlar_modulu')
    pending_ayarlar_modulu = request.form.get('pending_ayarlar_modulu') or session.get('pending_ayarlar_modulu')
    pending_log_modulu = request.form.get('pending_log_modulu') or session.get('pending_log_modulu')
    
    # Session'ı tamamen temizle
    session.clear()
    
    # Yeni oturum oluştur
    session['user_id'] = pending_user_id
    session['username'] = pending_username
    session['user_name'] = pending_user_name
    session['firma_id'] = pending_firma_id
    session['firma_adi'] = pending_firma_adi
    session['is_admin'] = pending_is_admin
    session['raporlar_modulu'] = pending_raporlar_modulu
    session['ayarlar_modulu'] = pending_ayarlar_modulu
    session['log_modulu'] = pending_log_modulu
    
    # Oturum kaydı oluştur - önce mevcut kaydı kontrol et
    token = secrets.token_hex(16)
    session['session_token'] = token
    
    # Mevcut kaydı kontrol et (yukarıda silinmiş olabilir ama race condition için tekrar kontrol et)
    mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
    if mevcut_kayit:
        # Mevcut kaydı güncelle
        mevcut_kayit.SessionToken = token
        mevcut_kayit.ClientIP = get_client_ip()
        mevcut_kayit.UserAgent = request.headers.get('User-Agent', '')
        mevcut_kayit.SonGorulmeZamani = datetime.now()
        mevcut_kayit.GirisZamani = datetime.now()  # Yeni giriş zamanı
    else:
        # Yeni kayıt oluştur
        kayit = AktifOturum(
            KullaniciID=user_id,
            SessionToken=token,
            ClientIP=get_client_ip(),
            UserAgent=request.headers.get('User-Agent', '')
        )
        db.session.add(kayit)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Oturum kaydı hatası (force-logout): {e}")
        flash('Oturum oluşturma hatası', 'error')
        return redirect(url_for('login'))
    
    # Zorunlu parola değişimi kontrolü
    user = Kullanici.query.get(user_id)
    if user and user.Sifre == '123':
        session['must_change_password'] = True
        flash('Lütfen güvenlik için şifrenizi değiştirin.', 'warning')
        return redirect(url_for('sifre_degistir'))
    
    flash('Başarıyla giriş yaptınız!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/clear-all-sessions', methods=['POST'])
def clear_all_sessions():
    """Tüm aktif oturumları temizle (admin için)"""
    print("Clear all sessions başladı")
    
    try:
        # Tüm aktif oturumları sil
        count = AktifOturum.query.count()
        print(f"Silinecek toplam oturum sayısı: {count}")
        
        AktifOturum.query.delete()
        db.session.commit()
        
        print("Tüm oturumlar başarıyla temizlendi")
        flash('Tüm aktif oturumlar temizlendi. Şimdi giriş yapabilirsiniz.', 'success')
        
    except Exception as e:
        print(f"Oturum temizleme hatası: {e}")
        db.session.rollback()
        flash('Oturum temizleme hatası oluştu.', 'error')
    
    return redirect(url_for('login'))

@app.route('/sifre-degistir', methods=['GET', 'POST'])
def sifre_degistir():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        yeni = request.form.get('yeni')
        yeni2 = request.form.get('yeni2')
        if not yeni or not yeni2:
            flash('Lütfen şifre alanlarını doldurun', 'error')
        elif yeni != yeni2:
            flash('Şifreler eşleşmiyor', 'error')
        elif not is_password_strong(yeni):
            flash('Şifre en az 8 haneli olmalı ve büyük/küçük harf, sayı ve özel karakter içermeli', 'error')
        else:
            u = Kullanici.query.get(session['user_id'])
            if not u:
                flash('Kullanıcı bulunamadı', 'error')
                return redirect(url_for('logout'))
            u.Sifre = yeni
            db.session.commit()
            session.pop('must_change_password', None)
            flash('Şifreniz güncellendi', 'success')
            return redirect(url_for('dashboard'))
    return render_template('sifre_degistir.html')

@app.route('/logout')
def logout():
    # Aktif oturumu temizle
    try:
        if 'user_id' in session:
            from sqlalchemy import and_
            u_id = session.get('user_id')
            token = session.get('session_token')
            kayit = AktifOturum.query.filter_by(KullaniciID=u_id).first()
            if kayit and (not token or kayit.SessionToken == token):
                db.session.delete(kayit)
                db.session.commit()
    except Exception:
        db.session.rollback()
    # Çıkış işlemi loglanmıyor
    
    session.clear()
    flash('Başarıyla çıkış yaptınız!', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Kullanici randevularini getir
    if session.get('is_admin', False):
        # Admin tum randevulari gorebilir
        randevular = Randevu.query.filter_by(FirmaID=session['firma_id']).order_by(Randevu.RandevuTarihi.desc()).limit(10).all()
    else:
        # Normal kullanici sadece yetkili oldugu randevulari gorebilir
        randevular = db.session.query(Randevu).join(RandevuYetki).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id']
        ).order_by(Randevu.RandevuTarihi.desc()).limit(10).all()
    
    # Yapılacaklar (Kişisel) verilerini getir - Durum bilgisi ile birlikte
    user_todos = db.session.query(Todo).outerjoin(TodoDurum, Todo.DurumID == TodoDurum.DurumID).filter(
        Todo.KullaniciID == session['user_id'], 
        Todo.Tip == 'Kisisel'
    ).order_by(Todo.Oncelik.desc(), Todo.OlusturmaTarihi.desc()).limit(5).all()
    
    # Görevler (Randevu) verilerini getir
    user_gorevler = Todo.query.filter_by(KullaniciID=session['user_id'], Tip='Randevu').order_by(
        Todo.Oncelik.desc(), Todo.OlusturmaTarihi.desc()
    ).limit(5).all()
    
    # Yapılacaklar (Kişisel) istatistikleri
    toplam_todo = Todo.query.filter_by(KullaniciID=session['user_id'], Tip='Kisisel').count()
    
    # Yapılacaklar durum istatistikleri için join kullan
    tamamlanan_todo = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Kisisel',
        TodoDurum.DurumAdi == 'Tamamlandı'
    ).count()
    
    beklemede_todo = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Kisisel',
        TodoDurum.DurumAdi == 'Beklemede'
    ).count()
    
    devam_eden_todo = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Kisisel',
        TodoDurum.DurumAdi == 'Devam Ediyor'
    ).count()
    
    # Görevler (Randevu) istatistikleri - Durumlara göre
    toplam_gorev = Todo.query.filter_by(KullaniciID=session['user_id'], Tip='Randevu').count()
    
    # Firma bazlı tüm durumları getir
    gorev_durumlar = TodoDurum.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(TodoDurum.Sira).all()
    
    # Her durum için kullanıcının görev sayısını hesapla
    gorev_durum_istatistikleri = []
    for durum in gorev_durumlar:
        sayi = db.session.query(Todo).join(TodoDurum).filter(
            Todo.KullaniciID == session['user_id'],
            Todo.Tip == 'Randevu',
            TodoDurum.DurumID == durum.DurumID
        ).count()
        gorev_durum_istatistikleri.append({
            'durum': durum,
            'sayi': sayi
        })
    
    # Eski istatistikler (geriye dönük uyumluluk için)
    tamamlanan_gorev = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Randevu',
        TodoDurum.DurumAdi == 'Tamamlandı'
    ).count()
    
    beklemede_gorev = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Randevu',
        TodoDurum.DurumAdi == 'Beklemede'
    ).count()
    
    devam_eden_gorev = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Randevu',
        TodoDurum.DurumAdi == 'Devam Ediyor'
    ).count()
    
    # Okunmamiş bildirim sayısı
    unread_count = Bildirim.query.filter_by(KullaniciID=session['user_id'], Okundu=False).count()
    
    return render_template('dashboard.html', 
                         randevular=randevular, 
                         unread_count=unread_count,
                         user_todos=user_todos,
                         user_gorevler=user_gorevler,
                         toplam_todo=toplam_todo,
                         tamamlanan_todo=tamamlanan_todo,
                         beklemede_todo=beklemede_todo,
                         devam_eden_todo=devam_eden_todo,
                         toplam_gorev=toplam_gorev,
                         tamamlanan_gorev=tamamlanan_gorev,
                         beklemede_gorev=beklemede_gorev,
                         devam_eden_gorev=devam_eden_gorev,
                         gorev_durum_istatistikleri=gorev_durum_istatistikleri)


@app.route('/profil')
@login_required
def profil():
    u = Kullanici.query.get(session['user_id'])
    if not u:
        flash('Kullanıcı bulunamadı', 'error')
        return redirect(url_for('logout'))
    unread_count = Bildirim.query.filter_by(KullaniciID=session['user_id'], Okundu=False).count()
    return render_template('profil.html', kullanici=u, unread_count=unread_count)

# Ayarlar Ana Sayfa
@app.route('/ayarlar')
@login_required
def ayarlar():
    # Modül izin kontrolü
    if not session.get('is_admin', False) and not session.get('ayarlar_modulu', False):
        flash('Bu sayfaya erişim yetkiniz yok', 'error')
        return redirect(url_for('dashboard'))
    unread_count = Bildirim.query.filter_by(KullaniciID=session['user_id'], Okundu=False).count()
    return render_template('ayarlar/index.html', unread_count=unread_count)

# Firma Ayarlari
@app.route('/ayarlar/firmalar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def ayarlar_firmalar():
    if request.method == 'POST':
        firma_adi = request.form.get('firma_adi')
        firma_kodu = request.form.get('firma_kodu')
        if not firma_adi or not firma_kodu:
            flash('Firma adı ve kodu zorunludur', 'error')
        else:
            if Firma.query.filter_by(FirmaKodu=firma_kodu).first():
                flash('Bu firma kodu zaten kullanılıyor', 'error')
            else:
                f = Firma(FirmaAdi=firma_adi, FirmaKodu=firma_kodu,
                          Adres=request.form.get('adres') or None,
                          Telefon=request.form.get('telefon') or None,
                          Email=request.form.get('email') or None)
                db.session.add(f)
                db.session.commit()
                flash('Firma eklendi', 'success')
        return redirect(url_for('ayarlar_firmalar'))

    firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
    return render_template('ayarlar/firmalar.html', firmalar=firmalar)

@app.route('/ayarlar/firmalar/sil/<int:firma_id>', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_firma_sil(firma_id):
    firma = Firma.query.get_or_404(firma_id)
    # Basit kontrol: Kullanıcı veya randevu bağlı ise silme (örnek amaçlı engelleme)
    if Kullanici.query.filter_by(FirmaID=firma.FirmaID).first() or Randevu.query.filter_by(FirmaID=firma.FirmaID).first():
        flash('Kullanıcı veya randevu bağlı firmalar silinemez', 'error')
    else:
        db.session.delete(firma)
        db.session.commit()
        flash('Firma silindi', 'success')
    return redirect(url_for('ayarlar_firmalar'))

@app.route('/ayarlar/firmalar/guncelle', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_firma_guncelle():
    try:
        firma_id = request.form.get('firma_id', type=int)
        if not firma_id:
            flash('Firma ID bulunamadı', 'error')
            return redirect(url_for('ayarlar_firmalar'))
        
        firma = Firma.query.get_or_404(firma_id)
        
        # Firma kodunun benzersizliğini kontrol et (kendi kodu hariç)
        existing_firma = Firma.query.filter(
            Firma.FirmaKodu == request.form['firma_kodu'],
            Firma.FirmaID != firma_id
        ).first()
        
        if existing_firma:
            flash('Bu firma kodu zaten kullanılıyor', 'error')
            return redirect(url_for('ayarlar_firmalar'))
        
        # Firma bilgilerini güncelle
        firma.FirmaAdi = request.form['firma_adi']
        firma.FirmaKodu = request.form['firma_kodu']
        firma.Adres = request.form.get('adres', '')
        firma.Telefon = request.form.get('telefon', '')
        firma.Email = request.form.get('email', '')
        firma.GuncellemeTarihi = datetime.now()
        
        db.session.commit()
        flash('Firma başarıyla güncellendi', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Firma güncellenirken hata: {str(e)}', 'error')
    
    return redirect(url_for('ayarlar_firmalar'))

# Kullanici Ayarlari
@app.route('/ayarlar/kullanicilar', methods=['GET', 'POST'])
@login_required
@admin_required
def ayarlar_kullanicilar():
    if request.method == 'POST':
        kullanici_adi = request.form.get('kullanici_adi')
        email = request.form.get('email')
        firma_id = request.form.get('firma_id', type=int)
        sifre = request.form.get('sifre') or '123'
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        
        # Admin değilse sadece kendi firmasına kullanıcı ekleyebilir
        if not session.get('is_admin', False):
            firma_id = session.get('firma_id')
        
        if not all([kullanici_adi, email, firma_id, ad, soyad]):
            flash('Tüm alanlar zorunludur', 'error')
        elif Kullanici.query.filter((Kullanici.KullaniciAdi==kullanici_adi) | (Kullanici.Email==email)).first():
            flash('Kullanıcı adı veya e-posta mevcut', 'error')
        else:
            # Modül izinlerini al
            raporlar_modulu = 'raporlar_modulu' in request.form
            ayarlar_modulu = 'ayarlar_modulu' in request.form
            log_modulu = 'log_modulu' in request.form
            
            # Varsayılan şifre 123 ve ilk girişte değişim zorunlu olacak
            u = Kullanici(KullaniciAdi=kullanici_adi, Email=email, FirmaID=firma_id,
                          Sifre=sifre or '123', Ad=ad, Soyad=soyad, Aktif=True,
                          RaporlarModulu=raporlar_modulu, AyarlarModulu=ayarlar_modulu, LogModulu=log_modulu)
            db.session.add(u)
            db.session.commit()

            # Fotoğraf işle (opsiyonel)
            try:
                # Öncelik: kırpılmış Base64 data
                cropped_b64 = request.form.get('foto_cropped')
                if cropped_b64 and cropped_b64.startswith('data:image'):
                    import base64
                    header, b64data = cropped_b64.split(',', 1)
                    raw = base64.b64decode(b64data)
                    from PIL import Image
                    import io
                    img = Image.open(io.BytesIO(raw)).convert('RGB')
                    os.makedirs(os.path.join('static', 'uploads', 'users'), exist_ok=True)
                    out_path = os.path.join('static', 'uploads', 'users', f'user_{u.KullaniciID}.jpg')
                    img.save(out_path, format='JPEG', quality=85, optimize=True)
                else:
                    foto = request.files.get('foto')
                    if foto and foto.filename:
                        from PIL import Image
                        import io
                        # Boyut kontrolü (sunucu tarafı)
                        foto.seek(0, io.SEEK_END)
                        size = foto.tell()
                        foto.seek(0)
                        if size <= 512 * 1024:
                            img = Image.open(foto.stream).convert('RGB')
                            # Kare kırp ve küçült (maks 256x256)
                            w, h = img.size
                            side = min(w, h)
                            left = (w - side) // 2
                            top = (h - side) // 2
                            img = img.crop((left, top, left + side, top + side))
                            img.thumbnail((256, 256))
                            # Kaydet
                            os.makedirs(os.path.join('static', 'uploads', 'users'), exist_ok=True)
                            out_path = os.path.join('static', 'uploads', 'users', f'user_{u.KullaniciID}.jpg')
                            img.save(out_path, format='JPEG', quality=85, optimize=True)
                        else:
                            flash('Fotoğraf 512KB üzeri olduğu için yüklenmedi.', 'warning')
            except Exception:
                flash('Fotoğraf işlenemedi.', 'warning')
            flash('Kullanıcı eklendi', 'success')
        return redirect(url_for('ayarlar_kullanicilar'))

    # Admin ise tüm firmaları, değilse sadece kendi firmasını göster
    if session.get('is_admin', False):
        firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
        kullanicilar = Kullanici.query.order_by(Kullanici.KullaniciID.desc()).limit(100).all()
    else:
        firmalar = Firma.query.filter_by(FirmaID=session.get('firma_id')).all()
        kullanicilar = Kullanici.query.filter_by(FirmaID=session.get('firma_id')).order_by(Kullanici.KullaniciID.desc()).limit(100).all()
    
    return render_template('ayarlar/kullanicilar.html', firmalar=firmalar, kullanicilar=kullanicilar)

@app.route('/ayarlar/kullanicilar/duzenle/<int:kullanici_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def ayarlar_kullanici_duzenle(kullanici_id):
    kullanici = Kullanici.query.get_or_404(kullanici_id)
    
    # Admin değilse sadece kendi firmasının kullanıcılarını düzenleyebilir
    if not session.get('is_admin', False) and kullanici.FirmaID != session.get('firma_id'):
        flash('Bu kullanıcıyı düzenleme yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_kullanicilar'))
    
    if request.method == 'POST':
        kullanici_adi = request.form.get('kullanici_adi')
        email = request.form.get('email')
        firma_id = request.form.get('firma_id', type=int)
        sifre = request.form.get('sifre')
        sifre2 = request.form.get('sifre2')
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        aktif = 'aktif' in request.form
        raporlar_modulu = 'raporlar_modulu' in request.form
        ayarlar_modulu = 'ayarlar_modulu' in request.form
        log_modulu = 'log_modulu' in request.form
        
        # Admin değilse firma değiştiremez
        if not session.get('is_admin', False):
            firma_id = kullanici.FirmaID
        
        if not all([kullanici_adi, email, firma_id, ad, soyad]):
            flash('Tüm alanlar zorunludur', 'error')
        else:
            # Kullanıcı adı ve email kontrolü (kendisi hariç)
            existing_user = Kullanici.query.filter(
                (Kullanici.KullaniciAdi == kullanici_adi) | (Kullanici.Email == email),
                Kullanici.KullaniciID != kullanici_id
            ).first()
            
            if existing_user:
                flash('Kullanıcı adı veya e-posta başka bir kullanıcı tarafından kullanılıyor', 'error')
            else:
                # Güncelleme
                kullanici.KullaniciAdi = kullanici_adi
                kullanici.Email = email
                kullanici.FirmaID = firma_id
                kullanici.Ad = ad
                kullanici.Soyad = soyad
                kullanici.Aktif = aktif
                kullanici.RaporlarModulu = raporlar_modulu
                kullanici.AyarlarModulu = ayarlar_modulu
                kullanici.LogModulu = log_modulu
                
                # Şifre güncelleme (sadece girilmişse) + doğrulama ve karmaşıklık
                if sifre or sifre2:
                    if sifre != sifre2:
                        flash('Şifreler eşleşmiyor', 'error')
                        return redirect(url_for('ayarlar_kullanici_duzenle', kullanici_id=kullanici_id))
                    if not is_password_strong(sifre):
                        flash('Şifre en az 8 haneli olmalı ve büyük/küçük harf, sayı ve özel karakter içermeli', 'error')
                        return redirect(url_for('ayarlar_kullanici_duzenle', kullanici_id=kullanici_id))
                    kullanici.Sifre = sifre
                
                db.session.commit()

                # Fotoğraf güncelle (opsiyonel)
                try:
                    cropped_b64 = request.form.get('foto_cropped')
                    if cropped_b64 and cropped_b64.startswith('data:image'):
                        import base64
                        header, b64data = cropped_b64.split(',', 1)
                        raw = base64.b64decode(b64data)
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(raw)).convert('RGB')
                        os.makedirs(os.path.join('static', 'uploads', 'users'), exist_ok=True)
                        out_path = os.path.join('static', 'uploads', 'users', f'user_{kullanici.KullaniciID}.jpg')
                        img.save(out_path, format='JPEG', quality=85, optimize=True)
                    else:
                        foto = request.files.get('foto')
                        if foto and foto.filename:
                            from PIL import Image
                            import io
                            foto.seek(0, io.SEEK_END)
                            size = foto.tell()
                            foto.seek(0)
                            if size <= 512 * 1024:
                                img = Image.open(foto.stream).convert('RGB')
                                w, h = img.size
                                side = min(w, h)
                                left = (w - side) // 2
                                top = (h - side) // 2
                                img = img.crop((left, top, left + side, top + side))
                                img.thumbnail((256, 256))
                                os.makedirs(os.path.join('static', 'uploads', 'users'), exist_ok=True)
                                out_path = os.path.join('static', 'uploads', 'users', f'user_{kullanici.KullaniciID}.jpg')
                                img.save(out_path, format='JPEG', quality=85, optimize=True)
                            else:
                                flash('Fotoğraf 512KB üzeri olduğu için yüklenmedi.', 'warning')
                except Exception:
                    flash('Fotoğraf işlenemedi.', 'warning')
                flash('Kullanıcı güncellendi', 'success')
                return redirect(url_for('ayarlar_kullanicilar'))
    
    # Admin ise tüm firmaları, değilse sadece kendi firmasını göster
    if session.get('is_admin', False):
        firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
    else:
        firmalar = Firma.query.filter_by(FirmaID=session.get('firma_id')).all()
    
    return render_template('ayarlar/kullanici_duzenle.html', kullanici=kullanici, firmalar=firmalar)

@app.route('/ayarlar/kullanicilar/sil/<int:kullanici_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_kullanici_sil(kullanici_id):
    if kullanici_id == session.get('user_id'):
        flash('Kendi hesabınızı silemezsiniz', 'error')
        return redirect(url_for('ayarlar_kullanicilar'))
    
    u = Kullanici.query.get_or_404(kullanici_id)
    
    # Admin değilse sadece kendi firmasının kullanıcılarını silebilir
    if not session.get('is_admin', False) and u.FirmaID != session.get('firma_id'):
        flash('Bu kullanıcıyı silme yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_kullanicilar'))
    
    db.session.delete(u)
    db.session.commit()
    flash('Kullanıcı silindi', 'success')
    return redirect(url_for('ayarlar_kullanicilar'))

# Kullanıcı şifre sıfırla (123)
@app.route('/ayarlar/kullanicilar/sifre-sifirla/<int:kullanici_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_kullanici_sifre_sifirla(kullanici_id):
    kullanici = Kullanici.query.get_or_404(kullanici_id)
    # Admin değilse sadece kendi firmasının kullanıcılarını sıfırlayabilir
    if not session.get('is_admin', False) and kullanici.FirmaID != session.get('firma_id'):
        flash('Bu kullanıcı için işlem yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_kullanicilar'))
    kullanici.Sifre = '123'
    db.session.commit()
    flash('Şifre 123 olarak sıfırlandı. İlk girişte değişiklik istenecek.', 'success')
    return redirect(url_for('ayarlar_kullanici_duzenle', kullanici_id=kullanici_id))

# Randevu Defteri Ayarlari
@app.route('/ayarlar/defter', methods=['GET', 'POST'])
@login_required
@super_admin_required
def ayarlar_defter():
    if request.method == 'POST':
        ayar_id = request.form.get('ayar_id', type=int)
        firma_id = request.form.get('firma_id', type=int)
        defter_adi = request.form.get('defter_adi') or 'Varsayilan Defter'
        calisma_gunleri = ','.join(request.form.getlist('calisma_gunleri')) or '1,2,3,4,5'
        baslangic = request.form.get('baslangic') or '09:00'
        bitis = request.form.get('bitis') or '18:00'
        slot = request.form.get('slot', type=int) or 30

        if ayar_id:
            ayar = RandevuDefterAyar.query.get_or_404(ayar_id)
            ayar.FirmaID = firma_id
            ayar.DefterAdi = defter_adi
            ayar.CalismaGunleri = calisma_gunleri
            ayar.BaslangicSaati = baslangic
            ayar.BitisSaati = bitis
            ayar.SlotDakika = slot
        else:
            ayar = RandevuDefterAyar(
                FirmaID=firma_id,
                DefterAdi=defter_adi,
                CalismaGunleri=calisma_gunleri,
                BaslangicSaati=baslangic,
                BitisSaati=bitis,
                SlotDakika=slot
            )
            db.session.add(ayar)
        db.session.commit()

        # Kaydet ile birlikte blok girildiyse ekle
        t1 = request.form.get('blok_tarih1')
        t2 = request.form.get('blok_tarih2')
        s1 = request.form.get('blok_saat1')
        s2 = request.form.get('blok_saat2')
        aciklama = request.form.get('blok_aciklama')
        if t1 or t2 or s1 or s2 or (aciklama and aciklama.strip()):
            try:
                bas_t = datetime.strptime(t1, '%Y-%m-%d').date() if t1 else None
                bit_t = datetime.strptime(t2, '%Y-%m-%d').date() if t2 else None
            except Exception:
                flash('Blok tarih formatı geçersiz', 'error')
                return redirect(url_for('ayarlar_defter'))
            if not bas_t:
                flash('Blok için başlangıç tarihi zorunludur', 'error')
                return redirect(url_for('ayarlar_defter'))
            if bit_t and bit_t < bas_t:
                flash('Blok bitiş tarihi başlangıçtan önce olamaz', 'error')
                return redirect(url_for('ayarlar_defter'))
            try:
                yeni_blok = RandevuDefterBlok(
                    FirmaID=ayar.FirmaID,
                    DefterID=ayar.AyarID,
                    BaslangicTarih=bas_t,
                    BitisTarih=bit_t,
                    SaatBaslangic=s1 or None,
                    SaatBitis=s2 or None,
                    Aciklama=(aciklama or '').strip() or None,
                    Aktif=True
                )
                db.session.add(yeni_blok)
                db.session.commit()
                flash('Blok eklendi', 'success')
            except Exception as e:
                db.session.rollback()
                print('Blok ekleme hatası:', e)
                flash('Blok eklenemedi', 'error')

        flash('Randevu defteri ayarları kaydedildi', 'success')
        return redirect(url_for('ayarlar_defter'))

    firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
    ayarlar_list = RandevuDefterAyar.query.order_by(RandevuDefterAyar.AyarID.desc()).all()
    bloklar = RandevuDefterBlok.query.filter_by(FirmaID=session['firma_id']).order_by(RandevuDefterBlok.BlokID.desc()).all()
    
    # Mevcut firmanın kategorilerini getir
    kategoriler = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id']
    ).filter(MusteriKategori.Aktif == 1).order_by(MusteriKategori.KategoriID.asc()).all()
    
    return render_template('ayarlar/defter.html', firmalar=firmalar, ayarlar_list=ayarlar_list, kategoriler=kategoriler, bloklar=bloklar)

@app.route('/ayarlar/defter/blok/ekle', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_defter_blok_ekle():
    firma_id = session['firma_id']
    defter_id = request.form.get('blok_defter_id', type=int)
    t1 = request.form.get('blok_tarih1')
    t2 = request.form.get('blok_tarih2')
    s1 = request.form.get('blok_saat1')
    s2 = request.form.get('blok_saat2')
    aciklama = request.form.get('blok_aciklama', '')
    try:
        bas_t = datetime.strptime(t1, '%Y-%m-%d').date() if t1 else None
        bit_t = datetime.strptime(t2, '%Y-%m-%d').date() if t2 else None
    except Exception:
        flash('Tarih formatı geçersiz', 'error')
        return redirect(url_for('ayarlar_defter'))
    if not bas_t:
        flash('Başlangıç tarihi zorunludur', 'error')
        return redirect(url_for('ayarlar_defter'))
    if bit_t and bit_t < bas_t:
        flash('Bitiş tarihi başlangıçtan önce olamaz', 'error')
        return redirect(url_for('ayarlar_defter'))

    blok = RandevuDefterBlok(
        FirmaID=firma_id,
        DefterID=defter_id,
        BaslangicTarih=bas_t,
        BitisTarih=bit_t,
        SaatBaslangic=s1 or None,
        SaatBitis=s2 or None,
        Aciklama=aciklama,
        Aktif=True
    )
    db.session.add(blok)
    db.session.commit()
    flash('Saat kapatma bloğu eklendi', 'success')
    return redirect(url_for('ayarlar_defter'))

@app.route('/ayarlar/defter/blok/sil/<int:blok_id>', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_defter_blok_sil(blok_id: int):
    b = RandevuDefterBlok.query.filter_by(BlokID=blok_id, FirmaID=session['firma_id']).first()
    if not b:
        flash('Blok bulunamadı', 'error')
        return redirect(url_for('ayarlar_defter'))
    db.session.delete(b)
    db.session.commit()
    flash('Blok silindi', 'success')
    return redirect(url_for('ayarlar_defter'))

@app.route('/ayarlar/defter/pasiflestir/<int:ayar_id>', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_defter_pasiflestir(ayar_id: int):
    ayar = RandevuDefterAyar.query.get_or_404(ayar_id)
    ayar.Aktif = not (ayar.Aktif if ayar.Aktif is not None else True)
    db.session.commit()
    flash('Randevu defteri durumu güncellendi', 'success')
    return redirect(url_for('ayarlar_defter'))

# Kategori Yönetimi
@app.route('/ayarlar/kategori/ekle', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_kategori_ekle():
    kategori_adi = request.form.get('kategori_adi')
    kategori_renk = request.form.get('kategori_renk', '#007bff')
    kategori_aciklama = request.form.get('kategori_aciklama', '')
    kategori_aktif = request.form.get('kategori_aktif') == 'on'
    
    if not kategori_adi:
        flash(gettext('Category name is required'), 'error')
        return redirect(url_for('ayarlar_defter'))
    
    # Aynı isimde kategori var mı kontrol et
    existing = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id'],
        KategoriAdi=kategori_adi
    ).first()
    
    if existing:
        flash(gettext('A category with this name already exists'), 'error')
        return redirect(url_for('ayarlar_defter'))
    
    kategori = MusteriKategori(
        FirmaID=session['firma_id'],
        KategoriAdi=kategori_adi,
        Renk=kategori_renk,
        Aciklama=kategori_aciklama,
        Aktif=kategori_aktif
    )
    
    db.session.add(kategori)
    db.session.commit()
    
    flash(gettext('Category added successfully'), 'success')
    return redirect(url_for('ayarlar_defter'))

@app.route('/ayarlar/kategori/guncelle', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_kategori_guncelle():
    kategori_id = request.form.get('kategori_id', type=int)
    kategori_adi = request.form.get('kategori_adi')
    kategori_renk = request.form.get('kategori_renk', '#007bff')
    kategori_aciklama = request.form.get('kategori_aciklama', '')
    kategori_aktif = request.form.get('kategori_aktif') == 'on'
    
    if not kategori_id or not kategori_adi:
        flash('Kategori bilgileri eksik', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    kategori = MusteriKategori.query.filter_by(
        KategoriID=kategori_id,
        FirmaID=session['firma_id']
    ).first()
    
    if not kategori:
        flash('Kategori bulunamadı', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    # Aynı isimde başka kategori var mı kontrol et
    existing = MusteriKategori.query.filter(
        MusteriKategori.FirmaID == session['firma_id'],
        MusteriKategori.KategoriAdi == kategori_adi,
        MusteriKategori.KategoriID != kategori_id
    ).first()
    
    if existing:
        flash(gettext('A category with this name already exists'), 'error')
        return redirect(url_for('ayarlar_defter'))
    
    kategori.KategoriAdi = kategori_adi
    kategori.Renk = kategori_renk
    kategori.Aciklama = kategori_aciklama
    kategori.Aktif = kategori_aktif
    
    db.session.commit()
    
    flash(gettext('Category updated successfully'), 'success')
    return redirect(url_for('ayarlar_defter'))

@app.route('/ayarlar/kategori/sil')
@login_required
@super_admin_required
def ayarlar_kategori_sil():
    kategori_id = request.args.get('id', type=int)
    
    if not kategori_id:
        flash('Kategori ID gerekli', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    kategori = MusteriKategori.query.filter_by(
        KategoriID=kategori_id,
        FirmaID=session['firma_id']
    ).first()
    
    if not kategori:
        flash('Kategori bulunamadı', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    # Bu kategoriyi kullanan müşteri var mı kontrol et
    musteri_count = Musteri.query.filter_by(KategoriID=kategori_id).count()
    
    if musteri_count > 0:
        flash(f'Bu kategoriyi kullanan {musteri_count} müşteri var. Önce müşterilerin kategorilerini değiştirin.', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    db.session.delete(kategori)
    db.session.commit()
    
    flash(gettext('Category deleted successfully'), 'success')
    return redirect(url_for('ayarlar_defter'))

# Randevu Referans Ayarlari
@app.route('/ayarlar/referanslar', methods=['GET', 'POST'])
@login_required
@admin_required
def ayarlar_referanslar():
    if request.method == 'POST':
        firma_id = request.form.get('firma_id', type=int)
        ad = request.form.get('ad')
        
        # Admin değilse sadece kendi firmasına referans ekleyebilir
        if not session.get('is_admin', False):
            firma_id = session.get('firma_id')
        
        if not firma_id or not ad:
            flash('Firma ve referans adı zorunludur', 'error')
        else:
            ref = RandevuReferans(FirmaID=firma_id, Ad=ad)
            db.session.add(ref)
            db.session.commit()
            flash('Referans eklendi', 'success')
        return redirect(url_for('ayarlar_referanslar'))

    # Admin ise tüm firmaları, değilse sadece kendi firmasını göster
    if session.get('is_admin', False):
        firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
        refs = db.session.query(RandevuReferans).order_by(RandevuReferans.ReferansID.desc()).limit(200).all()
    else:
        firmalar = Firma.query.filter_by(FirmaID=session.get('firma_id')).all()
        refs = db.session.query(RandevuReferans).filter_by(FirmaID=session.get('firma_id')).order_by(RandevuReferans.ReferansID.desc()).limit(200).all()
    
    return render_template('ayarlar/referanslar.html', firmalar=firmalar, referanslar=refs)

@app.route('/ayarlar/referanslar/sil/<int:ref_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_referans_sil(ref_id):
    ref = RandevuReferans.query.get_or_404(ref_id)
    
    # Admin değilse sadece kendi firmasının referanslarını silebilir
    if not session.get('is_admin', False) and ref.FirmaID != session.get('firma_id'):
        flash('Bu referansı silme yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_referanslar'))
    
    db.session.delete(ref)
    db.session.commit()
    flash('Referans silindi', 'success')
    return redirect(url_for('ayarlar_referanslar'))

# Randevu İşlemleri
@app.route('/ayarlar/islemler', methods=['GET', 'POST'])
@login_required
@admin_required
def ayarlar_islemler():
    if request.method == 'POST':
        # Firma, oturumdaki kullanıcıdan alınır (formdan değil)
        firma_id = session.get('firma_id')
        defter_id = request.form.get('defter_id', type=int)
        islem_adi = request.form.get('islem_adi')
        islem_aciklamasi = ''
        islem_suresi = 60
        islem_ucreti = 0.00
        
        # Her durumda sadece kendi firmasına eklenir
        if not firma_id:
            flash('Firma bilgisi bulunamadı', 'error')
            return redirect(url_for('ayarlar_islemler'))
            # Non-admin için defter doğrulaması: kendi firmasına ait değilse temizle
            if defter_id:
                dft = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=firma_id, Aktif=True).first()
                if not dft:
                    defter_id = None
        
        if not firma_id or not islem_adi:
            flash('Firma ve işlem adı zorunludur', 'error')
            return redirect(url_for('ayarlar_islemler'))
        # Defter seçimi zorunlu
        if not defter_id:
            flash('Defter seçimi zorunludur', 'error')
            return redirect(url_for('ayarlar_islemler'))
        # Seçilen defter firmaya ait mi?
        dft = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=firma_id, Aktif=True).first()
        if not dft:
            flash('Seçilen defter bulunamadı veya firmaya ait değil', 'error')
            return redirect(url_for('ayarlar_islemler'))
        else:
            islem = RandevuIslem(
                FirmaID=firma_id,
                DefterID=defter_id,
                IslemAdi=islem_adi,
                Aktif=True,
                OlusturmaTarihi=datetime.now()
            )
            db.session.add(islem)
            db.session.commit()
            flash('İşlem eklendi', 'success')
        return redirect(url_for('ayarlar_islemler'))

    # Listeleme de oturumdaki firmaya göre yapılır
    aktif_firma_id = session.get('firma_id')
    islemler = db.session.query(RandevuIslem).filter_by(FirmaID=aktif_firma_id).order_by(RandevuIslem.IslemID.desc()).limit(200).all()
    defterler = RandevuDefterAyar.query.filter_by(FirmaID=aktif_firma_id, Aktif=True).order_by(RandevuDefterAyar.DefterAdi).all()
    
    return render_template('ayarlar/islemler.html', islemler=islemler, defterler=defterler)

@app.route('/ayarlar/islemler/guncelle/<int:islem_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_islem_guncelle(islem_id: int):
    firma_id = session.get('firma_id')
    if not firma_id:
        flash('Firma bilgisi bulunamadı', 'error')
        return redirect(url_for('ayarlar_islemler'))

    islem = RandevuIslem.query.filter_by(IslemID=islem_id, FirmaID=firma_id).first()
    if not islem:
        flash('İşlem bulunamadı veya yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_islemler'))

    islem_adi = request.form.get('islem_adi', '').strip()
    defter_id = request.form.get('defter_id', type=int)
    if not islem_adi or not defter_id:
        flash('İşlem adı ve defter zorunludur', 'error')
        return redirect(url_for('ayarlar_islemler'))

    dft = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=firma_id, Aktif=True).first()
    if not dft:
        flash('Seçilen defter bulunamadı veya firmaya ait değil', 'error')
        return redirect(url_for('ayarlar_islemler'))

    islem.IslemAdi = islem_adi
    islem.DefterID = defter_id
    db.session.commit()
    flash('İşlem güncellendi', 'success')
    return redirect(url_for('ayarlar_islemler'))

@app.route('/ayarlar/islemler/sil/<int:islem_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_islem_sil(islem_id):
    islem = RandevuIslem.query.get_or_404(islem_id)
    
    # Admin değilse sadece kendi firmasının işlemlerini silebilir
    if not session.get('is_admin', False) and islem.FirmaID != session.get('firma_id'):
        flash('Bu işlemi silme yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_islemler'))
    
    db.session.delete(islem)
    db.session.commit()
    flash('İşlem silindi', 'success')
    return redirect(url_for('ayarlar_islemler'))

# E-posta Ayarları
@app.route('/ayarlar/email')
@login_required
@admin_required
def ayarlar_email():
    # Admin ise firma seçimi yapabilir
    if session.get('is_admin', False):
        selected_firma_id = request.args.get('firma_id', type=int)
        if selected_firma_id:
            firma = Firma.query.get(selected_firma_id)
            if not firma:
                flash('Seçilen firma bulunamadı!', 'error')
                return redirect(url_for('ayarlar'))
        else:
            # İlk firma varsayılan olarak seçili
            firma = Firma.query.first()
            if not firma:
                flash('Hiç firma bulunamadı!', 'error')
                return redirect(url_for('ayarlar'))
            selected_firma_id = firma.FirmaID
        
        tum_firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
        email_ayar = FirmaEmailAyar.query.filter_by(FirmaID=selected_firma_id).first()
        
        return render_template('ayarlar/email.html', 
                             email_ayar=email_ayar, 
                             firma=firma, 
                             tum_firmalar=tum_firmalar,
                             selected_firma_id=selected_firma_id,
                             is_admin=True)
    else:
        # Normal kullanıcı sadece kendi firmasını görebilir
        firma = Firma.query.get(session['firma_id'])
        if not firma:
            flash('Firma bilgisi bulunamadı!', 'error')
            return redirect(url_for('ayarlar'))
        
        email_ayar = FirmaEmailAyar.query.filter_by(FirmaID=session['firma_id']).first()
        return render_template('ayarlar/email.html', 
                             email_ayar=email_ayar, 
                             firma=firma,
                             is_admin=False)

@app.route('/ayarlar/email/ekle', methods=['POST'])
@login_required
@admin_required
def ayarlar_email_ekle():
    try:
        # Admin ise seçilen firmayı kullan, değilse kendi firmasını
        if session.get('is_admin', False):
            firma_id = request.form.get('firma_id', type=int) or session['firma_id']
        else:
            firma_id = session['firma_id']
        
        email_ayar = FirmaEmailAyar(
            FirmaID=firma_id,
            SMTP_Sunucu=request.form['smtp_sunucu'],
            SMTP_Port=int(request.form['smtp_port']),
            KullaniciAdi=request.form['kullanici_adi'],
            Sifre=request.form['sifre'],
            SSL_Kullan='ssl_kullan' in request.form,
            VarsayilanGonderenAdi=request.form.get('gonderen_adi', ''),
            VarsayilanGonderenEmail=request.form.get('gonderen_email', ''),
            VarsayilanEmailKonu=request.form.get('varsayilan_email_konu', ''),
            VarsayilanEmailMetni=request.form.get('varsayilan_email_metni', ''),
            Aktif='aktif' in request.form
        )
        db.session.add(email_ayar)
        db.session.commit()
        flash('E-posta ayarları eklendi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'E-posta ayarları eklenirken hata: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_email', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_email'))

@app.route('/ayarlar/email/guncelle/<int:ayar_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_email_guncelle(ayar_id):
    try:
        # Admin ise herhangi bir firmanın ayarını güncelleyebilir
        if session.get('is_admin', False):
            email_ayar = FirmaEmailAyar.query.get_or_404(ayar_id)
        else:
            email_ayar = FirmaEmailAyar.query.filter_by(EmailAyarID=ayar_id, FirmaID=session['firma_id']).first_or_404()
        
        email_ayar.SMTP_Sunucu = request.form['smtp_sunucu']
        email_ayar.SMTP_Port = int(request.form['smtp_port'])
        email_ayar.KullaniciAdi = request.form['kullanici_adi']
        email_ayar.Sifre = request.form['sifre']
        email_ayar.SSL_Kullan = 'ssl_kullan' in request.form
        email_ayar.VarsayilanGonderenAdi = request.form.get('gonderen_adi', '')
        email_ayar.VarsayilanGonderenEmail = request.form.get('gonderen_email', '')
        email_ayar.VarsayilanEmailKonu = request.form.get('varsayilan_email_konu', '')
        email_ayar.VarsayilanEmailMetni = request.form.get('varsayilan_email_metni', '')
        email_ayar.Aktif = 'aktif' in request.form
        db.session.commit()
        flash('E-posta ayarları güncellendi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'E-posta ayarları güncellenirken hata: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_email', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_email'))

@app.route('/ayarlar/email/sil/<int:ayar_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_email_sil(ayar_id):
    try:
        # Admin ise herhangi bir firmanın ayarını silebilir
        if session.get('is_admin', False):
            email_ayar = FirmaEmailAyar.query.get_or_404(ayar_id)
        else:
            email_ayar = FirmaEmailAyar.query.filter_by(EmailAyarID=ayar_id, FirmaID=session['firma_id']).first_or_404()
        
        db.session.delete(email_ayar)
        db.session.commit()
        flash('E-posta ayarları silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'E-posta ayarları silinirken hata: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_email', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_email'))

# SMS Ayarları
@app.route('/ayarlar/sms')
@login_required
@admin_required
def ayarlar_sms():
    # Admin ise firma seçimi yapabilir
    if session.get('is_admin', False):
        selected_firma_id = request.args.get('firma_id', type=int)
        if selected_firma_id:
            firma = Firma.query.get(selected_firma_id)
            if not firma:
                flash('Seçilen firma bulunamadı!', 'error')
                return redirect(url_for('ayarlar'))
        else:
            # İlk firma varsayılan olarak seçili
            firma = Firma.query.first()
            if not firma:
                flash('Hiç firma bulunamadı!', 'error')
                return redirect(url_for('ayarlar'))
            selected_firma_id = firma.FirmaID
        
        tum_firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
        sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=selected_firma_id).first()
        
        return render_template('ayarlar/sms.html', 
                             sms_ayar=sms_ayar, 
                             firma=firma, 
                             tum_firmalar=tum_firmalar,
                             selected_firma_id=selected_firma_id,
                             is_admin=True)
    else:
        # Normal kullanıcı sadece kendi firmasını görebilir
        firma = Firma.query.get(session['firma_id'])
        if not firma:
            flash('Firma bilgisi bulunamadı!', 'error')
            return redirect(url_for('ayarlar'))
        
        sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=session['firma_id']).first()
        return render_template('ayarlar/sms.html', 
                             sms_ayar=sms_ayar, 
                             firma=firma,
                             is_admin=False)

@app.route('/ayarlar/sms/ekle', methods=['POST'])
@login_required
@admin_required
def ayarlar_sms_ekle():
    try:
        # Admin ise formdan gelen firma_id'yi kullan
        hedef_firma_id = session['firma_id']
        try:
            if session.get('is_admin', False) and request.form.get('firma_id'):
                hedef_firma_id = int(request.form.get('firma_id'))
        except Exception:
            pass

        sms_ayar = FirmaSMSAyar(
            FirmaID=hedef_firma_id,
            SMSFirmasi=request.form['sms_firmasi'],
            API_Key=request.form.get('api_key', ''),
            API_Secret=request.form.get('api_secret', ''),
            KullaniciAdi=request.form.get('kullanici_adi', ''),
            Sifre=request.form.get('sifre', ''),
            GondericiAdi=request.form.get('gonderici_adi', ''),
            API_URL=request.form.get('api_url', ''),
            VarsayilanSMSMetni=request.form.get('varsayilan_sms_metni', ''),
            SMSGonderOnCreate=('sms_on_create' in request.form),
            SMSGonder24SaatOnce=('sms_24h' in request.form),
            Aktif='aktif' in request.form
        )
        db.session.add(sms_ayar)
        db.session.commit()
        flash('SMS ayarları eklendi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'SMS ayarları eklenirken hata: {str(e)}', 'error')
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_sms', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_sms'))

@app.route('/ayarlar/sms/guncelle/<int:ayar_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_sms_guncelle(ayar_id):
    try:
        # Admin kullanıcı başka firma için işlem yapıyorsa firma_id formdan gelebilir
        firma_id = session['firma_id']
        try:
            if session.get('is_admin', False) and request.form.get('firma_id'):
                firma_id = int(request.form.get('firma_id'))
        except Exception:
            pass

        sms_ayar = FirmaSMSAyar.query.filter_by(SMSAyarID=ayar_id, FirmaID=firma_id).first_or_404()
        sms_ayar.SMSFirmasi = request.form['sms_firmasi']
        sms_ayar.API_Key = request.form.get('api_key', '')
        sms_ayar.API_Secret = request.form.get('api_secret', '')
        sms_ayar.KullaniciAdi = request.form.get('kullanici_adi', '')
        sms_ayar.Sifre = request.form.get('sifre', '')
        sms_ayar.GondericiAdi = request.form.get('gonderici_adi', '')
        sms_ayar.API_URL = request.form.get('api_url', '')
        sms_ayar.VarsayilanSMSMetni = request.form.get('varsayilan_sms_metni', '')
        sms_ayar.SMSGonderOnCreate = ('sms_on_create' in request.form)
        sms_ayar.SMSGonder24SaatOnce = ('sms_24h' in request.form)
        sms_ayar.Aktif = 'aktif' in request.form
        db.session.commit()
        flash('SMS ayarları güncellendi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'SMS ayarları güncellenirken hata: {str(e)}', 'error')
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_sms', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_sms'))

@app.route('/ayarlar/sms/sil/<int:ayar_id>', methods=['POST', 'GET'])
@login_required
@admin_required
def ayarlar_sms_sil(ayar_id):
    try:
        # Admin kullanıcı başka firma için işlem yapıyorsa firma_id formdan gelebilir
        firma_id = session['firma_id']
        try:
            if session.get('is_admin', False):
                if request.method == 'POST' and request.form.get('firma_id'):
                    firma_id = int(request.form.get('firma_id'))
                elif request.method == 'GET' and request.args.get('firma_id'):
                    firma_id = int(request.args.get('firma_id'))
        except Exception:
            pass

        sms_ayar = FirmaSMSAyar.query.filter_by(SMSAyarID=ayar_id, FirmaID=firma_id).first_or_404()
        db.session.delete(sms_ayar)
        db.session.commit()
        flash('SMS ayarları silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'SMS ayarları silinirken hata: {str(e)}', 'error')
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False):
        hedef_firma_id = None
        if request.method == 'POST':
            hedef_firma_id = request.form.get('firma_id')
        else:
            hedef_firma_id = request.args.get('firma_id')
        if hedef_firma_id:
            return redirect(url_for('ayarlar_sms', firma_id=hedef_firma_id))
    return redirect(url_for('ayarlar_sms'))

# WhatsApp Ayarları
@app.route('/ayarlar/whatsapp')
@login_required
def ayarlar_whatsapp():
    # Admin ise firma seçimi yapabilir
    if session.get('is_admin', False):
        selected_firma_id = request.args.get('firma_id', type=int)
        if selected_firma_id:
            firma = Firma.query.get(selected_firma_id)
            if not firma:
                flash('Seçilen firma bulunamadı!', 'error')
                return redirect(url_for('ayarlar'))
        else:
            # İlk firma varsayılan olarak seçili
            firma = Firma.query.first()
            if not firma:
                flash('Hiç firma bulunamadı!', 'error')
                return redirect(url_for('ayarlar'))
            selected_firma_id = firma.FirmaID
        
        whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=selected_firma_id).first()
        firmalar = Firma.query.filter_by(Aktif=True).all()
        return render_template('ayarlar/whatsapp.html', 
                             whatsapp_ayar=whatsapp_ayar, 
                             firma=firma,
                             firmalar=firmalar,
                             is_admin=True)
    else:
        # Normal kullanıcı sadece kendi firmasını görebilir
        firma = Firma.query.get(session['firma_id'])
        if not firma:
            flash('Firma bilgisi bulunamadı!', 'error')
            return redirect(url_for('ayarlar'))
        
        whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=session['firma_id']).first()
        return render_template('ayarlar/whatsapp.html', 
                             whatsapp_ayar=whatsapp_ayar, 
                             firma=firma,
                             is_admin=False)

@app.route('/ayarlar/whatsapp/ekle', methods=['POST'])
@login_required
def ayarlar_whatsapp_ekle():
    try:
        # Admin ise formdan gelen firma_id'yi kullan
        hedef_firma_id = session['firma_id']
        try:
            if session.get('is_admin', False) and request.form.get('firma_id'):
                hedef_firma_id = int(request.form.get('firma_id'))
        except (ValueError, TypeError):
            pass
        
        # Mevcut ayar var mı kontrol et
        mevcut_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=hedef_firma_id).first()
        if mevcut_ayar:
            flash('Bu firma için WhatsApp ayarı zaten mevcut!', 'error')
            return redirect(url_for('ayarlar_whatsapp'))
        
        # Yeni WhatsApp ayarı oluştur
        whatsapp_ayar = FirmaWhatsAppAyar(
            FirmaID=hedef_firma_id,
            AccessToken=request.form.get('access_token'),
            PhoneNumberID=request.form.get('phone_number_id'),
            BusinessAccountID=request.form.get('business_account_id'),
            WebhookVerifyToken=request.form.get('webhook_verify_token'),
            RandevuOlusturmaMesaji=request.form.get('randevu_olusturma_mesaji'),
            RandevuHatirlatmaMesaji=request.form.get('randevu_hatirlatma_mesaji'),
            RandevuIptalMesaji=request.form.get('randevu_iptal_mesaji'),
            MesajGonderOnCreate=bool(request.form.get('mesaj_gonder_on_create')),
            MesajGonder24SaatOnce=bool(request.form.get('mesaj_gonder_24_saat_once')),
            MesajGonder1SaatOnce=bool(request.form.get('mesaj_gonder_1_saat_once')),
            Aktif=True
        )
        
        db.session.add(whatsapp_ayar)
        db.session.commit()
        
        flash('WhatsApp ayarları başarıyla eklendi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'WhatsApp ayarları eklenirken hata oluştu: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_whatsapp', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_whatsapp'))

@app.route('/ayarlar/whatsapp/guncelle/<int:ayar_id>', methods=['POST'])
@login_required
def ayarlar_whatsapp_guncelle(ayar_id):
    try:
        whatsapp_ayar = FirmaWhatsAppAyar.query.get_or_404(ayar_id)
        
        # Kullanıcı yetkisi kontrolü
        if not session.get('is_admin', False) and whatsapp_ayar.FirmaID != session['firma_id']:
            flash('Bu ayarı düzenleme yetkiniz yok!', 'error')
            return redirect(url_for('ayarlar_whatsapp'))
        
        # Ayarları güncelle
        whatsapp_ayar.AccessToken = request.form.get('access_token')
        whatsapp_ayar.PhoneNumberID = request.form.get('phone_number_id')
        whatsapp_ayar.BusinessAccountID = request.form.get('business_account_id')
        whatsapp_ayar.WebhookVerifyToken = request.form.get('webhook_verify_token')
        whatsapp_ayar.RandevuOlusturmaMesaji = request.form.get('randevu_olusturma_mesaji')
        whatsapp_ayar.RandevuHatirlatmaMesaji = request.form.get('randevu_hatirlatma_mesaji')
        whatsapp_ayar.RandevuIptalMesaji = request.form.get('randevu_iptal_mesaji')
        whatsapp_ayar.MesajGonderOnCreate = bool(request.form.get('mesaj_gonder_on_create'))
        whatsapp_ayar.MesajGonder24SaatOnce = bool(request.form.get('mesaj_gonder_24_saat_once'))
        whatsapp_ayar.MesajGonder1SaatOnce = bool(request.form.get('mesaj_gonder_1_saat_once'))
        whatsapp_ayar.GuncellemeTarihi = datetime.now()
        
        db.session.commit()
        flash('WhatsApp ayarları başarıyla güncellendi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'WhatsApp ayarları güncellenirken hata oluştu: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_whatsapp', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_whatsapp'))

@app.route('/ayarlar/whatsapp/sil/<int:ayar_id>', methods=['POST', 'GET'])
@login_required
def ayarlar_whatsapp_sil(ayar_id):
    try:
        whatsapp_ayar = FirmaWhatsAppAyar.query.get_or_404(ayar_id)
        
        # Kullanıcı yetkisi kontrolü
        if not session.get('is_admin', False) and whatsapp_ayar.FirmaID != session['firma_id']:
            flash('Bu ayarı silme yetkiniz yok!', 'error')
            return redirect(url_for('ayarlar_whatsapp'))
        
        db.session.delete(whatsapp_ayar)
        db.session.commit()
        flash('WhatsApp ayarları başarıyla silindi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'WhatsApp ayarları silinirken hata oluştu: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False):
        hedef_firma_id = request.args.get('firma_id')
        if hedef_firma_id:
            return redirect(url_for('ayarlar_whatsapp', firma_id=hedef_firma_id))
    return redirect(url_for('ayarlar_whatsapp'))

# Görev Durumları Ayarları
@app.route('/ayarlar/gorev-durumlar')
@login_required
def ayarlar_gorev_durumlar():
    firma_id = session['firma_id']
    durumlar = TodoDurum.query.filter_by(FirmaID=firma_id).order_by(TodoDurum.Sira, TodoDurum.DurumAdi).all()
    return render_template('ayarlar/gorev_durumlar.html', durumlar=durumlar)

# Veritabanı Ayarları
@app.route('/ayarlar/veritabani', methods=['GET', 'POST'])
@login_required
@admin_required
def ayarlar_veritabani():
    """Veritabanı ayarları sayfası ve kaydetme"""
    # Tablo yoksa oluştur
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'SistemAyarlar' not in inspector.get_table_names():
            db.create_all()
    except Exception:
        pass
    
    if request.method == 'POST':
        try:
            # Önce mevcut database_type'ı oku (değişiklik kontrolü için)
            old_db_type_setting = SistemAyar.query.filter_by(AyarAdi='database_type').first()
            old_db_type = old_db_type_setting.AyarDegeri.strip().lower() if old_db_type_setting and old_db_type_setting.AyarDegeri else None
            
            db_type = request.form.get('database_type', 'mssql').strip().lower()
            
            # Veritabanı değişti mi kontrol et
            db_changed = (old_db_type != db_type) if old_db_type else False
            
            # Mevcut ayarları güncelle veya yeni oluştur
            def save_setting(ayar_adi, deger, aciklama=None):
                setting = SistemAyar.query.filter_by(AyarAdi=ayar_adi).first()
                if setting:
                    old_value = setting.AyarDegeri
                    setting.AyarDegeri = deger if deger is not None else ''
                    if aciklama:
                        setting.Aciklama = aciklama
                    # Değişiklik oldu mu kontrol et
                    if old_value != setting.AyarDegeri:
                        print(f"[UPDATE] Ayar guncellendi: {ayar_adi}")
                else:
                    setting = SistemAyar(AyarAdi=ayar_adi, AyarDegeri=deger if deger is not None else '', Aciklama=aciklama)
                    db.session.add(setting)
                    print(f"[ADD] Yeni ayar eklendi: {ayar_adi}")
            
            # Veritabanı tipini kaydet
            save_setting('database_type', db_type, 'Veritabanı tipi (mssql veya mysql)')
            
            if db_type == 'mssql':
                save_setting('database_mssql_server', request.form.get('mssql_server', ''), 'MSSQL sunucu adresi')
                save_setting('database_mssql_port', request.form.get('mssql_port', '1433'), 'MSSQL port numarası')
                save_setting('database_mssql_database', request.form.get('mssql_database', ''), 'MSSQL veritabanı adı')
                save_setting('database_mssql_username', request.form.get('mssql_username', ''), 'MSSQL kullanıcı adı')
                mssql_password = request.form.get('mssql_password', '').strip()
                # Şifre kontrolü: boş değilse kaydet, boşsa mevcut şifreyi koru
                if mssql_password:
                    # Şifreyi şifreleyerek kaydet
                    encrypted_password = encrypt_password(mssql_password)
                    save_setting('database_mssql_password', encrypted_password, 'MSSQL şifresi (şifrelenmiş)')
                    print(f"[OK] MSSQL sifre kaydedildi (şifrelenmiş, uzunluk: {len(encrypted_password)})")
                else:
                    # Mevcut şifre ayarını kontrol et
                    existing_password = SistemAyar.query.filter_by(AyarAdi='database_mssql_password').first()
                    if existing_password:
                        print(f"[INFO] MSSQL sifre bos gonderildi, mevcut sifre korunuyor")
                    else:
                        print(f"[WARN] MSSQL sifre bos ve mevcut ayar yok, sifre kaydedilmedi")
                save_setting('database_mssql_driver', request.form.get('mssql_driver', 'ODBC Driver 17 for SQL Server'), 'MSSQL ODBC Driver')
            
            elif db_type == 'mysql':
                save_setting('database_mysql_host', request.form.get('mysql_host', ''), 'MySQL sunucu adresi')
                save_setting('database_mysql_port', request.form.get('mysql_port', '3306'), 'MySQL port numarası')
                save_setting('database_mysql_database', request.form.get('mysql_database', ''), 'MySQL veritabanı adı')
                save_setting('database_mysql_username', request.form.get('mysql_username', ''), 'MySQL kullanıcı adı')
                mysql_password = request.form.get('mysql_password', '').strip()
                # Şifre kontrolü: boş değilse kaydet, boşsa mevcut şifreyi koru
                if mysql_password:
                    # Şifreyi şifreleyerek kaydet
                    encrypted_password = encrypt_password(mysql_password)
                    save_setting('database_mysql_password', encrypted_password, 'MySQL şifresi (şifrelenmiş)')
                    print(f"[OK] MySQL sifre kaydedildi (şifrelenmiş, uzunluk: {len(encrypted_password)})")
                else:
                    # Mevcut şifre ayarını kontrol et
                    existing_password = SistemAyar.query.filter_by(AyarAdi='database_mysql_password').first()
                    if existing_password:
                        print(f"[INFO] MySQL sifre bos gonderildi, mevcut sifre korunuyor")
                    else:
                        print(f"[WARN] MySQL sifre bos ve mevcut ayar yok, sifre kaydedilmedi")
                save_setting('database_mysql_charset', request.form.get('mysql_charset', 'utf8mb4'), 'MySQL charset')
            
            db.session.commit()
            
            # Ayarları .env dosyasına da kaydet (isteğe bağlı checkbox ile kontrol edilebilir)
            export_to_env = request.form.get('export_to_env', 'false').lower() == 'true'
            
            if export_to_env:
                try:
                    # SistemAyarlar'dan database_type'ı oku ve ona göre .env dosyasını güncelle
                    export_settings_to_env(None)  # None göndererek SistemAyarlar'dan okumasını sağla
                    print("[OK] Ayarlar .env dosyasina kaydedildi!")
                    flash(_('Database settings saved and exported to .env file'), 'success')
                except Exception as env_err:
                    print(f"[WARN] .env dosyasina kaydetme hatasi: {env_err}")
                    import traceback
                    traceback.print_exc()
                    flash(_('Database settings saved, but failed to export to .env file'), 'warning')
            
            # Ayarlar kaydedildikten sonra bağlantıyı güncelle
            print("\n" + "=" * 60)
            print("[UPDATE] Veritabani ayarlari kaydedildi, baglanti guncelleniyor...")
            print("=" * 60)
            
            # _app_initialized flag'ini sıfırla ki initialize_database_from_settings tekrar çalışsın
            global _app_initialized
            _app_initialized = False
            
            # Yeni ayarları yükle
            try:
                initialize_database_from_settings()
                print("[OK] Veritabani baglantisi guncellendi!")
            except Exception as init_err:
                print(f"[WARN] Veritabani baglantisi guncellenirken hata: {init_err}")
                import traceback
                traceback.print_exc()
            
            # Veritabanı değiştiyse: Tüm aktif oturumları sonlandır ve logout yap
            if db_changed:
                print("\n[INFO] Veritabani degisti (eski: {old_db_type}, yeni: {db_type}), tum aktif oturumlar sonlandiriliyor...".format(
                    old_db_type=old_db_type or 'yok',
                    db_type=db_type
                ))
                try:
                    # Tüm aktif oturumları sil (yeni veritabanında)
                    # Önce yeni bağlantı üzerinden silme işlemi yapılabilir
                    deleted_count = AktifOturum.query.delete()
                    db.session.commit()
                    print(f"[OK] {deleted_count} aktif oturum sonlandirildi")
                except Exception as session_err:
                    print(f"[WARN] Oturum sonlandirma hatasi (normal olabilir): {session_err}")
                    db.session.rollback()
                
                # Session'ı temizle ve logout yap
                session.clear()
                flash(_('Database changed. All sessions have been terminated. Please log in again with the new database.'), 'info')
                return redirect(url_for('login'))
            else:
                # Veritabanı değişmediyse normal mesaj
                if not export_to_env:
                    flash(_('Database settings saved successfully'), 'success')
                return redirect(url_for('ayarlar_veritabani'))
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"Veritabanı ayarları kaydetme hatası: {error_detail}")
            flash(f'{_("Error saving database settings:")} {str(e)}', 'error')
    
    # GET isteği - mevcut ayarları yükle
    try:
        # Tablo yoksa oluştur
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            if 'SistemAyarlar' not in inspector.get_table_names():
                db.create_all()
        except Exception:
            pass
        
        db_type_setting = SistemAyar.query.filter_by(AyarAdi='database_type').first()
        db_type = db_type_setting.AyarDegeri.strip().lower() if db_type_setting and db_type_setting.AyarDegeri else 'mssql'
        
        # MSSQL ayarları
        mssql_server = SistemAyar.query.filter_by(AyarAdi='database_mssql_server').first()
        mssql_port = SistemAyar.query.filter_by(AyarAdi='database_mssql_port').first()
        mssql_database = SistemAyar.query.filter_by(AyarAdi='database_mssql_database').first()
        mssql_username = SistemAyar.query.filter_by(AyarAdi='database_mssql_username').first()
        mssql_driver = SistemAyar.query.filter_by(AyarAdi='database_mssql_driver').first()
        
        # MySQL ayarları
        mysql_host = SistemAyar.query.filter_by(AyarAdi='database_mysql_host').first()
        mysql_port = SistemAyar.query.filter_by(AyarAdi='database_mysql_port').first()
        mysql_database = SistemAyar.query.filter_by(AyarAdi='database_mysql_database').first()
        mysql_username = SistemAyar.query.filter_by(AyarAdi='database_mysql_username').first()
        mysql_charset = SistemAyar.query.filter_by(AyarAdi='database_mysql_charset').first()
        
        return render_template('ayarlar/veritabani.html',
                             db_type=db_type,
                             mssql_server=mssql_server.AyarDegeri if mssql_server else '',
                             mssql_port=mssql_port.AyarDegeri if mssql_port else '1433',
                             mssql_database=mssql_database.AyarDegeri if mssql_database else '',
                             mssql_username=mssql_username.AyarDegeri if mssql_username else '',
                             mssql_driver=mssql_driver.AyarDegeri if mssql_driver else 'ODBC Driver 17 for SQL Server',
                             mysql_host=mysql_host.AyarDegeri if mysql_host else '',
                             mysql_port=mysql_port.AyarDegeri if mysql_port else '3306',
                             mysql_database=mysql_database.AyarDegeri if mysql_database else '',
                             mysql_username=mysql_username.AyarDegeri if mysql_username else '',
                             mysql_charset=mysql_charset.AyarDegeri if mysql_charset else 'utf8mb4')
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Veritabanı ayarları yükleme hatası: {error_detail}")
        flash(f'{_("Error loading database settings:")} {str(e)}', 'error')
        return render_template('ayarlar/veritabani.html', db_type='mssql')

@app.route('/ayarlar/veritabani/durum', methods=['GET'])
@login_required
@admin_required
def ayarlar_veritabani_durum():
    """Mevcut veritabanı bağlantı durumunu kontrol et"""
    try:
        # Admin kontrolü - eğer admin değilse JSON olarak hata döndür
        if not session.get('is_admin', False):
            return jsonify({'error': 'Admin yetkisi gerekli'}), 403
        # SistemAyarlar'dan ayarları oku
        db_type_setting = SistemAyar.query.filter_by(AyarAdi='database_type').first()
        db_type = db_type_setting.AyarDegeri.strip().lower() if db_type_setting and db_type_setting.AyarDegeri else None
        
        # Mevcut bağlantı URI'sini al (gizli bilgileri gizle)
        current_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        # Şifreleri gizle
        if '@' in current_uri and '://' in current_uri:
            parts = current_uri.split('://')
            if len(parts) > 1:
                auth_part = parts[1].split('@')[0] if '@' in parts[1] else ''
                if ':' in auth_part:
                    username, password = auth_part.split(':', 1)
                    masked_uri = current_uri.replace(f':{password}@', ':***@', 1)
                else:
                    masked_uri = current_uri
            else:
                masked_uri = current_uri
        else:
            masked_uri = current_uri
        
        # .env'den DATABASE_URL'i kontrol et
        env_db_url = os.environ.get('DATABASE_URL', '')
        masked_env_uri = env_db_url
        if '@' in env_db_url and '://' in env_db_url:
            parts = env_db_url.split('://')
            if len(parts) > 1:
                auth_part = parts[1].split('@')[0] if '@' in parts[1] else ''
                if ':' in auth_part:
                    username, password = auth_part.split(':', 1)
                    masked_env_uri = env_db_url.replace(f':{password}@', ':***@', 1)
        
        # SistemAyarlar'dan URI oluştur (debug=False çünkü bu API route'dan çağrılıyor)
        settings_uri = get_database_uri_from_settings(debug=False)
        masked_settings_uri = None
        if settings_uri:
            # Şifreyi gizle
            if '@' in settings_uri and '://' in settings_uri:
                parts = settings_uri.split('://')
                if len(parts) > 1:
                    auth_part = parts[1].split('@')[0] if '@' in parts[1] else ''
                    if ':' in auth_part:
                        username, password = auth_part.split(':', 1)
                        masked_settings_uri = settings_uri.replace(f':{password}@', ':***@', 1)
                    else:
                        masked_settings_uri = settings_uri
                else:
                    masked_settings_uri = settings_uri
            else:
                masked_settings_uri = settings_uri
        
        # Hangi ayarların aktif olduğunu belirle
        # URI'leri karşılaştırırken şifre kısmını çıkararak karşılaştır
        def normalize_uri_for_comparison(uri):
            """URI'yi karşılaştırma için normalize et (şifreyi çıkar)"""
            if '@' in uri and '://' in uri:
                parts = uri.split('://')
                if len(parts) > 1:
                    auth_part = parts[1].split('@')[0] if '@' in parts[1] else ''
                    if ':' in auth_part:
                        username = auth_part.split(':')[0]
                        return uri.replace(auth_part, username + ':***')
            return uri
        
        current_uri_normalized = normalize_uri_for_comparison(current_uri)
        settings_uri_normalized = normalize_uri_for_comparison(settings_uri) if settings_uri else None
        
        is_using_settings = settings_uri and current_uri_normalized == settings_uri_normalized
        is_using_env = not is_using_settings and env_db_url
        
        return jsonify({
            'current_database_type': db_type,
            'current_uri': masked_uri,
            'env_uri': masked_env_uri,
            'settings_uri': masked_settings_uri,
            'is_using_settings': is_using_settings,
            'is_using_env': is_using_env,
            'settings_available': settings_uri is not None
        }), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[HATA] ayarlar_veritabani_durum hatasi: {error_detail}")
        return jsonify({'error': str(e)}), 500, {'Content-Type': 'application/json'}

@app.route('/ayarlar/veritabani/test', methods=['POST'])
@login_required
@admin_required
def ayarlar_veritabani_test():
    """Veritabanı bağlantısını test et"""
    try:
        db_type = request.form.get('database_type', 'mssql').strip().lower()
        
        if db_type == 'mssql':
            server = request.form.get('mssql_server', 'localhost')
            port = int(request.form.get('mssql_port', '1433'))
            database = request.form.get('mssql_database', '')
            username = request.form.get('mssql_username', '')
            password = request.form.get('mssql_password', '')
            driver = request.form.get('mssql_driver', 'ODBC Driver 17 for SQL Server')
            
            if not all([server, database, username]):
                return jsonify({'success': False, 'error': _('Missing required fields')})
            
            test_uri = build_mssql_uri(server, database, username, password, port, driver)
            engine = create_engine(test_uri, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
        elif db_type == 'mysql':
            host = request.form.get('mysql_host', 'localhost')
            port = int(request.form.get('mysql_port', '3306'))
            database = request.form.get('mysql_database', '')
            username = request.form.get('mysql_username', '')
            password = request.form.get('mysql_password', '')
            charset = request.form.get('mysql_charset', 'utf8mb4')
            
            if not all([host, database, username]):
                return jsonify({'success': False, 'error': _('Missing required fields')})
            
            test_uri = build_mysql_uri(host, database, username, password, port, charset)
            engine = create_engine(test_uri, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        else:
            return jsonify({'success': False, 'error': _('Invalid database type')})
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Görev Durumları API
@app.route('/api/gorev-durumlar', methods=['POST'])
@login_required
def api_gorev_durum_ekle():
    try:
        firma_id = session['firma_id']
        data = request.get_json()
        
        # Aktif değerini boolean'a çevir
        aktif_deger = data.get('Aktif', True)
        print(f"DEBUG: Aktif değeri: {aktif_deger}, tip: {type(aktif_deger)}")
        if isinstance(aktif_deger, str):
            aktif_deger = aktif_deger.lower() in ['true', '1', 'on', 'yes']
        elif isinstance(aktif_deger, bool):
            aktif_deger = aktif_deger
        else:
            aktif_deger = bool(aktif_deger)
        print(f"DEBUG: Dönüştürülmüş Aktif değeri: {aktif_deger}")
        
        # Yeni durum oluştur
        yeni_durum = TodoDurum(
            FirmaID=firma_id,
            DurumAdi=data.get('durum_adi'),
            DurumAciklamasi=data.get('durum_aciklamasi'),
            Renk=data.get('durum_renk', '#007bff'),
            Sira=int(data.get('durum_sira', 0)),
            Aktif=aktif_deger
        )
        
        db.session.add(yeni_durum)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Durum başarıyla eklendi'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/gorev-durumlar/<int:durum_id>', methods=['GET'])
@login_required
def api_gorev_durum_get(durum_id):
    try:
        firma_id = session['firma_id']
        durum = TodoDurum.query.filter_by(DurumID=durum_id, FirmaID=firma_id).first()
        
        if not durum:
            return jsonify({'success': False, 'message': 'Durum bulunamadı'})
        
        return jsonify({
            'success': True,
            'durum': {
                'DurumID': durum.DurumID,
                'DurumAdi': durum.DurumAdi,
                'DurumAciklamasi': durum.DurumAciklamasi,
                'Renk': durum.Renk,
                'Sira': durum.Sira,
                'Aktif': durum.Aktif
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/gorev-durumlar/<int:durum_id>', methods=['PUT'])
@login_required
def api_gorev_durum_guncelle(durum_id):
    try:
        firma_id = session['firma_id']
        durum = TodoDurum.query.filter_by(DurumID=durum_id, FirmaID=firma_id).first()
        
        if not durum:
            return jsonify({'success': False, 'message': 'Durum bulunamadı'})
        
        data = request.get_json()
        
        # Aktif değerini boolean'a çevir
        aktif_deger = data.get('Aktif', durum.Aktif)
        if isinstance(aktif_deger, str):
            aktif_deger = aktif_deger.lower() in ['true', '1', 'on', 'yes']
        elif isinstance(aktif_deger, bool):
            aktif_deger = aktif_deger
        else:
            aktif_deger = bool(aktif_deger)
        
        # Durumu güncelle
        durum.DurumAdi = data.get('durum_adi', durum.DurumAdi)
        durum.DurumAciklamasi = data.get('durum_aciklamasi', durum.DurumAciklamasi)
        durum.Renk = data.get('durum_renk', durum.Renk)
        durum.Sira = int(data.get('durum_sira', durum.Sira))
        durum.Aktif = aktif_deger
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Durum başarıyla güncellendi'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/gorev-durumlar/<int:durum_id>', methods=['DELETE'])
@login_required
def api_gorev_durum_sil(durum_id):
    try:
        firma_id = session['firma_id']
        durum = TodoDurum.query.filter_by(DurumID=durum_id, FirmaID=firma_id).first()
        
        if not durum:
            return jsonify({'success': False, 'message': 'Durum bulunamadı'})
        
        # Bu durumu kullanan görevler var mı kontrol et
        kullanan_todos = Todo.query.filter_by(DurumID=durum_id).count()
        if kullanan_todos > 0:
            return jsonify({'success': False, 'message': f'Bu durum {kullanan_todos} görevde kullanılıyor. Önce bu görevlerin durumunu değiştirin.'})
        
        db.session.delete(durum)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Durum başarıyla silindi'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# Görev Durumları Listesi API
@app.route('/api/gorev-durumlar', methods=['GET'])
@login_required
def api_gorev_durumlar_list():
    try:
        firma_id = session['firma_id']
        durumlar = TodoDurum.query.filter_by(FirmaID=firma_id, Aktif=True).order_by(TodoDurum.Sira, TodoDurum.DurumAdi).all()
        
        durum_list = []
        for durum in durumlar:
            durum_list.append({
                'DurumID': durum.DurumID,
                'DurumAdi': durum.DurumAdi,
                'Renk': durum.Renk
            })
        
        return jsonify({'success': True, 'durumlar': durum_list})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# WhatsApp Sohbet Ekranı
@app.route('/whatsapp')
@login_required
def whatsapp_chat():
    """WhatsApp Business API entegrasyonu ile sohbet ekranı"""
    # Firma WhatsApp ayarlarını kontrol et
    whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).first()
    
    if not whatsapp_ayar:
        flash('WhatsApp ayarları bulunamadı. Lütfen önce WhatsApp ayarlarını yapılandırın.', 'warning')
        return redirect(url_for('ayarlar_whatsapp'))
    
    # Müşteri listesini getir (mesaj gönderme için)
    from app import Musteri
    musteriler = Musteri.query.filter_by(FirmaID=session['firma_id']).all()
    
    return render_template('whatsapp/chat.html', 
                         whatsapp_ayar=whatsapp_ayar,
                         musteriler=musteriler)

# WhatsApp Mesaj Gönderme API
@app.route('/api/whatsapp/send', methods=['POST'])
@login_required
def whatsapp_send_message():
    """WhatsApp mesajı gönder"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        message = data.get('message')
        
        if not phone_number or not message:
            return jsonify({'success': False, 'error': 'Telefon numarası ve mesaj gerekli'}), 400
        
        # Telefon numarasını temizle
        phone_clean = ''.join(filter(str.isdigit, phone_number))
        if not phone_clean or len(phone_clean) < 10:
            return jsonify({'success': False, 'error': 'Geçersiz telefon numarası'}), 400
        
        # WhatsApp mesajını gönder
        success, result = send_whatsapp_message(phone_clean, message, session['firma_id'])
        
        if success:
            return jsonify({'success': True, 'message': 'Mesaj başarıyla gönderildi'})
        else:
            return jsonify({'success': False, 'error': result}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# WhatsApp mesaj gönderme fonksiyonu
def send_whatsapp_message(phone_number, message, firma_id):
    """WhatsApp mesajı gönder"""
    try:
        whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=firma_id, Aktif=True).first()
        if not whatsapp_ayar or not whatsapp_ayar.AccessToken or not whatsapp_ayar.PhoneNumberID:
            return False, "WhatsApp ayarları bulunamadı"
        
        import requests
        
        url = f"https://graph.facebook.com/v18.0/{whatsapp_ayar.PhoneNumberID}/messages"
        headers = {
            "Authorization": f"Bearer {whatsapp_ayar.AccessToken}",
            "Content-Type": "application/json"
        }
        
        data = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {"body": message}
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            return True, "Mesaj başarıyla gönderildi"
        else:
            return False, f"Mesaj gönderilemedi: {response.text}"
            
    except Exception as e:
        return False, f"Hata: {str(e)}"

@app.route('/randevular')
@login_required
def randevular():
    # Randevu listesi + referans, defter, durum, tarih ve oluşturan filtresi
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuReferans.Ad).all()
    defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuDefterAyar.DefterAdi).all()
    kullanicilar = Kullanici.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(Kullanici.Ad, Kullanici.Soyad).all()
    
    ref_id = request.args.get('referans_id', type=int)
    defter_id = request.args.get('defter_id', type=int)
    durum = request.args.get('durum', type=str)
    olusturan_id = request.args.get('olusturan_id', type=int)
    baslangic_str = request.args.get('baslangic', type=str)
    bitis_str = request.args.get('bitis', type=str)

    # Kullanıcının son seçtiği tarih aralığını hatırla
    if baslangic_str or bitis_str:
        if baslangic_str:
            session['randevular_baslangic'] = baslangic_str
        if bitis_str:
            session['randevular_bitis'] = bitis_str
    else:
        baslangic_str = session.get('randevular_baslangic')
        bitis_str = session.get('randevular_bitis')
    
    # Eğer hâlâ tarih filtresi yoksa bugünü varsayılan olarak ayarla
    if not baslangic_str and not bitis_str:
        today = datetime.now().date()
        baslangic_str = today.strftime('%Y-%m-%d')
        bitis_str = today.strftime('%Y-%m-%d')
    
    # Tarih filtrelerini datetime'a çevir
    baslangic = None
    bitis = None
    if baslangic_str:
        try:
            baslangic = datetime.strptime(baslangic_str, '%Y-%m-%d')
        except ValueError:
            baslangic = None
    if bitis_str:
        try:
            bitis = datetime.strptime(bitis_str, '%Y-%m-%d')
            # Bitiş tarihine 1 gün ekle (tarih aralığı dahil olsun)
            bitis = bitis + timedelta(days=1)
        except ValueError:
            bitis = None
    
    ref = None
    defter = None
    olusturan = None
    if ref_id:
        ref = RandevuReferans.query.filter_by(ReferansID=ref_id, FirmaID=session['firma_id']).first()
    if defter_id:
        defter = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=session['firma_id']).first()
    if olusturan_id:
        olusturan = Kullanici.query.filter_by(KullaniciID=olusturan_id, FirmaID=session['firma_id']).first()

    # Admin ise tüm randevuları göster, değilse yetkili randevular + kendi oluşturduğu randevular
    if session.get('is_admin', False):
        base_query = Randevu.query
    else:
        # Yetkili randevular + kendi oluşturduğu randevular (görevlerden oluşturulanlar dahil)
        base_query = db.session.query(Randevu).outerjoin(RandevuYetki, 
            (RandevuYetki.RandevuID == Randevu.RandevuID) & 
            (RandevuYetki.KullaniciID == session['user_id']) & 
            (RandevuYetki.GoruntulemeYetkisi == True)
        ).filter(
            (RandevuYetki.KullaniciID == session['user_id']) | 
            (Randevu.OlusturanKullaniciID == session['user_id'])
        )

    q = base_query.filter(Randevu.FirmaID == session['firma_id'])
    if ref is not None:
        q = q.filter(Randevu.RandevuBaslik == ref.Ad)
    if defter is not None:
        q = q.filter(Randevu.DefterID == defter.AyarID)
    if durum:
        q = q.filter(Randevu.Durum == durum)
    if olusturan is not None:
        q = q.filter(Randevu.OlusturanKullaniciID == olusturan.KullaniciID)
    if baslangic:
        q = q.filter(Randevu.RandevuTarihi >= baslangic)
    if bitis:
        q = q.filter(Randevu.RandevuTarihi < bitis)

    randevular = q.order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Bugünün tarihini string olarak hazırla
    today_str = datetime.now().date().strftime('%Y-%m-%d')
    
    return render_template('randevular.html', 
                         randevular=randevular, 
                         referanslar=referanslar, 
                         defterler=defterler,
                         kullanicilar=kullanicilar,
                         selected_referans_id=ref_id,
                         selected_defter_id=defter_id,
                         selected_durum=durum,
                         selected_olusturan_id=olusturan_id,
                         selected_baslangic=baslangic_str,
                         selected_bitis=bitis_str,
                         today_str=today_str)

@app.route('/api/musteri-arama')
@login_required
def musteri_arama():
    """Müşteri arama API'si"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return jsonify([])
    
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    # Müşteri arama sorgusu
    musteriler = Musteri.query.filter(
        Musteri.FirmaID == firma_id,
        Musteri.Aktif == True,
        or_(
            Musteri.MusteriAdi.ilike(f'%{query}%'),
            Musteri.MusteriSoyadi.ilike(f'%{query}%'),
            Musteri.Telefon.ilike(f'%{query}%'),
            Musteri.Email.ilike(f'%{query}%'),
            # Tam isim araması (Ad + Soyad)
            db.func.concat(Musteri.MusteriAdi, ' ', Musteri.MusteriSoyadi).ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    # Eğer sonuç bulunamadıysa, kelime bazlı arama yap
    if not musteriler and ' ' in query:
        words = query.split()
        if len(words) >= 2:
            # İlk kelime ad, ikinci kelime soyad başlangıcı
            first_word = words[0]
            second_word = words[1]
            
            musteriler = Musteri.query.filter(
                Musteri.FirmaID == firma_id,
                Musteri.Aktif == True,
                and_(
                    Musteri.MusteriAdi.ilike(f'%{first_word}%'),
                    Musteri.MusteriSoyadi.ilike(f'%{second_word}%')
                )
            ).limit(10).all()
    
    # Plaka kodlarını şehir isimlerine dönüştür
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }
    
    results = []
    for m in musteriler:
        sehir_adi = plaka_to_sehir.get(m.Sehir, m.Sehir) if m.Sehir else None
        results.append({
            'id': m.MusteriID,
            'ad': m.MusteriAdi,
            'soyad': m.MusteriSoyadi,
            'telefon': m.Telefon,
            'email': m.Email,
            'sehir': sehir_adi
        })
    
    return jsonify(results)

@app.route('/rapor/musteri-detay/<int:musteri_id>')
@login_required
def musteri_detay_raporu(musteri_id):
    """Müşteri detay raporu"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        flash('Müşteri bulunamadı.', 'error')
        return redirect(url_for('rapor_musteriler'))
    
    # Plaka kodlarını şehir isimlerine dönüştür
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Randevu istatistikleri
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    # Son randevu tarihi
    son_randevu = randevular[0] if randevular else None
    
    # Aylık randevu dağılımı (son 12 ay)
    from collections import defaultdict
    
    aylik_randevu = defaultdict(int)
    for r in randevular:
        if r.RandevuTarihi:
            ay_key = r.RandevuTarihi.strftime('%Y-%m')
            aylik_randevu[ay_key] += 1
    
    # Randevu defteri dağılımı
    defter_dagilimi = defaultdict(int)
    for r in randevular:
        if r.DefterID:
            # DefterID'den defter adını al
            defter = RandevuDefterAyar.query.filter_by(AyarID=r.DefterID).first()
            if defter:
                defter_dagilimi[defter.DefterAdi] += 1
            else:
                defter_dagilimi['Bilinmeyen Defter'] += 1
    
    # Şehir bilgisini dönüştür
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    
    return render_template('musteri_detay_raporu.html',
                         musteri=musteri,
                         randevular=randevular,
                         toplam_randevu=toplam_randevu,
                         tamamlanan_randevu=tamamlanan_randevu,
                         iptal_randevu=iptal_randevu,
                         bekleyen_randevu=bekleyen_randevu,
                         son_randevu=son_randevu,
                         aylik_randevu=dict(aylik_randevu),
                         defter_dagilimi=dict(defter_dagilimi),
                         sehir_adi=sehir_adi)

@app.route('/rapor/musteri-detay-modal/<int:musteri_id>')
@login_required
def musteri_detay_modal(musteri_id):
    """Müşteri detay raporu modal içeriği"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        return '<div class="alert alert-danger">Müşteri bulunamadı.</div>'
    
    print(f"DEBUG: Müşteri detay modal - Müşteri ID: {musteri_id}, Firma ID: {firma_id}")
    print(f"DEBUG: Müşteri adı: {musteri.MusteriAdi} {musteri.MusteriSoyadi}")
    
    # Plaka kodlarını şehir isimlerine dönüştür
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    print(f"DEBUG: Bulunan randevu sayısı: {len(randevular)}")
    for r in randevular:
        print(f"DEBUG: Randevu - ID: {r.RandevuID}, Tarih: {r.RandevuTarihi}, Durum: {r.Durum}")
    
    # Randevu istatistikleri
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    # Aylık randevu dağılımı
    aylik_randevu = defaultdict(int)
    for randevu in randevular:
        if randevu.RandevuTarihi:
            ay_key = randevu.RandevuTarihi.strftime('%Y-%m')
            aylik_randevu[ay_key] += 1
            print(f"DEBUG: Aylık dağılım - {ay_key}: {aylik_randevu[ay_key]}")
    
    print(f"DEBUG: Aylık randevu dağılımı: {dict(aylik_randevu)}")
    
    # Defter dağılımı
    defter_dagilimi = defaultdict(int)
    for randevu in randevular:
        if randevu.DefterID:
            defter = RandevuDefterAyar.query.filter_by(AyarID=randevu.DefterID).first()
            if defter:
                defter_dagilimi[defter.DefterAdi] += 1
                print(f"DEBUG: Defter dağılımı - {defter.DefterAdi}: {defter_dagilimi[defter.DefterAdi]}")
    
    print(f"DEBUG: Defter dağılımı: {dict(defter_dagilimi)}")
    
    # Şehir bilgisini dönüştür
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    
    return render_template('musteri_detay_modal.html',
                         musteri=musteri,
                         randevular=randevular,
                         toplam_randevu=toplam_randevu,
                         tamamlanan_randevu=tamamlanan_randevu,
                         iptal_randevu=iptal_randevu,
                         bekleyen_randevu=bekleyen_randevu,
                         aylik_randevu=dict(aylik_randevu),
                         defter_dagilimi=dict(defter_dagilimi),
                         sehir_adi=sehir_adi)

@app.route('/rapor/musteri-detay/<int:musteri_id>/pdf')
@login_required
def musteri_detay_pdf(musteri_id):
    """Müşteri detay raporu PDF"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        flash('Müşteri bulunamadı.', 'error')
        return redirect(url_for('rapor_musteriler'))
    
    # Plaka kodlarını şehir isimlerine dönüştür
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Randevu istatistikleri
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    # Şehir bilgisini dönüştür
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    
    # PDF oluştur
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Türkçe font desteği için DejaVu Sans fontunu kaydet
    try:
        # Windows sistem fontları
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/dejavu-sans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/dejavu-sans-bold.ttf'))
        turkish_font = 'DejaVuSans'
        turkish_font_bold = 'DejaVuSans-Bold'
    except:
        try:
            # Alternatif font yolları
            pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/arial.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
            turkish_font = 'DejaVuSans'
            turkish_font_bold = 'DejaVuSans-Bold'
        except:
            # Varsayılan font
            turkish_font = 'Helvetica'
            turkish_font_bold = 'Helvetica-Bold'
    
    # Stil tanımları
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=TA_CENTER, fontName=turkish_font_bold)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, spaceAfter=12, fontName=turkish_font_bold)
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontName=turkish_font)
    
    # İçerik oluştur
    story = []
    
    # Başlık
    story.append(Paragraph("Müşteri Detay Raporu", title_style))
    story.append(Spacer(1, 12))
    
    # Müşteri bilgileri
    story.append(Paragraph("Müşteri Bilgileri", heading_style))
    
    musteri_data = [
        ['Ad Soyad:', f"{musteri.MusteriAdi} {musteri.MusteriSoyadi}"],
        ['Telefon:', musteri.Telefon or 'Belirtilmemiş'],
        ['E-posta:', musteri.Email or 'Belirtilmemiş'],
        ['Yaş:', str(musteri.Yas) if musteri.Yas else 'Belirtilmemiş'],
        ['Cinsiyet:', musteri.Cinsiyet or 'Belirtilmemiş'],
        ['Şehir:', sehir_adi],
        ['İlçe:', musteri.Ilce or 'Belirtilmemiş'],
        ['Doğum Tarihi:', musteri.DogumTarihi.strftime('%d.%m.%Y') if musteri.DogumTarihi else 'Belirtilmemiş']
    ]
    
    if musteri.Adres:
        musteri_data.append(['Adres:', musteri.Adres])
    if musteri.Notlar:
        musteri_data.append(['Notlar:', musteri.Notlar])
    
    musteri_table = Table(musteri_data, colWidths=[2*inch, 4*inch])
    musteri_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), turkish_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(musteri_table)
    story.append(Spacer(1, 20))
    
    # Randevu istatistikleri
    story.append(Paragraph("Randevu İstatistikleri", heading_style))
    
    stats_data = [
        ['Toplam Randevu:', str(toplam_randevu)],
        ['Tamamlanan:', str(tamamlanan_randevu)],
        ['Beklemede:', str(bekleyen_randevu)],
        ['İptal:', str(iptal_randevu)]
    ]
    
    stats_table = Table(stats_data, colWidths=[2*inch, 1*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), turkish_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 20))
    
    # Randevu geçmişi
    if randevular:
        story.append(Paragraph("Randevu Geçmişi", heading_style))
        
        randevu_data = [['Tarih', 'Saat', 'Defter', 'Durum', 'Notlar']]
        
        for randevu in randevular:
            defter_adi = 'Bilinmeyen'
            if randevu.DefterID:
                defter = RandevuDefterAyar.query.filter_by(AyarID=randevu.DefterID).first()
                if defter:
                    defter_adi = defter.DefterAdi
            
            randevu_data.append([
                randevu.RandevuTarihi.strftime('%d.%m.%Y') if randevu.RandevuTarihi else '-',
                randevu.RandevuTarihi.strftime('%H:%M') if randevu.RandevuTarihi else '-',
                defter_adi,
                randevu.Durum,
                randevu.RandevuAciklamasi or '-'
            ])
        
        randevu_table = Table(randevu_data, colWidths=[1*inch, 0.8*inch, 1.2*inch, 1*inch, 2*inch])
        randevu_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), turkish_font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), turkish_font),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(randevu_table)
    else:
        story.append(Paragraph("Bu müşteri için randevu bulunamadı.", normal_style))
    
    # PDF'i oluştur
    doc.build(story)
    buffer.seek(0)
    
    # Dosya adı
    filename = f"musteri_detay_{musteri.MusteriAdi}_{musteri.MusteriSoyadi}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    # Çıktı alma (PDF) logla
    try:
        log_user_action('VIEW', 'Rapor', musteri_id, detail=f"Müşteri detay PDF indirildi: {musteri.MusteriAdi} {musteri.MusteriSoyadi}")
    except Exception:
        pass
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)

@app.route('/rapor/musteri-detay/<int:musteri_id>/excel')
@login_required
def musteri_detay_excel(musteri_id):
    """Müşteri detay raporu Excel"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        flash('Müşteri bulunamadı.', 'error')
        return redirect(url_for('rapor_musteriler'))
    
    # Plaka kodlarını şehir isimlerine dönüştür
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Excel dosyası oluştur
    wb = Workbook()
    
    # Müşteri bilgileri sayfası
    ws1 = wb.active
    ws1.title = "Müşteri Bilgileri"
    
    # Başlık
    ws1['A1'] = "Müşteri Detay Raporu"
    ws1['A1'].font = Font(size=16, bold=True)
    ws1.merge_cells('A1:D1')
    
    # Müşteri bilgileri
    row = 3
    ws1[f'A{row}'] = "Ad Soyad:"
    ws1[f'B{row}'] = f"{musteri.MusteriAdi} {musteri.MusteriSoyadi}"
    row += 1
    
    ws1[f'A{row}'] = "Telefon:"
    telefon_cell = ws1[f'B{row}']
    telefon_cell.value = musteri.Telefon or 'Belirtilmemiş'
    telefon_cell.number_format = '@'  # Metin formatı
    row += 1
    
    ws1[f'A{row}'] = "E-posta:"
    ws1[f'B{row}'] = musteri.Email or 'Belirtilmemiş'
    row += 1
    
    ws1[f'A{row}'] = "Yaş:"
    ws1[f'B{row}'] = musteri.Yas or 'Belirtilmemiş'
    row += 1
    
    ws1[f'A{row}'] = "Cinsiyet:"
    ws1[f'B{row}'] = musteri.Cinsiyet or 'Belirtilmemiş'
    row += 1
    
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    ws1[f'A{row}'] = "Şehir:"
    ws1[f'B{row}'] = sehir_adi
    row += 1
    
    ws1[f'A{row}'] = "İlçe:"
    ws1[f'B{row}'] = musteri.Ilce or 'Belirtilmemiş'
    row += 1
    
    ws1[f'A{row}'] = "Doğum Tarihi:"
    ws1[f'B{row}'] = musteri.DogumTarihi.strftime('%d.%m.%Y') if musteri.DogumTarihi else 'Belirtilmemiş'
    row += 1
    
    if musteri.Adres:
        ws1[f'A{row}'] = "Adres:"
        ws1[f'B{row}'] = musteri.Adres
        row += 1
    
    if musteri.Notlar:
        ws1[f'A{row}'] = "Notlar:"
        ws1[f'B{row}'] = musteri.Notlar
        row += 1
    
    # Randevu istatistikleri
    row += 2
    ws1[f'A{row}'] = "Randevu İstatistikleri"
    ws1[f'A{row}'].font = Font(size=14, bold=True)
    row += 1
    
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    ws1[f'A{row}'] = "Toplam Randevu:"
    ws1[f'B{row}'] = toplam_randevu
    row += 1
    
    ws1[f'A{row}'] = "Tamamlanan:"
    ws1[f'B{row}'] = tamamlanan_randevu
    row += 1
    
    ws1[f'A{row}'] = "Beklemede:"
    ws1[f'B{row}'] = bekleyen_randevu
    row += 1
    
    ws1[f'A{row}'] = "İptal:"
    ws1[f'B{row}'] = iptal_randevu
    
    # Randevu geçmişi sayfası
    ws2 = wb.create_sheet("Randevu Geçmişi")
    
    # Başlıklar
    headers = ['Tarih', 'Saat', 'Defter', 'Durum', 'Notlar']
    for col, header in enumerate(headers, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
    
    # Randevu verileri
    for row_idx, randevu in enumerate(randevular, 2):
        defter_adi = 'Bilinmeyen'
        if randevu.DefterID:
            defter = RandevuDefterAyar.query.filter_by(AyarID=randevu.DefterID).first()
            if defter:
                defter_adi = defter.DefterAdi
        
        ws2.cell(row=row_idx, column=1, value=randevu.RandevuTarihi.strftime('%d.%m.%Y') if randevu.RandevuTarihi else '-')
        ws2.cell(row=row_idx, column=2, value=randevu.RandevuTarihi.strftime('%H:%M') if randevu.RandevuTarihi else '-')
        ws2.cell(row=row_idx, column=3, value=defter_adi)
        ws2.cell(row=row_idx, column=4, value=randevu.Durum)
        ws2.cell(row=row_idx, column=5, value=randevu.RandevuAciklamasi or '-')
    
    # Sütun genişliklerini ayarla
    for ws in [ws1, ws2]:
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
    
    # Excel dosyasını kaydet
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    # Dosya adı
    filename = f"musteri_detay_{musteri.MusteriAdi}_{musteri.MusteriSoyadi}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    # Çıktı alma (Excel) logla
    try:
        log_user_action('VIEW', 'Rapor', musteri_id, detail=f"Müşteri detay Excel indirildi: {musteri.MusteriAdi} {musteri.MusteriSoyadi}")
    except Exception:
        pass
    return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                    as_attachment=True, download_name=filename)

@app.route('/rapor/musteriler')
@login_required
def rapor_musteriler():
    # Modül izin kontrolü
    if not session.get('raporlar_modulu', False):
        flash('Bu sayfaya erişim yetkiniz yok', 'error')
        return redirect(url_for('dashboard'))
    """Müşteri raporu: filtreler, KPI'lar, tablo ve CSV dışa aktarım"""
    firma_id = session['firma_id']

    # Filtreler
    kategori_id = request.args.get('kategori_id', type=int)
    sadece_aktif = request.args.get('aktif', default='1')  # '1' aktif, '' hepsi
    iletisim_var = request.args.get('iletisim_var')  # 'telefon', 'email', 'herikisi'
    
    # Yeni filtreler
    yas_min = request.args.get('yas_min', type=int)
    yas_max = request.args.get('yas_max', type=int)
    cinsiyet = request.args.get('cinsiyet')
    dogum_tarihi = request.args.get('dogum_tarihi')
    sehir = request.args.get('sehir')
    ilce = request.args.get('ilce')
    
    format_tip = request.args.get('format')  # 'csv' ise CSV döndür

    # Plaka kodları - şehir isimleri dönüşüm tablosu
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }

    # Müşteri temel sorgusu
    musteri_query = Musteri.query.filter_by(FirmaID=firma_id)
    if sadece_aktif == '1':
        musteri_query = musteri_query.filter(Musteri.Aktif == True)
    elif sadece_aktif == '0':
        musteri_query = musteri_query.filter(Musteri.Aktif == False)
    if kategori_id:
        musteri_query = musteri_query.filter(Musteri.KategoriID == kategori_id)
    if iletisim_var == 'telefon':
        musteri_query = musteri_query.filter(Musteri.Telefon.isnot(None), Musteri.Telefon != '')
    elif iletisim_var == 'email':
        musteri_query = musteri_query.filter(Musteri.Email.isnot(None), Musteri.Email != '')
    elif iletisim_var == 'herikisi':
        musteri_query = musteri_query.filter(
            Musteri.Telefon.isnot(None), Musteri.Telefon != '',
            Musteri.Email.isnot(None), Musteri.Email != ''
        )
    
    # Yeni filtreler
    if yas_min is not None:
        musteri_query = musteri_query.filter(Musteri.Yas >= yas_min)
    if yas_max is not None:
        musteri_query = musteri_query.filter(Musteri.Yas <= yas_max)
    if cinsiyet:
        musteri_query = musteri_query.filter(Musteri.Cinsiyet == cinsiyet)
    if dogum_tarihi:
        try:
            dogum_tarihi_obj = datetime.strptime(dogum_tarihi, '%Y-%m-%d').date()
            musteri_query = musteri_query.filter(Musteri.DogumTarihi == dogum_tarihi_obj)
        except:
            pass
    if sehir:
        # Seçilen şehir ismini plaka koduna dönüştür
        sehir_to_plaka = {v: k for k, v in plaka_to_sehir.items()}
        plaka_kodu = sehir_to_plaka.get(sehir, sehir)  # Eğer şehir ismi plaka kodunda yoksa orijinal değeri kullan
        musteri_query = musteri_query.filter(Musteri.Sehir == plaka_kodu)
    if ilce:
        musteri_query = musteri_query.filter(Musteri.Ilce == ilce)

    musteriler = musteri_query.order_by(Musteri.MusteriAdi, Musteri.MusteriSoyadi).all()

    # KPI'lar
    toplam_musteri = Musteri.query.filter_by(FirmaID=firma_id).count()
    aktif_musteri = Musteri.query.filter_by(FirmaID=firma_id, Aktif=True).count()
    yeni_musteri = 0

    # Randevu istatistikleri (müşteri başına randevu sayısı)
    randevu_q = db.session.query(Randevu.MusteriID, db.func.count(Randevu.RandevuID).label('adet')) 
    randevu_q = randevu_q.filter(Randevu.FirmaID == firma_id, Randevu.MusteriID.isnot(None))
    randevu_q = randevu_q.group_by(Randevu.MusteriID)
    musteri_id_to_randevu_adet = {mid: adet for mid, adet in randevu_q.all()}

    # Top N müşteriler (randevu sayısına göre) - SQL Server için alt sorgu ile
    randevu_count_sq = (
        db.session.query(
            Randevu.MusteriID.label('mid'),
            db.func.count(Randevu.RandevuID).label('adet')
        )
        .filter(Randevu.FirmaID == firma_id, Randevu.MusteriID.isnot(None))
    )
    randevu_count_sq = randevu_count_sq.group_by(Randevu.MusteriID).subquery()

    top_q = (
        db.session.query(Musteri, randevu_count_sq.c.adet)
        .join(randevu_count_sq, randevu_count_sq.c.mid == Musteri.MusteriID)
        .filter(Musteri.FirmaID == firma_id)
    )
    if sadece_aktif == '1':
        top_q = top_q.filter(Musteri.Aktif == True)
    if kategori_id:
        top_q = top_q.filter(Musteri.KategoriID == kategori_id)
    # Müşterileri birleştir (ad+soyad+telefon)
    def _norm_name(v):
        return (v or '').strip().lower()
    def _norm_phone(v):
        v = ''.join(ch for ch in (v or '') if ch.isdigit())
        return v[-10:] if len(v) >= 10 else v

    merged = {}
    for m in musteriler:
        k = (_norm_name(m.MusteriAdi), _norm_name(m.MusteriSoyadi), _norm_phone(m.Telefon))
        if k not in merged:
            merged[k] = {
                'id': m.MusteriID,
                'ad': m.MusteriAdi,
                'soyad': m.MusteriSoyadi,
                'telefon': m.Telefon or '',
                'email': m.Email or '',
                'aktif': bool(m.Aktif),
                'kategori': m.kategori.KategoriAdi if m.kategori else None,
                'olusturma': m.OlusturmaTarihi,
                'randevu_sayisi': musteri_id_to_randevu_adet.get(m.MusteriID, 0)
            }
        else:
            it = merged[k]
            it['randevu_sayisi'] += musteri_id_to_randevu_adet.get(m.MusteriID, 0)
            if not it['email'] and m.Email:
                it['email'] = m.Email
            if not it['kategori'] and m.kategori:
                it['kategori'] = m.kategori.KategoriAdi
            it['aktif'] = it['aktif'] or bool(m.Aktif)
            if it['olusturma'] is None or (m.OlusturmaTarihi and m.OlusturmaTarihi < it['olusturma']):
                it['olusturma'] = m.OlusturmaTarihi

    merged_rows = list(merged.values())

    # En çok randevusu olan 10 müşteri (birleştirilmiş verilerden)
    top_musteriler = sorted(merged_rows, key=lambda x: x['randevu_sayisi'], reverse=True)[:10]

    # Export işlemleri
    if format_tip in ['csv', 'excel', 'pdf']:
        # Çıktı alma logla
        try:
            log_user_action('VIEW', 'Rapor', detail=f"Müşteri raporu {format_tip.upper()} indirildi")
        except Exception:
            pass
        
        if format_tip == 'csv':
            # CSV Export
            output = StringIO()
            writer = csv.writer(output, delimiter=';')
            writer.writerow(['MusteriID', 'Ad', 'Soyad', 'Telefon', 'Email', 'Aktif', 'Kategori', 'OlusturmaTarihi', 'RandevuSayisi'])
            for r in merged_rows:
                # Telefon numarasını Excel'de metin olarak tanıması için +90'dan sonra boşluk ekle
                telefon = r['telefon'] or ''
                if telefon and telefon.startswith('+90'):
                    telefon = telefon.replace('+90', '+90 ')  # +90'dan sonra boşluk ekle
                writer.writerow([
                    r['id'], r['ad'], r['soyad'], telefon, r['email'], 'Evet' if r['aktif'] else 'Hayır', r['kategori'] or '', (r['olusturma'].strftime('%Y-%m-%d %H:%M') if r['olusturma'] else ''), r['randevu_sayisi']
                ])
            output.seek(0)
            filename = f"musteri_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            data = output.getvalue().encode('utf-8-sig')
            return send_file(BytesIO(data), mimetype='text/csv; charset=utf-8', as_attachment=True, download_name=filename)
        
        elif format_tip == 'excel':
            # Excel Export
            wb = Workbook()
            ws = wb.active
            ws.title = "Müşteri Raporu"
            
            # Başlık satırı
            headers = ['Müşteri ID', 'Ad', 'Soyad', 'Telefon', 'Email', 'Aktif', 'Kategori', 'Oluşturma Tarihi', 'Randevu Sayısı']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
            
            # Veri satırları
            for row, r in enumerate(merged_rows, 2):
                telefon = r['telefon'] or ''
                if telefon and telefon.startswith('+90'):
                    telefon = telefon.replace('+90', '+90 ')
                
                ws.cell(row=row, column=1, value=r['id'])
                ws.cell(row=row, column=2, value=r['ad'])
                ws.cell(row=row, column=3, value=r['soyad'])
                ws.cell(row=row, column=4, value=telefon)
                ws.cell(row=row, column=5, value=r['email'])
                ws.cell(row=row, column=6, value='Evet' if r['aktif'] else 'Hayır')
                ws.cell(row=row, column=7, value=r['kategori'] or '')
                ws.cell(row=row, column=8, value=r['olusturma'].strftime('%Y-%m-%d %H:%M') if r['olusturma'] else '')
                ws.cell(row=row, column=9, value=r['randevu_sayisi'])
            
            # Sütun genişliklerini ayarla
            for column in ws.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Excel dosyasını kaydet
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            filename = f"musteri_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            return send_file(
                buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
        
        elif format_tip == 'pdf':
            # PDF Export
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
            
            # Türkçe font desteği
            try:
                pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/dejavu-sans.ttf'))
                pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/dejavu-sans-bold.ttf'))
                turkish_font = 'DejaVuSans'
                turkish_font_bold = 'DejaVuSans-Bold'
            except:
                try:
                    pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/arial.ttf'))
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
                    turkish_font = 'DejaVuSans'
                    turkish_font_bold = 'DejaVuSans-Bold'
                except:
                    turkish_font = 'Helvetica'
                    turkish_font_bold = 'Helvetica-Bold'
            
            # Stil tanımları
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=TA_CENTER, fontName=turkish_font_bold)
            
            # Başlık
            title = Paragraph("Müşteri Raporu", title_style)
            
            # Özet bilgiler
            summary_data = [
                ['Toplam Müşteri', str(toplam_musteri)],
                ['Aktif Müşteri', str(aktif_musteri)],
                ['Yeni Müşteri', str(yeni_musteri)]
            ]
            
            summary_table = Table(summary_data)
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), turkish_font),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            # Tablo verileri
            table_data = [['Müşteri ID', 'Ad', 'Soyad', 'Telefon', 'Email', 'Aktif', 'Kategori', 'Randevu Sayısı']]
            
            for r in merged_rows[:50]:  # İlk 50 kayıt
                telefon = r['telefon'] or ''
                if telefon and telefon.startswith('+90'):
                    telefon = telefon.replace('+90', '+90 ')
                
                table_data.append([
                    str(r['id']),
                    r['ad'],
                    r['soyad'],
                    telefon,
                    r['email'],
                    'Evet' if r['aktif'] else 'Hayır',
                    r['kategori'] or '',
                    str(r['randevu_sayisi'])
                ])
            
            # Tablo oluştur
            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), turkish_font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), turkish_font),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            # PDF oluştur
            elements = [title, Spacer(1, 12), summary_table, Spacer(1, 12), table]
            doc.build(elements)
            buffer.seek(0)
            
            filename = f"musteri_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            return send_file(
                buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )

    # Kategoriler dropdown için
    kategoriler = MusteriKategori.query.filter_by(FirmaID=firma_id).order_by(MusteriKategori.KategoriAdi).all()
    
    # Şehir ve ilçe seçenekleri
    sehirler = db.session.query(Musteri.Sehir).filter(
        Musteri.FirmaID == firma_id,
        Musteri.Sehir.isnot(None),
        Musteri.Sehir != ''
    ).distinct().order_by(Musteri.Sehir).all()
    
    
    # Plaka kodlarını şehir isimlerine dönüştür ve benzersiz hale getir
    sehir_listesi = []
    for s in sehirler:
        plaka = s[0]
        sehir_adi = plaka_to_sehir.get(plaka, plaka)  # Eğer plaka kodunda yoksa orijinal değeri kullan
        if sehir_adi not in sehir_listesi:
            sehir_listesi.append(sehir_adi)
    
    sehir_listesi.sort()  # Alfabetik sırala
    
    ilceler = db.session.query(Musteri.Ilce).filter(
        Musteri.FirmaID == firma_id,
        Musteri.Ilce.isnot(None),
        Musteri.Ilce != ''
    ).distinct().order_by(Musteri.Ilce).all()
    ilce_listesi = [i[0] for i in ilceler]
    
    # Grafik verileri
    # Cinsiyet dağılımı
    gender_stats = db.session.query(Musteri.Cinsiyet, db.func.count(Musteri.MusteriID)).filter(
        Musteri.FirmaID == firma_id
    ).group_by(Musteri.Cinsiyet).all()
    gender_data = {gender: count for gender, count in gender_stats if gender}
    
    # Yaş dağılımı (yaş grupları)
    age_groups = {
        '0-18': 0, '19-25': 0, '26-35': 0, '36-45': 0, '46-55': 0, '56-65': 0, '65+': 0
    }
    age_stats = db.session.query(Musteri.Yas).filter(
        Musteri.FirmaID == firma_id, Musteri.Yas.isnot(None)
    ).all()
    for (yas,) in age_stats:
        if yas <= 18:
            age_groups['0-18'] += 1
        elif yas <= 25:
            age_groups['19-25'] += 1
        elif yas <= 35:
            age_groups['26-35'] += 1
        elif yas <= 45:
            age_groups['36-45'] += 1
        elif yas <= 55:
            age_groups['46-55'] += 1
        elif yas <= 65:
            age_groups['56-65'] += 1
        else:
            age_groups['65+'] += 1
    
    # Kategori dağılımı
    category_stats = db.session.query(
        MusteriKategori.KategoriAdi, db.func.count(Musteri.MusteriID)
    ).join(Musteri, Musteri.KategoriID == MusteriKategori.KategoriID).filter(
        Musteri.FirmaID == firma_id
    ).group_by(MusteriKategori.KategoriAdi).all()
    category_data = {kategori: count for kategori, count in category_stats}
    
    # Şehir dağılımı (top 10)
    city_stats = db.session.query(
        Musteri.Sehir, db.func.count(Musteri.MusteriID)
    ).filter(
        Musteri.FirmaID == firma_id, Musteri.Sehir.isnot(None), Musteri.Sehir != ''
    ).group_by(Musteri.Sehir).order_by(db.func.count(Musteri.MusteriID).desc()).limit(10).all()
    city_data = {sehir: count for sehir, count in city_stats}

    # Görüntülenecek satırlar için zenginleştirme
    rows = []
    for r in merged_rows:
        rows.append({
            'id': r['id'],
            'ad': r['ad'],
            'soyad': r['soyad'],
            'tam_ad': f"{r['ad']} {r['soyad']}".strip(),
            'telefon': r['telefon'],
            'email': r['email'],
            'aktif': r['aktif'],
            'kategori': r['kategori'],
            'olusturma': r['olusturma'],
            'randevu_sayisi': r['randevu_sayisi']
        })

    # Zaman serisi analizi - Aylık müşteri artışı
    monthly_data = {}
    for m in musteriler:
        if m.OlusturmaTarihi:
            month_key = m.OlusturmaTarihi.strftime('%Y-%m')
            monthly_data[month_key] = monthly_data.get(month_key, 0) + 1
    
    # Zaman serisi analizi - Haftalık müşteri artışı (son 12 hafta)
    weekly_data = {}
    today = datetime.now().date()
    
    # Son 12 hafta için haftalık veriler
    for i in range(12):
        week_start = today - timedelta(weeks=i+1)
        week_end = today - timedelta(weeks=i)
        week_key = f"{week_start.strftime('%Y-%m-%d')} - {week_end.strftime('%Y-%m-%d')}"
        weekly_data[week_key] = 0
    
    for m in musteriler:
        if m.OlusturmaTarihi:
            m_date = m.OlusturmaTarihi.date()
            for i in range(12):
                week_start = today - timedelta(weeks=i+1)
                week_end = today - timedelta(weeks=i)
                if week_start <= m_date < week_end:
                    week_key = f"{week_start.strftime('%Y-%m-%d')} - {week_end.strftime('%Y-%m-%d')}"
                    weekly_data[week_key] = weekly_data.get(week_key, 0) + 1
                    break
    
    # Randevu trendleri - Müşteri başına randevu sayısı analizi
    from collections import defaultdict
    
    # Müşteri başına randevu sayısı dağılımı
    randevu_sayisi_dagilimi = defaultdict(int)
    for m in musteriler:
        randevu_sayisi = musteri_id_to_randevu_adet.get(m.MusteriID, 0)
        randevu_sayisi_dagilimi[randevu_sayisi] += 1
    
    # En çok randevu alan müşteriler (top 10)
    en_cok_randevu_alan = []
    for m in musteriler:
        randevu_sayisi = musteri_id_to_randevu_adet.get(m.MusteriID, 0)
        if randevu_sayisi > 0:
            en_cok_randevu_alan.append({
                'musteri_adi': f"{m.MusteriAdi} {m.MusteriSoyadi}",
                'randevu_sayisi': randevu_sayisi
            })
    
    # Randevu sayısına göre sırala (azalan)
    en_cok_randevu_alan.sort(key=lambda x: x['randevu_sayisi'], reverse=True)
    en_cok_randevu_alan = en_cok_randevu_alan[:10]
    
    # Randevu sıklığı analizi (0, 1, 2-5, 6-10, 10+ randevu)
    randevu_siklik_dagilimi = {
        '0 Randevu': 0,
        '1 Randevu': 0,
        '2-5 Randevu': 0,
        '6-10 Randevu': 0,
        '10+ Randevu': 0
    }
    
    for m in musteriler:
        randevu_sayisi = musteri_id_to_randevu_adet.get(m.MusteriID, 0)
        if randevu_sayisi == 0:
            randevu_siklik_dagilimi['0 Randevu'] += 1
        elif randevu_sayisi == 1:
            randevu_siklik_dagilimi['1 Randevu'] += 1
        elif 2 <= randevu_sayisi <= 5:
            randevu_siklik_dagilimi['2-5 Randevu'] += 1
        elif 6 <= randevu_sayisi <= 10:
            randevu_siklik_dagilimi['6-10 Randevu'] += 1
        else:
            randevu_siklik_dagilimi['10+ Randevu'] += 1
    
    return render_template(
        'rapor_musteriler.html',
        rows=rows,
        toplam_musteri=toplam_musteri,
        aktif_musteri=aktif_musteri,
        yeni_musteri=yeni_musteri,
        top_musteriler=top_musteriler,
        kategoriler=kategoriler,
        sehir_listesi=sehir_listesi,
        ilce_listesi=ilce_listesi,
        gender_data=gender_data,
        age_groups=age_groups,
        category_data=category_data,
        city_data=city_data,
        monthly_data=monthly_data,
        weekly_data=weekly_data,
        randevu_sayisi_dagilimi=dict(randevu_sayisi_dagilimi),
        en_cok_randevu_alan=en_cok_randevu_alan,
        randevu_siklik_dagilimi=randevu_siklik_dagilimi,
        filtreler={
            'kategori_id': kategori_id or '',
            'aktif': sadece_aktif,
            'iletisim_var': iletisim_var or '',
            'yas_min': yas_min or '',
            'yas_max': yas_max or '',
            'cinsiyet': cinsiyet or '',
            'dogum_tarihi': dogum_tarihi or '',
            'sehir': sehir or '',
            'ilce': ilce or ''
        }
    )

@app.route('/randevu/<int:randevu_id>/duzenle', methods=['GET', 'POST'])
@login_required
def randevu_duzenle(randevu_id):
    """Randevu düzenleme sayfası"""
    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first_or_404()
    
    # Yetki kontrolü
    if not session.get('is_admin', False) and randevu.OlusturanKullaniciID != session['user_id']:
        flash('Bu randevuyu düzenleme yetkiniz yok', 'error')
        return redirect(url_for('randevular'))
    
    if request.method == 'POST':
        try:
            # Form verilerini al
            tarih_gun = request.form.get('tarih_gun')
            saat = request.form.get('saat')
            referans_id = request.form.get('referans_id', type=int)
            randevu_suresi = request.form.get('randevu_suresi', type=int)
            randevu_notlar = request.form.get('randevu_notlar', '').strip()
            atanan_kullanici_id = request.form.get('atanan_kullanici', type=int)
            
            if not tarih_gun or not saat or not randevu_suresi:
                flash('Lütfen tüm zorunlu alanları doldurun', 'error')
                return redirect(url_for('randevu_duzenle', randevu_id=randevu_id))
            
            # Tarih/saat birleştir
            try:
                randevu_dt = datetime.strptime(f"{tarih_gun} {saat}", '%Y-%m-%d %H:%M')
            except ValueError:
                flash('Tarih/saat formatı geçersiz', 'error')
                return redirect(url_for('randevu_duzenle', randevu_id=randevu_id))
            
            # Referans bilgisini güncelle
            ref = None
            if referans_id:
                ref = RandevuReferans.query.filter_by(ReferansID=referans_id, FirmaID=session['firma_id']).first()
            
            # Log için eski değerleri yakala
            old_data = {}
            new_data = {}

            # Randevu bilgilerini güncelle
            randevu.RandevuTarihi = randevu_dt
            randevu.RandevuSuresi = randevu_suresi
            randevu.RandevuNotlar = randevu_notlar
            randevu.GuncellemeTarihi = datetime.now()

            
            # Referans güncelle - başlık otomatik olarak referans adı olur
            if ref:
                # Başlık değişimi logu için kontrol et
                if randevu.RandevuBaslik != ref.Ad:
                    old_data.setdefault('randevu', {})['baslik'] = randevu.RandevuBaslik
                    new_data.setdefault('randevu', {})['baslik'] = ref.Ad
                randevu.RandevuBaslik = ref.Ad
            else:
                # Referans seçilmediyse mevcut başlığı koru
                pass
            
            # Müşteri bilgilerini güncelle (eğer müşteri varsa)
            if randevu.musteri:
                # Müşteri alanları için eski değerleri yakala
                old_musteri = {
                    'telefon': randevu.musteri.Telefon,
                    'email': randevu.musteri.Email,
                    'cinsiyet': randevu.musteri.Cinsiyet,
                    'dogum_tarihi': randevu.musteri.DogumTarihi.strftime('%Y-%m-%d') if randevu.musteri.DogumTarihi else None,
                    'yas': randevu.musteri.Yas,
                }
                # Telefon numarasını ülke kodu ile birleştir
                telefon_ulke_kodu = request.form.get('telefon_ulke_kodu', '+90')
                telefon_numara = request.form.get('musteri_telefon', '').replace(' ', '')
                tam_telefon = f"{telefon_ulke_kodu}{telefon_numara}" if telefon_numara else ''
                
                musteri_email = request.form.get('musteri_email', '').strip()
                musteri_cinsiyet = request.form.get('musteri_cinsiyet', '').strip()
                
                # Doğum tarihi ve yaş güncelleme
                dogum_tarihi = request.form.get('musteri_dogum_tarihi')
                if dogum_tarihi:
                    randevu.musteri.DogumTarihi = datetime.strptime(dogum_tarihi, '%Y-%m-%d').date()
                    # Yaşı hesapla
                    bugun = datetime.now().date()
                    yas = bugun.year - randevu.musteri.DogumTarihi.year
                    if (bugun.month, bugun.day) < (randevu.musteri.DogumTarihi.month, randevu.musteri.DogumTarihi.day):
                        yas -= 1
                    randevu.musteri.Yas = yas
                elif request.form.get('musteri_yas'):
                    randevu.musteri.Yas = request.form.get('musteri_yas', type=int)
                
                if tam_telefon:
                    randevu.musteri.Telefon = tam_telefon
                if musteri_email:
                    randevu.musteri.Email = musteri_email
                if musteri_cinsiyet:
                    randevu.musteri.Cinsiyet = musteri_cinsiyet
                
                randevu.musteri.GuncellemeTarihi = datetime.now()

                # Yeni müşteri değerleri ve farkları hesapla
                new_musteri = {
                    'telefon': randevu.musteri.Telefon,
                    'email': randevu.musteri.Email,
                    'cinsiyet': randevu.musteri.Cinsiyet,
                    'dogum_tarihi': randevu.musteri.DogumTarihi.strftime('%Y-%m-%d') if randevu.musteri.DogumTarihi else None,
                    'yas': randevu.musteri.Yas,
                }
                for key in new_musteri:
                    if old_musteri.get(key) != new_musteri.get(key):
                        old_data.setdefault('musteri', {})[key] = old_musteri.get(key)
                        new_data.setdefault('musteri', {})[key] = new_musteri.get(key)

            # Randevu alanları için farkları hesapla
            # Not: Tarih ve süre değişimi
            # Eski değerleri hesaplamak için form öncesi değerleri kullanmak gerekir; randevu objesinde artık yenisi var.
            # Bu nedenle formdan gelenlerle karşılaştırıp log detail'inde belirtelim.
            try:
                if randevu.RandevuNotlar != randevu_notlar:
                    old_data.setdefault('randevu', {})['notlar'] = randevu.RandevuNotlar
                    new_data.setdefault('randevu', {})['notlar'] = randevu_notlar
            except Exception:
                pass
            # Tarih ve süreyi açıkça logla
            # Bu alanlarda eski değer commit öncesi elimizde olmadığı için kullanıcıya anlaşılır detail verisi ekleyeceğiz
            # (taşıma API'sinde olduğu gibi detay mesajı oluşturulacak)
            
            db.session.commit()
            
            # Otomatik görev oluşturma - Seçilen kullanıcıya
            if atanan_kullanici_id:
                try:
                    # Görev başlığı oluştur
                    musteri_adi = f"{randevu.MusteriAdi} {randevu.MusteriSoyadi}".strip() if randevu.MusteriAdi else "Müşteri"
                    gorev_baslik = f"Randevu: {musteri_adi} - {randevu_dt.strftime('%d.%m.%Y %H:%M')}"
                    
                    # Görev açıklaması oluştur
                    gorev_aciklama = f"Randevu Detayları:\n"
                    gorev_aciklama += f"• Müşteri: {musteri_adi}\n"
                    gorev_aciklama += f"• Tarih: {randevu_dt.strftime('%d.%m.%Y %H:%M')}\n"
                    gorev_aciklama += f"• Süre: {randevu_suresi} dakika\n"
                    if randevu_notlar:
                        gorev_aciklama += f"• Açıklama: {randevu_notlar}\n"
                    if ref:
                        gorev_aciklama += f"• Referans: {ref.Ad}\n"
                    
                    # Yeni görev oluştur (randevu bazlı)
                    yeni_gorev = Todo(
                        KullaniciID=atanan_kullanici_id,
                        Baslik=gorev_baslik,
                        Aciklama=gorev_aciklama,
                        Oncelik='Orta',
                        Durum='Beklemede',
                        Tip='Randevu',  # Randevu bazlı görev
                        BitisTarihi=randevu_dt,  # DateTime olarak
                        HatirlatmaTarihi=randevu_dt  # DateTime olarak
                    )
                    
                    db.session.add(yeni_gorev)
                    db.session.commit()
                    
                    # Log ekle
                    try:
                        log_user_action(
                            action_type='Görev Oluşturuldu',
                            table_name='Todos',
                            record_id=yeni_gorev.TodoID,
                            old_data=None,
                            new_data={'baslik': gorev_baslik, 'kullanici_id': atanan_kullanici_id},
                            detail=f"Randevu bazlı görev: {musteri_adi}"
                        )
                    except Exception as log_error:
                        print(f"Görev log hatası (önemli değil): {log_error}")
                    
                    print(f"Randevu bazlı görev oluşturuldu: {gorev_baslik} (Kullanıcı: {atanan_kullanici_id})")
                    
                except Exception as gorev_error:
                    print(f"Görev oluşturma hatası: {gorev_error}")
                    # Görev oluşturma hatası randevu güncellemeyi etkilemesin
            
            # Değişiklik varsa logla
            try:
                detail_msg = 'Randevu ve/veya müşteri bilgileri güncellendi'
                if old_data or new_data:
                    log_user_action('UPDATE', 'Randevu', randevu_id, old_data=old_data or None, new_data=new_data or None, detail=detail_msg)
            except Exception:
                pass

            flash('Randevu ve müşteri bilgileri başarıyla güncellendi', 'success')
            return redirect(url_for('randevu_detay', randevu_id=randevu_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Randevu güncellenirken hata: {str(e)}', 'error')
            return redirect(url_for('randevu_duzenle', randevu_id=randevu_id))
    
    # GET request - formu doldur
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuReferans.Ad).all()
    
    # Randevunun defteri ayarlarını al (minimum süre için)
    defter_ayar = None
    if randevu.DefterID:
        defter_ayar = RandevuDefterAyar.query.filter_by(
            AyarID=randevu.DefterID,
            FirmaID=session['firma_id'], 
            Aktif=True
        ).first()
    
    # Minimum süre: randevunun defter ayarındaki slot dakikası, yoksa varsayılan 30 dakika
    min_sure = defter_ayar.SlotDakika if defter_ayar else 30
    
    return render_template('randevu_duzenle.html', 
                         randevu=randevu, 
                         referanslar=referanslar,
                         min_sure=min_sure)

@app.route('/randevu/ekle', methods=['GET', 'POST'])
@login_required
def randevu_ekle():
    if request.method == 'POST':
        # JSON veya form verilerini al
        if request.is_json:
            data = request.get_json()
            tarih_gun = data.get('tarih_gun')
            saat = data.get('selected_saat')
            defter_id = data.get('defter_id', type=int)
            referans_id = data.get('referans_id', type=int)
            islem_id = data.get('islem_id', type=int)
            gorev_id = data.get('gorev_id', type=int)
            musteri_adi = data.get('musteri_adi', '')
            musteri_soyadi = data.get('musteri_soyadi', '')
            telefon = data.get('telefon', '')
            email = data.get('email', '')
            aciklama = data.get('aciklama', '')
            randevu_suresi = data.get('sure', 60)
        else:
            # Form alanlarini guvenle al
            tarih_gun = request.form.get('tarih_gun')
            saat = request.form.get('saat')
            defter_id = request.form.get('defter_id', type=int)
            referans_id = request.form.get('referans_id', type=int)
            islem_id = request.form.get('islem_id', type=int)
            gorev_id = request.form.get('gorev_id', type=int)  # Görev ID'si
            musteri_adi = request.form.get('musteri_adi', '')
            musteri_soyadi = request.form.get('musteri_soyadi', '')
            telefon = request.form.get('telefon', '')
            email = request.form.get('email', '')
            aciklama = request.form.get('aciklama', '')
            randevu_suresi = int(request.form.get('sure', 60))
        if not tarih_gun or not saat or not defter_id:
            flash('Lütfen tarih, saat ve randevu defteri seçin', 'error')
            return redirect(url_for('randevu_ekle'))
        # Referans istege bagli; yok ise "Yok" kullan
        try:
            randevu_dt = datetime.strptime(f"{tarih_gun} {saat}", '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Tarih/saat formatı geçersiz', 'error')
            return redirect(url_for('randevu_ekle'))

        # Geçmiş tarih/saat için koruma
        now_local = datetime.now()
        if randevu_dt < now_local:
            flash('Geçmiş tarihe veya saate randevu verilemez', 'error')
            return redirect(url_for('randevu_ekle'))

        # Seçilen defteri kontrol et
        defter_ayar = RandevuDefterAyar.query.filter_by(
            AyarID=defter_id, 
            FirmaID=session['firma_id'], 
            Aktif=True
        ).first()
        if not defter_ayar:
            flash('Seçilen randevu defteri bulunamadı', 'error')
            return redirect(url_for('randevu_ekle'))
        
        # Süre validation - slot dakikasının katı olmalı
        if randevu_suresi % defter_ayar.SlotDakika != 0:
            flash(f'Randevu süresi {defter_ayar.SlotDakika} dakikanın katları olmalı', 'error')
            return redirect(url_for('randevu_ekle'))

        # Çakışan randevu ve blok kontrolü - Optimistic Locking ile güçlendirilmiş
        randevu_bas = randevu_dt
        randevu_bit = randevu_dt + timedelta(minutes=randevu_suresi)

        # 1) Mevcut randevularla çakışma kontrolü (Optimistic Locking)
        day_start_chk = datetime(randevu_dt.year, randevu_dt.month, randevu_dt.day, 0, 0)
        day_end_chk = day_start_chk + timedelta(days=1)
        
        # İlk kontrol - genel çakışma
        existing_for_defter = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID == defter_id,
            Randevu.RandevuTarihi >= day_start_chk,
            Randevu.RandevuTarihi < day_end_chk,
            Randevu.Durum != 'Iptal'  # İptal edilen randevuları hariç tut
        ).all()
        
        for r in existing_for_defter:
            r_start = r.RandevuTarihi
            r_dur = r.RandevuSuresi or 60
            r_end = r_start + timedelta(minutes=int(r_dur))
            if r_start < randevu_bit and randevu_bas < r_end:
                flash('Seçilen saat aralığında mevcut randevu var', 'error')
                return redirect(url_for('randevu_ekle'))

        # 2) Bloklarla çakışma
        from sqlalchemy import or_, and_
        gun = randevu_dt.date()
        bloklar = db.session.query(RandevuDefterBlok).filter(
            RandevuDefterBlok.FirmaID == session['firma_id'],
            RandevuDefterBlok.Aktif == True,
            RandevuDefterBlok.BaslangicTarih <= gun,
            or_(RandevuDefterBlok.BitisTarih == None, RandevuDefterBlok.BitisTarih >= gun),
            or_(RandevuDefterBlok.DefterID == None, RandevuDefterBlok.DefterID == defter_id)
        ).all()

        def is_blocked_interval(bas: datetime, bit: datetime) -> bool:
            for b in bloklar:
                # Saat verilmemişse tüm gün kapalı
                if not b.SaatBaslangic or not b.SaatBitis:
                    return True
                try:
                    bh, bm = map(int, b.SaatBaslangic.split(':'))
                    eh, em = map(int, b.SaatBitis.split(':'))
                except Exception:
                    continue
                b_bas = datetime(gun.year, gun.month, gun.day, bh, bm)
                b_bit = datetime(gun.year, gun.month, gun.day, eh, em)
                if b_bas < bit and bas < b_bit:
                    return True
            return False

        if is_blocked_interval(randevu_bas, randevu_bit):
            flash('Seçilen saat aralığı kapalı (bloklandı)', 'error')
            return redirect(url_for('randevu_ekle'))

        # Referans basligini cek (varsa)
        ref = None
        if referans_id:
            ref = RandevuReferans.query.filter_by(ReferansID=referans_id, FirmaID=session['firma_id']).first()

        # Müşteri işlemleri
        secilen_musteri_id = request.form.get('secilen_musteri_id')
        musteri_id = None
        
        if secilen_musteri_id:
            # Mevcut müşteri seçildi
            musteri_id = int(secilen_musteri_id)
            musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=session['firma_id']).first()
            if not musteri:
                flash('Seçilen müşteri bulunamadı', 'error')
                return redirect(url_for('randevu_ekle'))
            
            # Müşteri bilgilerini güncelle
            musteri.Sehir = request.form.get('musteri_sehir', '') or musteri.Sehir
            musteri.Ilce = request.form.get('musteri_ilce', '') or musteri.Ilce
            musteri.Adres = request.form.get('musteri_adres', '') or musteri.Adres
            musteri.Cinsiyet = request.form.get('musteri_cinsiyet', '') or musteri.Cinsiyet
            musteri.KategoriID = request.form.get('musteri_kategori', type=int) or musteri.KategoriID
            musteri.Notlar = request.form.get('musteri_notlar', '') or musteri.Notlar
            
            # Doğum tarihi ve yaş güncelleme
            dogum_tarihi = request.form.get('musteri_dogum_tarihi')
            if dogum_tarihi:
                musteri.DogumTarihi = datetime.strptime(dogum_tarihi, '%Y-%m-%d').date()
                # Yaşı hesapla
                bugun = datetime.now().date()
                yas = bugun.year - musteri.DogumTarihi.year
                if (bugun.month, bugun.day) < (musteri.DogumTarihi.month, musteri.DogumTarihi.day):
                    yas -= 1
                musteri.Yas = yas
            elif request.form.get('musteri_yas'):
                musteri.Yas = request.form.get('musteri_yas', type=int)
            
            db.session.commit()
        else:
            # Telefon numarasını ülke kodu ile birleştir
            telefon_ulke_kodu = request.form.get('telefon_ulke_kodu', '+90')
            telefon_numara = request.form.get('musteri_telefon', '').replace(' ', '')
            tam_telefon = f"{telefon_ulke_kodu}{telefon_numara}" if telefon_numara else ''
            
            # Doğum tarihi ve yaş hesaplama
            dogum_tarihi = request.form.get('musteri_dogum_tarihi')
            yas = None
            if dogum_tarihi:
                dogum_tarihi_obj = datetime.strptime(dogum_tarihi, '%Y-%m-%d').date()
                # Yaşı hesapla
                bugun = datetime.now().date()
                yas = bugun.year - dogum_tarihi_obj.year
                if (bugun.month, bugun.day) < (dogum_tarihi_obj.month, dogum_tarihi_obj.day):
                    yas -= 1
            elif request.form.get('musteri_yas'):
                yas = request.form.get('musteri_yas', type=int)
            
            # Yeni müşteri oluştur
            musteri = Musteri(
                FirmaID=session['firma_id'],
                MusteriAdi=request.form['musteri_adi'],
                MusteriSoyadi=request.form.get('musteri_soyadi', 'Müşteri'),
                Telefon=tam_telefon,
                Email=request.form.get('musteri_email', ''),
                # Yeni adres alanları
                Ulke=request.form.get('musteri_ulke', 'Türkiye'),
                Sehir=request.form.get('musteri_sehir', ''),
                Ilce=request.form.get('musteri_ilce', ''),
                Adres=request.form.get('musteri_adres', ''),
                Cinsiyet=request.form.get('musteri_cinsiyet', ''),
                KategoriID=request.form.get('musteri_kategori', type=int) or None,
                Notlar=request.form.get('musteri_notlar', ''),
                DogumTarihi=dogum_tarihi_obj if dogum_tarihi else None,
                Yas=yas
            )
            db.session.add(musteri)
            db.session.flush()  # ID'yi almak için
            musteri_id = musteri.MusteriID

        # OPTIMISTIC LOCKING: Randevu oluşturmadan hemen önce son kontrol
        # Bu, eş zamanlı randevu oluşturma girişimlerini engeller
        final_check = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID == defter_id,
            Randevu.RandevuTarihi >= day_start_chk,
            Randevu.RandevuTarihi < day_end_chk,
            Randevu.Durum != 'Iptal'
        ).all()
        
        for r in final_check:
            r_start = r.RandevuTarihi
            r_dur = r.RandevuSuresi or 60
            r_end = r_start + timedelta(minutes=int(r_dur))
            if r_start < randevu_bit and randevu_bas < r_end:
                flash('Bu slot başka bir kullanıcı tarafından rezerve edildi. Lütfen başka bir saat seçin.', 'error')
                return redirect(url_for('randevu_ekle'))

        # Görev bilgilerini al (eğer görev ID'si varsa)
        gorev_baslik = 'Yok'
        gorev_aciklama = ''
        if gorev_id:
            gorev = Todo.query.filter_by(TodoID=gorev_id, KullaniciID=session['user_id'], Tip='Randevu').first()
            if gorev:
                gorev_baslik = gorev.Baslik
                gorev_aciklama = gorev.Aciklama or ''
        
        randevu = Randevu(
            RandevuBaslik=(ref.Ad if ref else gorev_baslik),
            RandevuAciklamasi=aciklama or gorev_aciklama,
            RandevuTarihi=randevu_dt,
            RandevuSuresi=randevu_suresi,
            MusteriAdi=musteri_adi,
            MusteriSoyadi=musteri_soyadi or 'Müşteri',
            MusteriTelefon=telefon,
            MusteriEmail=email,
            MusteriID=musteri_id,  # Müşteri ID'sini ekle
            IslemID=islem_id,  # İşlem ID'sini ekle
            OlusturanKullaniciID=session['user_id'],
            FirmaID=session['firma_id'],
            DefterID=defter_id  # Defter ID'sini ekle
        )
        
        try:
            db.session.add(randevu)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return jsonify({'success': False, 'message': 'Randevu oluşturulurken bir hata oluştu. Lütfen tekrar deneyin.'})
            flash('Randevu oluşturulurken bir hata oluştu. Lütfen tekrar deneyin.', 'error')
            return redirect(url_for('randevu_ekle'))

        # Eğer görev ID'si varsa, görevi sil (randevu oluşturuldu)
        if gorev_id:
            try:
                gorev = Todo.query.filter_by(TodoID=gorev_id, KullaniciID=session['user_id'], Tip='Randevu').first()
                if gorev:
                    db.session.delete(gorev)
                    print(f"Görev silindi: {gorev.Baslik}")
            except Exception as e:
                print(f"Görev silinirken hata: {e}")

        # Otomatik görev oluşturma - Seçilen kullanıcıya
        atanan_kullanici_id = request.form.get('atanan_kullanici', type=int)
        if atanan_kullanici_id:
            try:
                # Görev başlığı oluştur
                musteri_adi = f"{request.form['musteri_adi']} {request.form.get('musteri_soyadi', '')}".strip()
                gorev_baslik = f"Randevu: {musteri_adi} - {randevu_dt.strftime('%d.%m.%Y %H:%M')}"
                
                # Görev açıklaması oluştur
                gorev_aciklama = f"Randevu Detayları:\n"
                gorev_aciklama += f"• Müşteri: {musteri_adi}\n"
                gorev_aciklama += f"• Tarih: {randevu_dt.strftime('%d.%m.%Y %H:%M')}\n"
                gorev_aciklama += f"• Süre: {randevu_suresi} dakika\n"
                if request.form.get('aciklama'):
                    gorev_aciklama += f"• Açıklama: {request.form.get('aciklama')}\n"
                if ref:
                    gorev_aciklama += f"• Referans: {ref.Ad}\n"
                
                # Yeni görev oluştur (randevu bazlı)
                yeni_gorev = Todo(
                    KullaniciID=atanan_kullanici_id,
                    Baslik=gorev_baslik,
                    Aciklama=gorev_aciklama,
                    Oncelik='Orta',
                    Durum='Beklemede',
                    Tip='Randevu',  # Randevu bazlı görev
                    BitisTarihi=randevu_dt,  # DateTime olarak
                    HatirlatmaTarihi=randevu_dt  # DateTime olarak
                )
                
                db.session.add(yeni_gorev)
                db.session.commit()
                
                # Log ekle
                try:
                    log_user_action(
                        action_type='Görev Oluşturuldu',
                        table_name='Todos',
                        record_id=yeni_gorev.TodoID,
                        old_data=None,
                        new_data={'baslik': gorev_baslik, 'kullanici_id': atanan_kullanici_id},
                        detail=f"Randevu bazlı görev: {musteri_adi}"
                    )
                except Exception as log_error:
                    print(f"Görev log hatası (önemli değil): {log_error}")
                
                print(f"Randevu bazlı görev oluşturuldu: {gorev_baslik} (Kullanıcı: {atanan_kullanici_id})")
                
            except Exception as gorev_error:
                print(f"Görev oluşturma hatası: {gorev_error}")
                # Görev oluşturma hatası randevu oluşturmayı etkilemesin

        # SMS: randevu olusturuldugunda gonder
        try:
            sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).first()
            if sms_ayar and sms_ayar.SMSGonderOnCreate and randevu.MusteriTelefon:
                sms_text = (sms_ayar.VarsayilanSMSMetni or "Merhaba {MUSTERI_ADI}, {RANDEVU_TARIH} tarihindeki randevunuzu hatırlatırız.")
                # Ad + Soyad birlestir
                try:
                    if randevu.musteri and randevu.musteri.MusteriSoyadi:
                        full_name = f"{randevu.musteri.MusteriAdi} {randevu.musteri.MusteriSoyadi}".strip()
                    else:
                        full_name = (randevu.MusteriAdi or '').strip()
                except Exception:
                    full_name = (randevu.MusteriAdi or '').strip()

                sms_text = sms_text.replace('{MUSTERI_ADI}', full_name or '-')\
                                   .replace('{RANDEVU_TARIH}', randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M'))
                # Defter adi
                try:
                    defter_adi = randevu.defter.DefterAdi if randevu.defter else ''
                except Exception:
                    defter_adi = ''
                sms_text = sms_text.replace('{DEFTER_ADI}', defter_adi)
                send_sms_with_firma_settings(session['firma_id'], randevu.MusteriTelefon, sms_text)
        except Exception as e:
            print(f"Randevu olusturuldu SMS gonderim hatasi: {e}")

        # SMS: 24 saat once hatirlatma kaydi
        try:
            sms_ayar = sms_ayar or FirmaSMSAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).first()
            if sms_ayar and sms_ayar.SMSGonder24SaatOnce and randevu.MusteriTelefon:
                s = RandevuSMSHatirlatma(
                    RandevuID=randevu.RandevuID,
                    FirmaID=session['firma_id'],
                    RecipientPhone=randevu.MusteriTelefon,
                    MinutesBefore=1440
                )
                db.session.add(s)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"SMS hatirlatma kaydi olusurken hata: {e}")

        # Varsayilan: 60 ve 10 dk once hatirlatma (email varsa)
        try:
            if randevu.MusteriEmail:
                for before in [60, 10]:
                    h = RandevuHatirlatma(
                        RandevuID=randevu.RandevuID,
                        FirmaID=session['firma_id'],
                        RecipientEmail=randevu.MusteriEmail,
                        MinutesBefore=before
                    )
                    db.session.add(h)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Hatirlatma kaydi olusurken hata: {e}")

        # Bildirim: randevu olusturuldu (olusturana ve varsa yetkili kullanicilara)
        try:
            b = Bildirim(
                KullaniciID=session['user_id'],
                FirmaID=session['firma_id'],
                Metin=f"{randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M')} için randevu oluşturuldu",
                Tip='randevu',
                IlgiliRandevuID=randevu.RandevuID
            )
            db.session.add(b)
            db.session.commit()
        except Exception:
            db.session.rollback()
        
        # Olusturan kullaniciya tam yetki ver
        if _assert_same_firm_for_permission(session['user_id'], randevu.RandevuID):
            randevu_yetki = RandevuYetki(
                RandevuID=randevu.RandevuID,
                KullaniciID=session['user_id'],
                GoruntulemeYetkisi=True,
                DuzenlemeYetkisi=True,
                SilmeYetkisi=True
            )
            db.session.add(randevu_yetki)
            db.session.commit()
        else:
            flash('Farklı firmaya yetki verilemez', 'error')
        
        # Randevu oluşturulduğunda müşteriye e-posta gönder (e-posta varsa)
        if randevu.MusteriEmail:
            subject = f"Randevu Onayı - {randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M')}"
            body = (
                f"Merhaba {randevu.MusteriAdi or 'Değerli Müşterimiz'},\n\n"
                f"{randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M')} tarihinde randevunuz başarıyla oluşturulmuştur.\n"
                f"Referans: {randevu.RandevuBaslik}\n"
                f"Süre: {randevu.RandevuSuresi or 60} dakika\n\n"
                f"Randevu detayları için bizimle iletişime geçebilirsiniz.\n\n"
                f"İyi günler dileriz."
            )
            # Firma ayarlarını kullan, yoksa genel ayarları kullan
            email_sent = send_email_with_firma_settings(randevu.FirmaID, randevu.MusteriEmail, subject, body)
            if not email_sent:
                send_email_simple(randevu.MusteriEmail, subject, body)
        
        # WhatsApp mesajı gönder (eğer ayar aktifse)
        try:
            whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).first()
            if whatsapp_ayar and whatsapp_ayar.MesajGonderOnCreate and whatsapp_ayar.RandevuOlusturmaMesaji:
                # Telefon numarasını temizle (sadece rakamlar)
                phone_clean = ''.join(filter(str.isdigit, randevu.MusteriTelefon))
                if phone_clean and len(phone_clean) >= 10:
                    # Mesaj şablonunu değişkenlerle doldur
                    message = whatsapp_ayar.RandevuOlusturmaMesaji
                    message = message.replace('{musteri_adi}', randevu.MusteriAdi or 'Müşteri')
                    message = message.replace('{tarih}', randevu_dt.strftime('%d.%m.%Y'))
                    message = message.replace('{saat}', randevu_dt.strftime('%H:%M'))
                    message = message.replace('{defter}', defter_ayar.DefterAdi)
                    message = message.replace('{referans}', randevu.Referans.Ad if randevu.Referans else 'Yok')
                    
                    # WhatsApp mesajı gönder
                    success, result = send_whatsapp_message(phone_clean, message, session['firma_id'])
                    if not success:
                        print(f"WhatsApp mesajı gönderilemedi: {result}")
        except Exception as e:
            print(f"WhatsApp mesajı gönderme hatası: {str(e)}")
        
        # Randevu oluşturma logla
        log_user_action('CREATE', 'Randevu', randevu.RandevuID, 
                       detail=f"Randevu oluşturuldu: {randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M')} - {randevu.MusteriAdi}")
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Randevu başarıyla oluşturuldu!'})
        flash('Randevu başarıyla oluşturuldu!', 'success')
        return redirect(url_for('randevular'))
    # GET isteği
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuReferans.Ad).all()
    
    # Müşterileri al
    musteriler = Musteri.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(Musteri.MusteriAdi, Musteri.MusteriSoyadi).all()
    
    # Müşteri kategorilerini al
    musteri_kategoriler = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id']
    ).filter(MusteriKategori.Aktif == 1).all()
    
    # Randevu defteri ayarlarını al (tüm aktif defterler)
    defter_ayarlar = RandevuDefterAyar.query.filter_by(
        FirmaID=session['firma_id'], 
        Aktif=True
    ).order_by(RandevuDefterAyar.DefterAdi).all()
    
    
    # Eğer defter yoksa varsayılan defter oluştur
    if not defter_ayarlar:
        print(f"Firma {session['firma_id']} için defter bulunamadı, varsayılan defter oluşturuluyor...")
        varsayilan_defter = RandevuDefterAyar(
            FirmaID=session['firma_id'],
            DefterAdi='Varsayılan Defter',
            CalismaGunleri='1,2,3,4,5',
            BaslangicSaati='09:00',
            BitisSaati='18:00',
            SlotDakika=30,
            Aktif=True
        )
        db.session.add(varsayilan_defter)
        db.session.commit()
        defter_ayarlar = [varsayilan_defter]
    else:
        varsayilan_defter = defter_ayarlar[0]
    
    min_sure = varsayilan_defter.SlotDakika
    
    # İşlemler listesini al (varsayılan deftere göre filtrele, sonra JS değiştikçe AJAX ile alınabilir)
    islemler = RandevuIslem.query.filter_by(
        FirmaID=session.get('firma_id'), 
        Aktif=True
    ).filter(
        (RandevuIslem.DefterID == varsayilan_defter.AyarID) | (RandevuIslem.DefterID.is_(None))
    ).order_by(RandevuIslem.IslemAdi).all()
    
    # Ülkeleri getir
    countries = get_countries()
    
    return render_template('randevu_ekle.html', 
                         referanslar=referanslar,
                         islemler=islemler,
                         musteriler=musteriler,
                         musteri_kategoriler=musteri_kategoriler,
                         defter_ayarlar=defter_ayarlar,
                         varsayilan_defter=varsayilan_defter,
                         min_sure=min_sure,
                         countries=countries)

@app.route('/api/kullanicilar')
@login_required
def api_kullanicilar():
    """Firma kullanıcılarını getir"""
    try:
        firma_id = session.get('firma_id')
        if not firma_id:
            return jsonify({'success': False, 'message': 'Firma bilgisi bulunamadı'}), 400
        
        # Firma kullanıcılarını getir
        kullanicilar = Kullanici.query.filter_by(FirmaID=firma_id, Aktif=True).all()
        
        kullanici_listesi = []
        for kullanici in kullanicilar:
            kullanici_listesi.append({
                'id': kullanici.KullaniciID,
                'adi': kullanici.Ad,
                'soyadi': kullanici.Soyad,
                'tam_adi': f"{kullanici.Ad} {kullanici.Soyad}".strip(),
                'email': kullanici.Email
            })
        
        return jsonify({'success': True, 'kullanicilar': kullanici_listesi})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/api/gorevler/calendar')
@login_required
def api_gorevler_calendar():
    """Görevler için takvim API'si"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Kullanıcı bilgisi bulunamadı'}), 400
        
        # Tarih aralığı parametreleri
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        
        # Filtre parametreleri
        search_term = request.args.get('search', '').strip()
        status_filter = request.args.get('status', 'all')
        priority_filter = request.args.get('priority', 'all')
        date_filter = request.args.get('date', '')
        
        # Görevleri getir (sadece randevu bazlı görevler) ve tamamlananları gizle
        query = Todo.query.filter_by(KullaniciID=user_id, Tip='Randevu')
        try:
            # Tamamlananları hariç tut (durum adı üzerinden)
            query = query.outerjoin(TodoDurum, Todo.DurumID == TodoDurum.DurumID) \
                         .filter(or_(TodoDurum.DurumAdi != 'Tamamlandı', TodoDurum.DurumAdi.is_(None)))
        except Exception:
            # Herhangi bir hata olursa sadece DurumID None olmayan ve adı 'Tamamlandı' olmayanları approx filtrele
            pass
        
        # Arama filtresi
        if search_term:
            query = query.filter(
                or_(
                    Todo.Baslik.ilike(f'%{search_term}%'),
                    Todo.Aciklama.ilike(f'%{search_term}%')
                )
            )
        
        # Durum filtresi
        if status_filter != 'all':
            query = query.filter(Todo.DurumID == status_filter)
        
        # Öncelik filtresi
        if priority_filter != 'all':
            query = query.filter(Todo.Oncelik == priority_filter.title())
        
        # Tarih filtresi
        if date_filter:
            try:
                filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                query = query.filter(
                    or_(
                        func.date(Todo.BitisTarihi) == filter_date,
                        func.date(Todo.HatirlatmaTarihi) == filter_date
                    )
                )
            except ValueError:
                pass  # Geçersiz tarih formatı
        
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                query = query.filter(
                    or_(
                        Todo.BitisTarihi.between(start_dt, end_dt),
                        Todo.HatirlatmaTarihi.between(start_dt, end_dt)
                    )
                )
            except ValueError:
                pass  # Geçersiz tarih formatı, tüm görevleri getir
        
        gorevler = query.all()
        
        # FullCalendar formatında events oluştur
        events = []
        for gorev in gorevler:
            # Başlangıç zamanı öncelik sırasıyla belirlenir:
            # 1) Bağlı Randevu kaydı varsa Randevu.RandevuTarihi
            # 2) Todo.RandevuTarihi + RandevuSaati alanları
            # 3) BitisTarihi ya da HatirlatmaTarihi
            start_dt = None
            try:
                if gorev.RandevuID:
                    r = Randevu.query.filter_by(RandevuID=gorev.RandevuID).first()
                    if r and r.RandevuTarihi:
                        start_dt = r.RandevuTarihi
                if start_dt is None and gorev.RandevuTarihi and gorev.RandevuSaati:
                    try:
                        saat_parts = str(gorev.RandevuSaati).split(':')
                        hour = int(saat_parts[0])
                        minute = int(saat_parts[1]) if len(saat_parts) > 1 else 0
                        start_dt = datetime.combine(gorev.RandevuTarihi, time(hour, minute))
                    except Exception:
                        pass
                if start_dt is None:
                    start_dt = gorev.BitisTarihi or gorev.HatirlatmaTarihi
            except Exception:
                start_dt = gorev.BitisTarihi or gorev.HatirlatmaTarihi

            if start_dt:
                # Öncelik rengi belirle
                oncelik_class = 'oncelik-dusuk'
                if gorev.Oncelik == 'Yüksek':
                    oncelik_class = 'oncelik-yuksek'
                elif gorev.Oncelik == 'Orta':
                    oncelik_class = 'oncelik-orta'
                
                # Durum class'ı ve rengi
                durum_class = ''
                durum_color = '#007bff'  # Varsayılan renk
                if gorev.durum:
                    # Veritabanındaki renk kodunu kullan
                    durum_color = gorev.durum.Renk if gorev.durum.Renk else '#007bff'
                    
                    # Tamamlandı durumu için özel class
                    if gorev.durum.DurumAdi == 'Tamamlandı':
                        durum_class = 'tamamlandi'
                
                # Durum adını title'a ekle
                durum_adi = gorev.durum.DurumAdi if gorev.durum else 'Durum Yok'
                
                # Müşteri bilgilerini title'a ekle
                musteri_bilgi = ''
                if gorev.MusteriAdi:
                    musteri_bilgi = f" - {gorev.MusteriAdi}"
                    if gorev.MusteriSoyadi:
                        musteri_bilgi += f" {gorev.MusteriSoyadi}"
                
                # Saat bilgisini ekle (randevular takvimi gibi)
                saat_bilgi = start_dt.strftime('%H:%M') if hasattr(start_dt, 'strftime') else ''
                # Başlık sadece saat + başlık olsun, ikinci satıra defter adı
                defter_adi = None
                try:
                    # 1) Görev üzerindeki defter ID'den bul
                    if gorev.RandevuDefteriID:
                        defter = RandevuDefterAyar.query.filter_by(AyarID=gorev.RandevuDefteriID).first()
                        if defter and defter.DefterAdi:
                            defter_adi = defter.DefterAdi
                            print(f"DEBUG: Görev {gorev.TodoID} için defter adı bulundu (RandevuDefteriID): {defter_adi}")
                    # 2) Bağlı randevudan ilişki ile bul
                    if not defter_adi and gorev.RandevuID:
                        r = Randevu.query.filter_by(RandevuID=gorev.RandevuID).first()
                        if r:
                            if r.defter and r.defter.DefterAdi:
                                defter_adi = r.defter.DefterAdi
                                print(f"DEBUG: Görev {gorev.TodoID} için defter adı bulundu (Randevu.defter): {defter_adi}")
                            # 3) İlişki yoksa direkt DefterID ile bul
                            elif r.DefterID:
                                defter2 = RandevuDefterAyar.query.filter_by(AyarID=r.DefterID).first()
                                if defter2 and defter2.DefterAdi:
                                    defter_adi = defter2.DefterAdi
                                    print(f"DEBUG: Görev {gorev.TodoID} için defter adı bulundu (Randevu.DefterID): {defter_adi}")
                    if not defter_adi:
                        print(f"DEBUG: Görev {gorev.TodoID} için defter adı bulunamadı. RandevuDefteriID: {gorev.RandevuDefteriID}, RandevuID: {gorev.RandevuID}")
                except Exception as e:
                    defter_adi = None
                    print(f"DEBUG: Görev {gorev.TodoID} için defter adı aranırken hata: {e}")

                title_with_status = f"{saat_bilgi} {gorev.Baslik}{musteri_bilgi}".strip()
                
                events.append({
                    'id': f'gorev_{gorev.TodoID}',
                    'title': title_with_status,
                    'start': start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                    'allDay': False,
                    'backgroundColor': durum_color,
                    'borderColor': durum_color,
                    'className': f'{oncelik_class} {durum_class}',
                    'extendedProps': {
                        'gorev_id': gorev.TodoID,
                        'aciklama': gorev.Aciklama,
                        'oncelik': gorev.Oncelik,
                        'durum': durum_adi,
                        'durum_rengi': durum_color,
                        'tip': 'gorev',
                        'musteri_adi': gorev.MusteriAdi,
                        'musteri_soyadi': gorev.MusteriSoyadi,
                        'musteri_telefon': gorev.MusteriTelefon,
                        'musteri_email': gorev.MusteriEmail,
                        'defter_adi': defter_adi
                    }
                })
        
        return jsonify(events)
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/api/musteri-ara')
@login_required
def api_musteri_ara():
    """Müşteri arama API'si - Sadece aktif müşteriler"""
    try:
        query = request.args.get('q', '').strip()
        if len(query) < 2:
            return jsonify([])
        
        firma_id = session.get('firma_id')
        if not firma_id:
            return jsonify([])
        
        # Sadece aktif müşterileri ara
        musteriler = Musteri.query.filter(
            Musteri.FirmaID == firma_id,
            Musteri.Aktif == True,
            or_(
                Musteri.MusteriAdi.ilike(f'%{query}%'),
                Musteri.MusteriSoyadi.ilike(f'%{query}%'),
                Musteri.Telefon.ilike(f'%{query}%'),
                Musteri.Email.ilike(f'%{query}%'),
                # Tam isim araması (Ad + Soyad)
                db.func.concat(Musteri.MusteriAdi, ' ', Musteri.MusteriSoyadi).ilike(f'%{query}%')
            )
        ).limit(10).all()
        
        results = []
        for musteri in musteriler:
            results.append({
                'id': musteri.MusteriID,
                'ad': musteri.MusteriAdi or '',
                'soyad': musteri.MusteriSoyadi or '',
                'telefon': musteri.Telefon or '',
                'email': musteri.Email or '',
                'display': f"{musteri.MusteriAdi or ''} {musteri.MusteriSoyadi or ''}".strip()
            })
        
        return jsonify(results)
        
    except Exception as e:
        print(f"Müşteri arama hatası: {e}")
        return jsonify([])

@app.route('/api/musteri-bilgi')
@login_required
def api_musteri_bilgi():
    """Müşteri bilgilerini ad ve soyada göre getir"""
    try:
        ad = request.args.get('ad', '').strip()
        soyad = request.args.get('soyad', '').strip()
        
        if not ad or not soyad:
            return jsonify({'success': False, 'message': 'Ad ve soyad gerekli'})
        
        firma_id = session.get('firma_id')
        if not firma_id:
            return jsonify({'success': False, 'message': 'Firma ID bulunamadı'})
        
        # Müşteriyi ad ve soyada göre bul
        musteri = Musteri.query.filter(
            Musteri.FirmaID == firma_id,
            Musteri.MusteriAdi.ilike(ad),
            Musteri.MusteriSoyadi.ilike(soyad)
        ).first()
        
        if musteri:
            return jsonify({
                'success': True,
                'musteri': {
                    'id': musteri.MusteriID,
                    'ad': musteri.MusteriAdi,
                    'soyad': musteri.MusteriSoyadi,
                    'telefon': musteri.Telefon or '',
                    'email': musteri.Email or ''
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Müşteri bulunamadı'})
        
    except Exception as e:
        print(f"Müşteri bilgi hatası: {e}")
        return jsonify({'success': False, 'message': 'Hata oluştu'})

@app.route('/api/islemler')
@login_required
def api_islemler():
    firma_id = session.get('firma_id')
    defter_id = request.args.get('defter_id', type=int)
    
    q = RandevuIslem.query.filter_by(FirmaID=firma_id, Aktif=True)
    if defter_id:
        q = q.filter((RandevuIslem.DefterID == defter_id) | (RandevuIslem.DefterID.is_(None)))
    
    items = q.order_by(RandevuIslem.IslemAdi).all()
    
    return jsonify([
        {
            'IslemID': i.IslemID,
            'IslemAdi': i.IslemAdi
        } for i in items
    ])

@app.route('/randevu/<int:randevu_id>')
@login_required
def randevu_detay(randevu_id):
    # Yetki kontrolu
    if session.get('is_admin', False):
        randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
    else:
        randevu = db.session.query(Randevu).join(RandevuYetki).filter(
            Randevu.RandevuID == randevu_id,
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id']
        ).first()
    
    if not randevu:
        flash('Randevu bulunamadı veya erişim yetkiniz yok!', 'error')
        return redirect(url_for('randevular'))
    
    return render_template('randevu_detay.html', randevu=randevu)

@app.route('/randevu/sil/<int:randevu_id>', methods=['POST'])
@login_required
def randevu_sil(randevu_id):
    # Randevuyu ve erisim yetkisini kontrol et
    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
    if not randevu:
        flash('Randevu bulunamadı veya erişim yetkiniz yok', 'error')
        return redirect(url_for('randevular'))

    is_admin = session.get('is_admin', False)
    has_delete_perm = db.session.query(RandevuYetki).filter_by(
        RandevuID=randevu_id,
        KullaniciID=session['user_id'],
        SilmeYetkisi=True
    ).first() is not None

    if not (is_admin or randevu.OlusturanKullaniciID == session['user_id'] or has_delete_perm):
        flash('Silme yetkiniz yok', 'error')
        return redirect(url_for('randevular'))

    try:
        # Silme öncesi bilgileri kaydet
        randevu_bilgi = {
            'tarih': randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M'),
            'musteri': randevu.MusteriAdi,
            'referans': randevu.RandevuBaslik
        }
        
        # Cascade delete ile tüm ilgili kayıtlar otomatik silinir
        db.session.delete(randevu)
        db.session.commit()
        
        # Randevu silme logla
        log_user_action('DELETE', 'Randevu', randevu_id, 
                       old_data=randevu_bilgi,
                       detail=f"Randevu silindi: {randevu_bilgi['tarih']} - {randevu_bilgi['musteri']}")
        
        flash('Randevu silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Randevu silinirken hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('randevular'))

@app.route('/randevu/durum/<int:randevu_id>', methods=['POST'])
@login_required
def randevu_durum(randevu_id):
    yeni_durum = request.form.get('durum')
    if yeni_durum not in ['Beklemede', 'Onaylandi', 'Iptal', 'Tamamlandi']:
        flash('Geçersiz durum', 'error')
        return redirect(url_for('randevular'))

    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
    if not randevu:
        flash('Randevu bulunamadı veya erişim yetkiniz yok', 'error')
        return redirect(url_for('randevular'))

    is_admin = session.get('is_admin', False)
    has_edit_perm = db.session.query(RandevuYetki).filter_by(
        RandevuID=randevu_id,
        KullaniciID=session['user_id'],
        DuzenlemeYetkisi=True
    ).first() is not None

    if not (is_admin or randevu.OlusturanKullaniciID == session['user_id'] or has_edit_perm):
        flash('Durum güncelleme yetkiniz yok', 'error')
        return redirect(url_for('randevular'))

    eski_durum = randevu.Durum
    randevu.Durum = yeni_durum
    db.session.commit()
    
    # Durum değişikliği logla
    log_user_action('UPDATE', 'Randevu', randevu_id,
                   old_data={'durum': eski_durum},
                   new_data={'durum': yeni_durum},
                   detail=f"Randevu durumu değiştirildi: {eski_durum} -> {yeni_durum}")
    
    # Eğer randevu iptal edildiyse, slot'u açık hale getir
    if yeni_durum == 'Iptal':
        # Randevu iptal edildiğinde slot artık kullanılabilir
        # Bu durumda slot API'si otomatik olarak bu slot'u açık gösterecek
        pass
    
    flash('Randevu durumu güncellendi', 'success')
    return redirect(url_for('randevular'))

# Takvim Görünümü
@app.route('/takvim')
@login_required
def takvim():
    # Ay ve yıl parametreleri
    year = request.args.get('year', type=int) or datetime.now().year
    month = request.args.get('month', type=int) or datetime.now().month
    view_type = request.args.get('view', 'month')  # month, week
    defter_id = request.args.get('defter_id', type=int)
    week_start_param = request.args.get('week_start')  # YYYY-MM-DD (Pazartesi)
    
    # Tarih aralığı hesapla
    if view_type == 'month':
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
    else:  # week
        # Haftanın başlangıcı parametreden ya da bugüne göre Pazartesi
        if week_start_param:
            try:
                ws = datetime.strptime(week_start_param, '%Y-%m-%d')
            except ValueError:
                ws = datetime.now()
        else:
            ws = datetime.now()
        days_since_monday = ws.weekday()
        start_date = ws - timedelta(days=days_since_monday)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)
    
    # Kullanıcının yetkili olduğu defterleri getir
    if session.get('is_admin', False):
        # Admin kullanıcılar tüm defterleri görebilir
        defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
    else:
        # Normal kullanıcılar: Aynı deftere randevu alabilen kullanıcılar, o defterdeki tüm randevuları görebilir
        # Kullanıcının randevu aldığı defterleri bul
        from sqlalchemy import distinct
        kullanici_defter_ids = db.session.query(distinct(Randevu.DefterID)).filter(
            Randevu.OlusturanKullaniciID == session['user_id'],
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID.isnot(None)
        ).all()
        
        # Kullanıcının randevu aldığı defter ID'lerini liste olarak al
        defter_id_list = [defter_id[0] for defter_id in kullanici_defter_ids if defter_id[0] is not None]
        
        if defter_id_list:
            defterler = RandevuDefterAyar.query.filter(
                RandevuDefterAyar.AyarID.in_(defter_id_list),
                RandevuDefterAyar.FirmaID == session['firma_id'],
                RandevuDefterAyar.Aktif == True
            ).all()
        else:
            # Eğer hiç randevu alınmamışsa boş liste
            defterler = []
    
    # Eğer defter seçilmemişse:
    # - Aylık görünümde: tüm defterler gösterilir
    # - Haftalık görünümde: ilk defter seçili gelir
    if not defter_id and view_type == 'week' and defterler:
        defter_id = defterler[0].AyarID
    
    # Randevuları getir (iptal edilen randevular hariç) - işlem bilgisi ile birlikte
    if session.get('is_admin', False):
        # Admin: Tüm randevuları görebilir
        query = db.session.query(Randevu, RandevuIslem).outerjoin(RandevuIslem, Randevu.IslemID == RandevuIslem.IslemID).filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_date,
            Randevu.RandevuTarihi < end_date,
            Randevu.Durum != 'Iptal'  # İptal edilen randevuları hariç tut
        )
        if defter_id:
            query = query.filter(Randevu.DefterID == defter_id)
        results = query.order_by(Randevu.RandevuTarihi).all()
        # Randevu ve işlem bilgilerini birleştir
        randevular = []
        for randevu, islem in results:
            randevu.islem_adi = islem.IslemAdi if islem else None
            randevular.append(randevu)
    else:
        # Normal kullanıcı: Aynı deftere randevu alabilen kullanıcılar, o defterdeki tüm randevuları görebilir
        if defter_id_list:  # Kullanıcının randevu aldığı defterler varsa
            query = db.session.query(Randevu, RandevuIslem).outerjoin(RandevuIslem, Randevu.IslemID == RandevuIslem.IslemID).filter(
                Randevu.FirmaID == session['firma_id'],
                Randevu.RandevuTarihi >= start_date,
                Randevu.RandevuTarihi < end_date,
                Randevu.Durum != 'Iptal',  # İptal edilen randevuları hariç tut
                Randevu.DefterID.in_(defter_id_list)  # Sadece kullanıcının randevu aldığı defterler
            )
            if defter_id:
                query = query.filter(Randevu.DefterID == defter_id)
            results = query.order_by(Randevu.RandevuTarihi).all()
            # Randevu ve işlem bilgilerini birleştir
            randevular = []
            for randevu, islem in results:
                randevu.islem_adi = islem.IslemAdi if islem else None
                randevular.append(randevu)
        else:
            # Kullanıcının hiç randevu aldığı defter yoksa boş liste
            randevular = []
    
    # Haftalık görünüm için başlık ve gezinme verileri
    # Dil kontrolü (tüm görünümler için)
    current_lang = session.get('language', 'tr')
    
    week_start_str = start_date.strftime('%Y-%m-%d') if view_type == 'week' else None
    prev_week_start = (start_date - timedelta(days=7)).strftime('%Y-%m-%d') if view_type == 'week' else None
    next_week_start = (start_date + timedelta(days=7)).strftime('%Y-%m-%d') if view_type == 'week' else None
    if view_type == 'week':
        week_end_display = (end_date - timedelta(days=1))
        if current_lang == 'en':
            # İngilizce ay isimleri
            english_months = {
                1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
            }
            start_month = english_months[start_date.month]
            end_month = english_months[week_end_display.month]
        elif current_lang == 'fr':
            # Fransızca ay isimleri
            french_months = {
                1: 'Jan', 2: 'Fév', 3: 'Mar', 4: 'Avr', 5: 'Mai', 6: 'Juin',
                7: 'Juil', 8: 'Août', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Déc'
            }
            start_month = french_months[start_date.month]
            end_month = french_months[week_end_display.month]
        elif current_lang == 'de':
            # Almanca ay isimleri
            german_months = {
                1: 'Jan', 2: 'Feb', 3: 'Mär', 4: 'Apr', 5: 'Mai', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Dez'
            }
            start_month = german_months[start_date.month]
            end_month = german_months[week_end_display.month]
        else:
            # Türkçe ay isimleri
            turkish_months = {
                1: 'Oca', 2: 'Şub', 3: 'Mar', 4: 'Nis', 5: 'May', 6: 'Haz',
                7: 'Tem', 8: 'Ağu', 9: 'Eyl', 10: 'Eki', 11: 'Kas', 12: 'Ara'
            }
            start_month = turkish_months[start_date.month]
            end_month = turkish_months[week_end_display.month]
        
        week_range_title = f"{start_date.day} {start_month} {start_date.year} - {week_end_display.day} {end_month} {week_end_display.year}"
    else:
        week_range_title = None

    return render_template('takvim.html', 
                         randevular=randevular, 
                         year=year, 
                         month=month, 
                         view_type=view_type,
                         start_date=start_date,
                         end_date=end_date,
                         datetime=datetime,
                         timedelta=timedelta,
                         defterler=defterler,
                         selected_defter_id=defter_id,
                         week_start_str=week_start_str,
                         prev_week_start=prev_week_start,
                         next_week_start=next_week_start,
                         week_range_title=week_range_title,
                         lang=current_lang)

# API: Randevu taşıma (drag & drop)
@app.route('/api/randevu/tasi', methods=['POST'])
@login_required
def api_randevu_tasi():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "JSON verisi bulunamadı"}), 400
            
        randevu_id = data.get('randevu_id')
        yeni_tarih = data.get('yeni_tarih')  # YYYY-MM-DD HH:MM format
        
        print(f"API çağrısı - Randevu ID: {randevu_id}, Yeni Tarih: {yeni_tarih}")
        
        if not randevu_id or not yeni_tarih:
            return jsonify({"success": False, "message": "Eksik parametre"}), 400
        
        try:
            yeni_dt = datetime.strptime(yeni_tarih, '%Y-%m-%d %H:%M')
        except ValueError as e:
            print(f"Tarih parse hatası: {e}")
            return jsonify({"success": False, "message": "Geçersiz tarih formatı"}), 400
    except Exception as e:
        print(f"Genel hata: {e}")
        return jsonify({"success": False, "message": "Sunucu hatası"}), 500
    
    # Randevuyu bul ve yetki kontrolü
    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
    if not randevu:
        return jsonify({"success": False, "message": "Randevu bulunamadı"}), 404
    
    is_admin = session.get('is_admin', False)
    has_edit_perm = db.session.query(RandevuYetki).filter_by(
        RandevuID=randevu_id,
        KullaniciID=session['user_id'],
        DuzenlemeYetkisi=True
    ).first() is not None
    
    if not (is_admin or randevu.OlusturanKullaniciID == session['user_id'] or has_edit_perm):
        return jsonify({"success": False, "message": "Yetkiniz yok"}), 403
    
    # Hedef defter bilgisine göre slot'a yapıştır
    try:
        defter_ayar = RandevuDefterAyar.query.get(randevu.DefterID)
        slot_dk = (defter_ayar.SlotDakika if defter_ayar and defter_ayar.SlotDakika else 30)
        # minute'i slot basamağına yuvarla (aşağı)
        yeni_dt = yeni_dt.replace(minute=(yeni_dt.minute // slot_dk) * slot_dk, second=0, microsecond=0)
    except Exception as e:
        print(f"Slot yuvarlama hatası: {e}")

    # Çakışma kontrolü (aynı defter için) - Optimistic Locking ile güçlendirilmiş
    randevu_suresi = randevu.RandevuSuresi or 60
    bitis_tarihi = yeni_dt + timedelta(minutes=randevu_suresi)
    
    # Mevcut randevuları kontrol et (iptal edilenleri hariç tut)
    mevcut_randevular = Randevu.query.filter(
        Randevu.FirmaID == session['firma_id'],
        Randevu.DefterID == randevu.DefterID,
        Randevu.RandevuID != randevu_id,
        Randevu.Durum != 'Iptal'  # İptal edilen randevuları hariç tut
    ).all()
    
    cakisan = None
    for mevcut in mevcut_randevular:
        mevcut_suresi = mevcut.RandevuSuresi or 60
        mevcut_bitis = mevcut.RandevuTarihi + timedelta(minutes=mevcut_suresi)
        
        # Çakışma kontrolü: yeni randevu mevcut randevu ile çakışıyor mu?
        if (yeni_dt < mevcut_bitis and bitis_tarihi > mevcut.RandevuTarihi):
            cakisan = mevcut
            break
    
    if cakisan:
        return jsonify({"success": False, "message": "Bu saatte başka randevu var"}), 400
    
    # Tarihi güncelle - Optimistic Locking ile korumalı
    try:
        eski_tarih = randevu.RandevuTarihi
        randevu.RandevuTarihi = yeni_dt
        db.session.commit()
        print(f"Randevu {randevu_id} başarıyla taşındı")
        
        # Randevu taşıma logla
        log_user_action('UPDATE', 'Randevu', randevu_id,
                       old_data={'tarih': eski_tarih.strftime('%Y-%m-%d %H:%M')},
                       new_data={'tarih': yeni_dt.strftime('%Y-%m-%d %H:%M')},
                       detail=f"Randevu taşındı: {eski_tarih.strftime('%d.%m.%Y %H:%M')} -> {yeni_dt.strftime('%d.%m.%Y %H:%M')}")
        
    except Exception as e:
        db.session.rollback()
        print(f"Randevu taşıma hatası: {e}")
        return jsonify({"success": False, "message": "Randevu taşınırken bir hata oluştu"}), 500

    # Başarıyı hemen döndür; yan işlemleri ateşle ama hataları yut
    try:
        # Bildirim: randevu taşındı (olusturana bildirim)
        try:
            b = Bildirim(
                KullaniciID=randevu.OlusturanKullaniciID,
                FirmaID=session['firma_id'],
                Metin=f"Randevu {eski_tarih.strftime('%d.%m.%Y %H:%M')} -> {yeni_dt.strftime('%d.%m.%Y %H:%M')} taşındı",
                Tip='randevu',
                IlgiliRandevuID=randevu.RandevuID
            )
            db.session.add(b)
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Randevu taşındığında müşteriye e-posta gönder (e-posta varsa)
        if randevu.MusteriEmail:
            subject = f"Randevu Tarihi Değişikliği - {yeni_dt.strftime('%d.%m.%Y %H:%M')}"
            body = (
                f"Merhaba {randevu.MusteriAdi or 'Değerli Müşterimiz'},\n\n"
                f"Randevu tarihiniz değiştirilmiştir:\n"
                f"Eski Tarih: {eski_tarih.strftime('%d.%m.%Y %H:%M')}\n"
                f"Yeni Tarih: {yeni_dt.strftime('%d.%m.%Y %H:%M')}\n"
                f"Referans: {randevu.RandevuBaslik}\n"
                f"Süre: {randevu.RandevuSuresi or 60} dakika\n\n"
                f"Bu değişiklik hakkında sorularınız için bizimle iletişime geçebilirsiniz.\n\n"
                f"İyi günler dileriz."
            )
            try:
                email_sent = send_email_with_firma_settings(randevu.FirmaID, randevu.MusteriEmail, subject, body)
                if not email_sent:
                    send_email_simple(randevu.MusteriEmail, subject, body)
            except Exception:
                pass
    except Exception:
        pass

    return jsonify({"success": True, "message": "Randevu taşındı"})

# Log Görüntüleme
@app.route('/loglar')
@login_required
def loglar():
    # Log modülü yetki kontrolü
    if not (session.get('is_admin', False) or session.get('log_modulu', False)):
        flash('Bu sayfaya erişim yetkiniz yok', 'error')
        return redirect(url_for('dashboard'))
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Filtreler
    kullanici_id = request.args.get('kullanici_id', type=int)
    islem_tipi = request.args.get('islem_tipi')
    tablo_adi = request.args.get('tablo_adi')
    
    # Bugünün tarihi
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Tarih filtreleri - eğer belirtilmemişse bugünü kullan
    tarih_baslangic = request.args.get('tarih_baslangic', today)
    tarih_bitis = request.args.get('tarih_bitis', today)
    
    # Query oluştur
    query = KullaniciLog.query.join(Kullanici)
    
    if kullanici_id:
        query = query.filter(KullaniciLog.KullaniciID == kullanici_id)
    if islem_tipi:
        query = query.filter(KullaniciLog.IslemTipi == islem_tipi)
    if tablo_adi:
        query = query.filter(KullaniciLog.TabloAdi == tablo_adi)
    # Tarih filtrelerini uygula (her zaman)
    try:
        baslangic_dt = datetime.strptime(tarih_baslangic, '%Y-%m-%d')
        query = query.filter(KullaniciLog.OlusturmaTarihi >= baslangic_dt)
    except ValueError:
        pass
    try:
        bitis_dt = datetime.strptime(tarih_bitis, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(KullaniciLog.OlusturmaTarihi < bitis_dt)
    except ValueError:
        pass
    
    # Sadece kendi firma logları
    query = query.filter(Kullanici.FirmaID == session['firma_id'])
    
    # Sıralama ve sayfalama
    query = query.order_by(KullaniciLog.OlusturmaTarihi.desc())
    
    # Export işlemleri
    export_format = request.args.get('export')
    if export_format in ['csv', 'excel', 'pdf']:
        logs = query.all()
        
        # Çıktı alma logla
        try:
            log_user_action('VIEW', 'Sistem', detail=f"Loglar {export_format.upper()} indirildi")
        except Exception:
            pass
        
        if export_format == 'csv':
            # CSV Export
            output = StringIO()
            writer = csv.writer(output, delimiter=';')
            writer.writerow(['Tarih', 'Kullanıcı', 'İşlem', 'Tablo', 'Kayıt Bilgisi', 'Detay', 'IP'])
            for log in logs:
                record_info = get_record_info(log)
                writer.writerow([
                    log.OlusturmaTarihi.strftime('%d.%m.%Y %H:%M:%S'),
                    log.kullanici.KullaniciAdi,
                    log.IslemTipi,
                    log.TabloAdi,
                    record_info or (log.KayitID or ''),
                    log.IslemDetayi or '',
                    log.IPAdresi or ''
                ])
            output.seek(0)
            return send_file(
                BytesIO(output.getvalue().encode('utf-8-sig')),
                mimetype='text/csv; charset=utf-8',
                as_attachment=True,
                download_name=f'loglar_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )
        
        elif export_format == 'excel':
            # Excel Export
            wb = Workbook()
            ws = wb.active
            ws.title = "Kullanıcı Logları"
            
            # Başlık satırı
            headers = ['Tarih', 'Kullanıcı', 'İşlem', 'Tablo', 'Kayıt Bilgisi', 'Detay', 'IP']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
            
            # Veri satırları
            for row, log in enumerate(logs, 2):
                record_info = get_record_info(log)
                ws.cell(row=row, column=1, value=log.OlusturmaTarihi.strftime('%d.%m.%Y %H:%M:%S'))
                ws.cell(row=row, column=2, value=log.kullanici.KullaniciAdi)
                ws.cell(row=row, column=3, value=log.IslemTipi)
                ws.cell(row=row, column=4, value=log.TabloAdi)
                ws.cell(row=row, column=5, value=record_info or (log.KayitID or ''))
                ws.cell(row=row, column=6, value=log.IslemDetayi or '')
                ws.cell(row=row, column=7, value=log.IPAdresi or '')
            
            # Sütun genişliklerini ayarla
            for column in ws.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Excel dosyasını kaydet
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            return send_file(
                buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'loglar_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            )
        
        elif export_format == 'pdf':
            # PDF Export
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
            
            # Türkçe font desteği
            try:
                pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/dejavu-sans.ttf'))
                pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/dejavu-sans-bold.ttf'))
                turkish_font = 'DejaVuSans'
                turkish_font_bold = 'DejaVuSans-Bold'
            except:
                try:
                    pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/arial.ttf'))
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
                    turkish_font = 'DejaVuSans'
                    turkish_font_bold = 'DejaVuSans-Bold'
                except:
                    turkish_font = 'Helvetica'
                    turkish_font_bold = 'Helvetica-Bold'
            
            # Stil tanımları
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=TA_CENTER, fontName=turkish_font_bold)
            
            # Başlık
            title = Paragraph("Kullanıcı Aktivite Logları", title_style)
            
            # Tablo verileri
            table_data = [['Tarih', 'Kullanıcı', 'İşlem', 'Tablo', 'Kayıt Bilgisi', 'Detay', 'IP']]
            
            for log in logs:
                record_info = get_record_info(log)
                table_data.append([
                    log.OlusturmaTarihi.strftime('%d.%m.%Y %H:%M:%S'),
                    log.kullanici.KullaniciAdi,
                    log.IslemTipi,
                    log.TabloAdi,
                    record_info or (log.KayitID or ''),
                    log.IslemDetayi or '',
                    log.IPAdresi or ''
                ])
            
            # Tablo oluştur
            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), turkish_font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), turkish_font),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            # PDF oluştur
            elements = [title, Spacer(1, 12), table]
            doc.build(elements)
            buffer.seek(0)
            
            return send_file(
                buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'loglar_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            )
    
    # Sayfalama
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    loglar = pagination.items
    total_pages = pagination.pages
    
    # Her log için record bilgisini hazırla
    for log in loglar:
        log.record_info = get_record_info(log)
    
    # Kullanıcı listesi (filtre için)
    kullanicilar = Kullanici.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
    
    return render_template('loglar.html', 
                         loglar=loglar,
                         kullanicilar=kullanicilar,
                         page=page,
                         total_pages=total_pages,
                         current_filters=request.args,
                         today=today)

@app.route('/api/loglar/<int:log_id>/data')
@login_required
def api_log_data(log_id):
    # Log modülü yetki kontrolü
    if not (session.get('is_admin', False) or session.get('log_modulu', False)):
        return jsonify({"error": "Yetkiniz yok"}), 403
    log = KullaniciLog.query.join(Kullanici).filter(
        KullaniciLog.LogID == log_id,
        Kullanici.FirmaID == session['firma_id']
    ).first()
    
    if not log:
        return jsonify({"error": "Log bulunamadı"}), 404
    
    data = {}
    if log.EskiVeri:
        try:
            data['old_data'] = json.loads(log.EskiVeri)
        except:
            data['old_data'] = log.EskiVeri
    if log.YeniVeri:
        try:
            data['new_data'] = json.loads(log.YeniVeri)
        except:
            data['new_data'] = log.YeniVeri
    
    return jsonify(data)

# API: Secilebilir saat slotlari
@app.route('/api/slots')
@login_required
def api_slots():
    # Inputs
    date_str = request.args.get('date')  # YYYY-MM-DD
    defter_id = request.args.get('defter_id', type=int)
    include_unavailable = request.args.get('all', '0') == '1'
    if not date_str:
        return jsonify({"success": False, "message": "date parametresi zorunlu"}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"success": False, "message": "date formatı YYYY-MM-DD olmalı"}), 400

    # Firma ayarlari
    firma_id = session['firma_id']
    
    # Eğer defter_id verilmişse, o defteri kullan
    if defter_id:
        ayar = RandevuDefterAyar.query.filter_by(
            AyarID=defter_id, 
            FirmaID=firma_id, 
            Aktif=True
        ).first()
        if not ayar:
            return jsonify({"success": False, "message": "Belirtilen defter bulunamadı"}), 400
    else:
        # Varsayılan olarak ilk aktif defteri kullan
        ayar = RandevuDefterAyar.query.filter_by(FirmaID=firma_id, Aktif=True).order_by(RandevuDefterAyar.AyarID.desc()).first()
    
    if not ayar:
        # Varsayilan
        calisma_gunleri = {'1','2','3','4','5'}
        baslangic = '09:00'
        bitis = '18:00'
        slot_dk = 30
    else:
        calisma_gunleri = set((ayar.CalismaGunleri or '1,2,3,4,5').split(','))
        baslangic = ayar.BaslangicSaati or '09:00'
        bitis = ayar.BitisSaati or '18:00'
        slot_dk = ayar.SlotDakika or 30

    # Gun uygun mu?
    # Python weekday(): Monday=0..Sunday=6 -> our mapping 1..7
    weekday_num = (target_date.weekday() + 1)  # 1..7
    if str(weekday_num) not in calisma_gunleri:
        return jsonify({"success": True, "slots": []})

    # Saat araligi
    def parse_hhmm(s):
        h, m = s.split(':')
        return int(h), int(m)
    sh, sm = parse_hhmm(baslangic)
    eh, em = parse_hhmm(bitis)
    start_dt = datetime(target_date.year, target_date.month, target_date.day, sh, sm)
    end_dt = datetime(target_date.year, target_date.month, target_date.day, eh, em)

    # Bloklar (kapatilan araliklar)
    from sqlalchemy import or_, and_, and_
    bloklar = db.session.query(RandevuDefterBlok).filter(
        RandevuDefterBlok.FirmaID == firma_id,
        RandevuDefterBlok.Aktif == True,
        # Tarih araligi kapsama
        or_(
            RandevuDefterBlok.BitisTarih == None,
            RandevuDefterBlok.BitisTarih >= target_date
        ),
        RandevuDefterBlok.BaslangicTarih <= target_date,
        # Defter filtresi: None tüm defterler veya seçili defter
        or_(
            RandevuDefterBlok.DefterID == None,
            RandevuDefterBlok.DefterID == (ayar.AyarID if ayar else None)
        )
    ).all()

    def is_blocked(slot_start: datetime, slot_end: datetime) -> bool:
        if not bloklar:
            return False
        for b in bloklar:
            # Saat belirtilmemişse tüm gün bloklu kabul et
            if not b.SaatBaslangic or not b.SaatBitis:
                return True
            try:
                bh, bm = map(int, b.SaatBaslangic.split(':'))
                ehh, emm = map(int, b.SaatBitis.split(':'))
            except Exception:
                continue
            b_start = datetime(target_date.year, target_date.month, target_date.day, bh, bm)
            b_end = datetime(target_date.year, target_date.month, target_date.day, ehh, emm)
            if b_start < slot_end and slot_start < b_end:
                return True
        return False

    # O gun var olan randevular (sadece seçili defter için)
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0)
    day_end = day_start + timedelta(days=1)
    existing = Randevu.query.filter(
        Randevu.FirmaID == firma_id,
        Randevu.DefterID == defter_id,  # Sadece seçili defter
        Randevu.RandevuTarihi >= day_start,
        Randevu.RandevuTarihi < day_end,
        Randevu.Durum != 'iptal'  # İptal edilen randevuları hariç tut
    ).all()

    def is_overlapping(slot_start: datetime, slot_end: datetime) -> bool:
        for r in existing:
            r_start = r.RandevuTarihi
            r_end = r_start + timedelta(minutes=(r.RandevuSuresi or 60))
            if r_start < slot_end and slot_start < r_end:
                return True
        return False

    # Slotlari olustur
    slots = []
    cur = start_dt
    while cur + timedelta(minutes=slot_dk) <= end_dt:
        slot_end = cur + timedelta(minutes=slot_dk)
        taken = is_overlapping(cur, slot_end)
        blocked = is_blocked(cur, slot_end)
        slot_label = cur.strftime('%H:%M')
        if include_unavailable or (not taken and not blocked):
            slots.append({"time": slot_label, "available": (not taken and not blocked)})
        cur += timedelta(minutes=slot_dk)

    return jsonify({"success": True, "slots": slots})

# API: Slot müsaitlik kontrolü (Real-time UI feedback için)
@app.route('/api/slot/check', methods=['POST'])
@login_required
def api_slot_check():
    """Belirli bir slot'un müsait olup olmadığını kontrol eder"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Geçersiz veri"}), 400
        
        tarih_str = data.get('tarih')
        saat_str = data.get('saat')
        defter_id = int(data.get('defter_id', 0))
        randevu_suresi = int(data.get('sure', 60))
        exclude_randevu_id = int(data.get('exclude_randevu_id', 0)) if data.get('exclude_randevu_id') else None  # Düzenleme sırasında kendi randevusunu hariç tut
        
        if not tarih_str or not saat_str or not defter_id:
            return jsonify({"success": False, "message": "Eksik parametreler"}), 400
        
        # Tarih/saat parse et
        try:
            randevu_dt = datetime.strptime(f"{tarih_str} {saat_str}", '%Y-%m-%d %H:%M')
        except ValueError:
            return jsonify({"success": False, "message": "Geçersiz tarih/saat formatı"}), 400
        
        # Geçmiş tarih kontrolü
        if randevu_dt < datetime.now():
            return jsonify({"success": False, "available": False, "message": "Geçmiş tarih/saat"}), 200
        
        # Defter kontrolü
        defter_ayar = RandevuDefterAyar.query.filter_by(
            AyarID=defter_id, 
            FirmaID=session['firma_id'], 
            Aktif=True
        ).first()
        if not defter_ayar:
            return jsonify({"success": False, "message": "Defter bulunamadı"}), 400
        
        # Süre validation
        if randevu_suresi % defter_ayar.SlotDakika != 0:
            return jsonify({"success": False, "available": False, "message": f"Süre {defter_ayar.SlotDakika} dakikanın katları olmalı"}), 200
        
        # Çakışma kontrolü
        randevu_bas = randevu_dt
        randevu_bit = randevu_dt + timedelta(minutes=randevu_suresi)
        
        day_start = datetime(randevu_dt.year, randevu_dt.month, randevu_dt.day, 0, 0)
        day_end = day_start + timedelta(days=1)
        
        # Mevcut randevuları kontrol et
        query = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID == defter_id,
            Randevu.RandevuTarihi >= day_start,
            Randevu.RandevuTarihi < day_end,
            Randevu.Durum != 'Iptal'
        )
        
        if exclude_randevu_id:
            query = query.filter(Randevu.RandevuID != exclude_randevu_id)
        
        existing_randevular = query.all()
        
        for r in existing_randevular:
            r_start = r.RandevuTarihi
            r_dur = r.RandevuSuresi or 60
            r_end = r_start + timedelta(minutes=int(r_dur))
            if r_start < randevu_bit and randevu_bas < r_end:
                return jsonify({
                    "success": True, 
                    "available": False, 
                    "message": "Bu saatte mevcut randevu var",
                    "conflicting_appointment": {
                        "id": r.RandevuID,
                        "title": r.RandevuBaslik,
                        "start": r_start.strftime('%H:%M'),
                        "end": r_end.strftime('%H:%M'),
                        "customer": f"{r.MusteriAdi} {r.MusteriSoyadi or ''}".strip()
                    }
                }), 200
        
        # Blok kontrolü
        from sqlalchemy import or_, and_
        gun = randevu_dt.date()
        bloklar = db.session.query(RandevuDefterBlok).filter(
            RandevuDefterBlok.FirmaID == session['firma_id'],
            RandevuDefterBlok.Aktif == True,
            RandevuDefterBlok.BaslangicTarih <= gun,
            or_(RandevuDefterBlok.BitisTarih == None, RandevuDefterBlok.BitisTarih >= gun),
            or_(RandevuDefterBlok.DefterID == None, RandevuDefterBlok.DefterID == defter_id)
        ).all()
        
        def is_blocked_interval(bas: datetime, bit: datetime) -> bool:
            for b in bloklar:
                if not b.SaatBaslangic or not b.SaatBitis:
                    return True
                try:
                    bh, bm = map(int, b.SaatBaslangic.split(':'))
                    ehh, emm = map(int, b.SaatBitis.split(':'))
                except:
                    continue
                b_start = datetime(gun.year, gun.month, gun.day, bh, bm)
                b_end = datetime(gun.year, gun.month, gun.day, ehh, emm)
                if b_start < bit and bas < b_end:
                    return True
            return False
        
        if is_blocked_interval(randevu_bas, randevu_bit):
            return jsonify({
                "success": True, 
                "available": False, 
                "message": "Bu saat aralığı bloklu"
            }), 200
        
        return jsonify({
            "success": True, 
            "available": True, 
            "message": "Slot müsait"
        }), 200
        
    except Exception as e:
        import traceback
        print(f"Slot kontrol hatası: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "message": f"Sunucu hatası: {str(e)}"}), 500

# JSON API: Defter blokları (listele/ekle/sil) - randevu ekranından inline yönetim için
@app.route('/api/defter_bloklar', methods=['GET'])
@login_required
def api_defter_bloklar_liste():
    firma_id = session['firma_id']
    defter_id = request.args.get('defter_id', type=int)
    q = RandevuDefterBlok.query.filter_by(FirmaID=firma_id).order_by(RandevuDefterBlok.BlokID.desc())
    if defter_id:
        q = q.filter((RandevuDefterBlok.DefterID == defter_id) | (RandevuDefterBlok.DefterID.is_(None)))
    items = []
    for b in q.all():
        items.append({
            'BlokID': b.BlokID,
            'DefterID': b.DefterID,
            'DefterAdi': b.defter.DefterAdi if b.defter else 'Tümü',
            'BaslangicTarih': b.BaslangicTarih.strftime('%Y-%m-%d') if b.BaslangicTarih else None,
            'BitisTarih': b.BitisTarih.strftime('%Y-%m-%d') if b.BitisTarih else None,
            'SaatBaslangic': b.SaatBaslangic,
            'SaatBitis': b.SaatBitis,
            'Aciklama': b.Aciklama,
            'Aktif': b.Aktif,
        })
    return jsonify({'success': True, 'items': items})

@app.route('/api/defter_bloklar', methods=['POST'])
@login_required
def api_defter_blok_ekle():
    firma_id = session['firma_id']
    payload = request.get_json(silent=True) or {}
    defter_id = payload.get('defter_id')
    tarih1 = payload.get('tarih1')
    tarih2 = payload.get('tarih2')
    saat1 = payload.get('saat1')
    saat2 = payload.get('saat2')
    aciklama = payload.get('aciklama') or ''
    try:
        bas_t = datetime.strptime(tarih1, '%Y-%m-%d').date() if tarih1 else None
        bit_t = datetime.strptime(tarih2, '%Y-%m-%d').date() if tarih2 else None
    except Exception:
        return jsonify({'success': False, 'message': 'Geçersiz tarih formatı'}), 400
    if not bas_t:
        return jsonify({'success': False, 'message': 'Başlangıç tarihi zorunlu'}), 400
    if bit_t and bit_t < bas_t:
        return jsonify({'success': False, 'message': 'Bitiş tarihi başlangıçtan önce olamaz'}), 400

    blok = RandevuDefterBlok(
        FirmaID=firma_id,
        DefterID=int(defter_id) if defter_id else None,
        BaslangicTarih=bas_t,
        BitisTarih=bit_t,
        SaatBaslangic=saat1 or None,
        SaatBitis=saat2 or None,
        Aciklama=aciklama,
        Aktif=True
    )
    db.session.add(blok)
    db.session.commit()
    return jsonify({'success': True, 'id': blok.BlokID})

@app.route('/api/defter_bloklar/<int:blok_id>', methods=['DELETE'])
@login_required
def api_defter_blok_sil(blok_id: int):
    b = RandevuDefterBlok.query.filter_by(BlokID=blok_id, FirmaID=session['firma_id']).first()
    if not b:
        return jsonify({'success': False, 'message': 'Blok bulunamadı'}), 404
    db.session.delete(b)
    db.session.commit()
    return jsonify({'success': True})

# Raporlar Sayfasi
@app.route('/raporlar')
@login_required
def raporlar():
    # Modül izin kontrolü
    if not session.get('raporlar_modulu', False):
        flash('Bu sayfaya erişim yetkiniz yok', 'error')
        return redirect(url_for('dashboard'))
    # Varsayilan tarih araligi: son 30 gun
    end_str = request.args.get('bitis')
    start_str = request.args.get('baslangic')
    today = datetime.now().date()
    default_start = today - timedelta(days=30)
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else default_start
    except ValueError:
        start_date = default_start
    try:
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else today
    except ValueError:
        end_date = today

    # Kapasite ve defter parametrelerini al
    kapasite = request.args.get('kapasite', '')
    defter_id = request.args.get('defter_id', '')
    format_tip = request.args.get('format')  # Export format
    print(f"Form parametreleri - defter_id: '{defter_id}', kapasite: '{kapasite}', format: '{format_tip}'")
    
    # Defter listesini al
    defterler = RandevuDefterAyar.query.filter(
        RandevuDefterAyar.FirmaID == session['firma_id'],
        RandevuDefterAyar.Aktif == True
    ).all()
    print(f"Bulunan defter sayısı: {len(defterler)}")
    for defter in defterler:
        print(f"Defter: {defter.DefterAdi} (ID: {defter.AyarID})")
    
    # Eğer belirli bir defter seçilmişse ve kapasite boş/0 ise, defterden otomatik hesapla
    auto_capacity = None
    if defter_id and (not kapasite or kapasite == '0'):
        try:
            ayar = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=session['firma_id'], Aktif=True).first()
            if ayar:
                def parse_hhmm(s):
                    try:
                        h, m = (s or '09:00').split(':')
                        return int(h), int(m)
                    except:
                        return 9, 0  # Varsayılan 09:00
                
                sh, sm = parse_hhmm(ayar.BaslangicSaati or '09:00')
                eh, em = parse_hhmm(ayar.BitisSaati or '18:00')
                total_minutes = max(0, (eh * 60 + em) - (sh * 60 + sm))
                slot_min = max(1, ayar.SlotDakika or 30)  # En az 1 dakika
                auto_capacity = max(1, total_minutes // slot_min)
                print(f"Defter {ayar.DefterAdi} için otomatik kapasite hesaplandı: {auto_capacity} (Saat: {ayar.BaslangicSaati}-{ayar.BitisSaati}, Slot: {slot_min}dk)")
        except Exception as e:
            print(f"Kapasite hesaplama hatası: {e}")
            auto_capacity = None

    if not kapasite or kapasite == '0':
        kapasite = str(auto_capacity or 8)

    # Export işlemleri
    if format_tip in ['csv', 'excel', 'pdf']:
        # Randevu verilerini al
        start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)
        
        # Randevu sorgusu
        if session.get('is_admin', False):
            q = Randevu.query.filter(
                Randevu.FirmaID == session['firma_id'],
                Randevu.RandevuTarihi >= start_dt,
                Randevu.RandevuTarihi <= end_dt
            )
        else:
            q = db.session.query(Randevu).join(RandevuYetki).filter(
                RandevuYetki.KullaniciID == session['user_id'],
                RandevuYetki.GoruntulemeYetkisi == True,
                Randevu.FirmaID == session['firma_id'],
                Randevu.RandevuTarihi >= start_dt,
                Randevu.RandevuTarihi <= end_dt
            )
        
        # Defter filtresi
        if defter_id:
            q = q.filter(Randevu.DefterID == defter_id)
        
        randevular = q.order_by(Randevu.RandevuTarihi.desc()).all()
        
        # Çıktı alma logla
        try:
            log_user_action('VIEW', 'Rapor', detail=f"Randevu raporu {format_tip.upper()} indirildi")
        except Exception:
            pass
        
        if format_tip == 'csv':
            # CSV Export
            output = StringIO()
            writer = csv.writer(output, delimiter=';')
            writer.writerow(['Randevu ID', 'Tarih', 'Saat', 'Müşteri', 'Telefon', 'Email', 'Başlık', 'Durum', 'Süre', 'Defter'])
            for r in randevular:
                writer.writerow([
                    r.RandevuID,
                    r.RandevuTarihi.strftime('%d.%m.%Y'),
                    r.RandevuTarihi.strftime('%H:%M'),
                    f"{r.MusteriAdi} {r.MusteriSoyadi or ''}".strip(),
                    r.MusteriTelefon or '',
                    r.MusteriEmail or '',
                    r.RandevuBaslik or '',
                    r.Durum or '',
                    f"{r.RandevuSuresi or 60} dk",
                    r.defter.DefterAdi if r.defter else ''
                ])
            output.seek(0)
            filename = f"randevu_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            data = output.getvalue().encode('utf-8-sig')
            return send_file(BytesIO(data), mimetype='text/csv; charset=utf-8', as_attachment=True, download_name=filename)
        
        elif format_tip == 'excel':
            # Excel Export
            wb = Workbook()
            ws = wb.active
            ws.title = "Randevu Raporu"
            
            # Başlık satırı
            headers = ['Randevu ID', 'Tarih', 'Saat', 'Müşteri', 'Telefon', 'Email', 'Başlık', 'Durum', 'Süre', 'Defter']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
            
            # Veri satırları
            for row, r in enumerate(randevular, 2):
                ws.cell(row=row, column=1, value=r.RandevuID)
                ws.cell(row=row, column=2, value=r.RandevuTarihi.strftime('%d.%m.%Y'))
                ws.cell(row=row, column=3, value=r.RandevuTarihi.strftime('%H:%M'))
                ws.cell(row=row, column=4, value=f"{r.MusteriAdi} {r.MusteriSoyadi or ''}".strip())
                ws.cell(row=row, column=5, value=r.MusteriTelefon or '')
                ws.cell(row=row, column=6, value=r.MusteriEmail or '')
                ws.cell(row=row, column=7, value=r.RandevuBaslik or '')
                ws.cell(row=row, column=8, value=r.Durum or '')
                ws.cell(row=row, column=9, value=f"{r.RandevuSuresi or 60} dk")
                ws.cell(row=row, column=10, value=r.defter.DefterAdi if r.defter else '')
            
            # Sütun genişliklerini ayarla
            for column in ws.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Excel dosyasını kaydet
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            filename = f"randevu_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            return send_file(
                buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
        
        elif format_tip == 'pdf':
            # PDF Export
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
            
            # Türkçe font desteği
            try:
                pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/dejavu-sans.ttf'))
                pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/dejavu-sans-bold.ttf'))
                turkish_font = 'DejaVuSans'
                turkish_font_bold = 'DejaVuSans-Bold'
            except:
                try:
                    pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/arial.ttf'))
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
                    turkish_font = 'DejaVuSans'
                    turkish_font_bold = 'DejaVuSans-Bold'
                except:
                    turkish_font = 'Helvetica'
                    turkish_font_bold = 'Helvetica-Bold'
            
            # Stil tanımları
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=TA_CENTER, fontName=turkish_font_bold)
            
            # Başlık
            title = Paragraph("Randevu Raporu", title_style)
            
            # Özet bilgiler
            toplam_randevu = len(randevular)
            tamamlanan = len([r for r in randevular if r.Durum == 'Tamamlandı'])
            iptal = len([r for r in randevular if r.Durum == 'İptal'])
            beklemede = len([r for r in randevular if r.Durum == 'Beklemede'])
            
            summary_data = [
                ['Toplam Randevu', str(toplam_randevu)],
                ['Tamamlanan', str(tamamlanan)],
                ['İptal', str(iptal)],
                ['Beklemede', str(beklemede)]
            ]
            
            summary_table = Table(summary_data)
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), turkish_font),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            # Tablo verileri
            table_data = [['Tarih', 'Saat', 'Müşteri', 'Telefon', 'Başlık', 'Durum', 'Süre']]
            
            for r in randevular[:50]:  # İlk 50 kayıt
                table_data.append([
                    r.RandevuTarihi.strftime('%d.%m.%Y'),
                    r.RandevuTarihi.strftime('%H:%M'),
                    f"{r.MusteriAdi} {r.MusteriSoyadi or ''}".strip(),
                    r.MusteriTelefon or '',
                    r.RandevuBaslik or '',
                    r.Durum or '',
                    f"{r.RandevuSuresi or 60} dk"
                ])
            
            # Tablo oluştur
            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), turkish_font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), turkish_font),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            # PDF oluştur
            elements = [title, Spacer(1, 12), summary_table, Spacer(1, 12), table]
            doc.build(elements)
            buffer.seek(0)
            
            filename = f"randevu_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            return send_file(
                buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )

    return render_template('raporlar.html', 
                         baslangic=start_date.strftime('%Y-%m-%d'), 
                         bitis=end_date.strftime('%Y-%m-%d'),
                         kapasite=kapasite,
                         defter_id=defter_id,
                         defterler=defterler)


# Raporlar API - Ozet
@app.route('/api/raporlar/ozet')
@login_required
def api_raporlar_ozet():
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    defter_id = request.args.get('defter_id', '')
    try:
        start_date = datetime.strptime(baslangic, '%Y-%m-%d').date() if baslangic else (datetime.now().date() - timedelta(days=30))
        end_date = datetime.strptime(bitis, '%Y-%m-%d').date() if bitis else datetime.now().date()
    except ValueError:
        return jsonify({"success": False, "message": "Tarih formatı YYYY-MM-DD olmalı"}), 400

    # Tarihleri kapsayan datetime araligi
    start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    # Izin farkindaligi
    if session.get('is_admin', False):
        q = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_dt,
            Randevu.RandevuTarihi <= end_dt
        )
    else:
        q = db.session.query(Randevu).join(RandevuYetki).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_dt,
            Randevu.RandevuTarihi <= end_dt
        )
    
    # Defter filtresi ekle (Randevu.DefterID üzerinden)
    if defter_id:
        print(f"API Ozet - Defter filtresi uygulanıyor: {defter_id}")
        
        # Debug: Mevcut randevuları kontrol et
        all_randevular = q.all()
        print(f"DEBUG: Filtre öncesi toplam randevu: {len(all_randevular)}")
        
        # Debug: İlk randevunun DefterID'sini kontrol et
        if all_randevular:
            first_randevu = all_randevular[0]
            print(f"DEBUG: İlk randevu DefterID: {first_randevu.DefterID}")
        
        # Debug: DefterID=5 olan randevuları kontrol et
        defter_randevular = q.filter(Randevu.DefterID == defter_id).all()
        print(f"DEBUG: DefterID={defter_id} olan randevu sayısı: {len(defter_randevular)}")
        
        q = q.filter(Randevu.DefterID == defter_id)
    else:
        print("API Ozet - Defter filtresi uygulanmıyor")

    items = q.all()
    print(f"API Ozet - Toplam {len(items)} randevu bulundu")

    toplam = len(items)
    durum_counter = Counter(r.Durum or 'Bilinmiyor' for r in items)
    ref_counter = Counter(r.RandevuBaslik or 'Yok' for r in items)

    saat_counter = defaultdict(int)
    for r in items:
        saat_counter[r.RandevuTarihi.hour] += 1
    saatler = list(range(0,24))
    saat_deger = [saat_counter.get(h, 0) for h in saatler]

    return jsonify({
        "success": True,
        "toplam": toplam,
        "durumlar": durum_counter,
        "referanslar": ref_counter,
        "saatler": {"labels": saatler, "values": saat_deger}
    })

# Yoğun Saatler Raporu API
@app.route('/api/raporlar/yoğun-saatler')
@login_required
def api_raporlar_yogun_saatler():
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    kapasite_param = request.args.get('kapasite', '')
    defter_id = request.args.get('defter_id', '')
    
    try:
        start_date = datetime.strptime(baslangic, '%Y-%m-%d').date() if baslangic else (datetime.now().date() - timedelta(days=30))
        end_date = datetime.strptime(bitis, '%Y-%m-%d').date() if bitis else datetime.now().date()
    except ValueError:
        return jsonify({"success": False, "message": "Tarih formatı YYYY-MM-DD olmalı"}), 400

    # Tarihleri kapsayan datetime araligi
    start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    # Eğer defter seçilmiş ve kapasite belirtilmemişse, defterden otomatik kapasite hesapla
    auto_capacity = None
    if defter_id and (not kapasite_param or kapasite_param == '0'):
        try:
            ayar = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=session['firma_id'], Aktif=True).first()
            if ayar:
                def parse_hhmm(s):
                    h, m = (s or '09:00').split(':')
                    return int(h), int(m)
                sh, sm = parse_hhmm(ayar.BaslangicSaati or '09:00')
                eh, em = parse_hhmm(ayar.BitisSaati or '18:00')
                total_minutes = max(0, (eh * 60 + em) - (sh * 60 + sm))
                slot_min = ayar.SlotDakika or 30
                auto_capacity = max(1, total_minutes // slot_min)
        except Exception:
            auto_capacity = None

    kapasite = int(kapasite_param) if (kapasite_param and kapasite_param != '0') else int(auto_capacity or 8)

    # Izin farkindaligi
    if session.get('is_admin', False):
        q = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_dt,
            Randevu.RandevuTarihi <= end_dt
        )
    else:
        q = db.session.query(Randevu).join(RandevuYetki).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_dt,
            Randevu.RandevuTarihi <= end_dt
        )
    
    # Defter filtresi ekle (Randevu.DefterID üzerinden)
    if defter_id:
        print(f"API Yogun Saatler - Defter filtresi uygulanıyor: {defter_id}")
        q = q.filter(Randevu.DefterID == defter_id)
    else:
        print("API Yogun Saatler - Defter filtresi uygulanmıyor")

    items = q.all()

    # Saatlik dağılım
    saat_counter = defaultdict(int)
    for r in items:
        saat_counter[r.RandevuTarihi.hour] += 1
    
    # 0-23 saat arası tüm saatler
    saatler = list(range(0, 24))
    saat_deger = [saat_counter.get(h, 0) for h in saatler]
    
    # En yoğun saat
    max_appointments = max(saat_deger) if saat_deger else 0
    peak_hour = saatler[saat_deger.index(max_appointments)] if max_appointments > 0 else 0
    
    # Ortalama kapasite kullanımı
    total_days = (end_date - start_date).days + 1
    total_possible_appointments = total_days * kapasite
    total_actual_appointments = len(items)
    avg_capacity_usage = (total_actual_appointments / total_possible_appointments * 100) if total_possible_appointments > 0 else 0
    
    # Verimlilik oranı (yoğun saatlerdeki verimlilik)
    peak_hours = [h for h in saatler if saat_counter.get(h, 0) >= max_appointments * 0.8]
    peak_hours_appointments = sum(saat_counter.get(h, 0) for h in peak_hours)
    efficiency_rate = (peak_hours_appointments / total_actual_appointments * 100) if total_actual_appointments > 0 else 0
    
    # Haftalık dağılım
    weekly_counter = defaultdict(int)
    for r in items:
        week_start = r.RandevuTarihi.date() - timedelta(days=r.RandevuTarihi.weekday())
        weekly_counter[week_start] += 1
    
    # Son 12 hafta
    weekly_labels = []
    weekly_values = []
    for i in range(12):
        week_start = end_date - timedelta(weeks=i)
        week_start = week_start - timedelta(days=week_start.weekday())
        weekly_labels.insert(0, week_start.strftime('%d/%m'))
        weekly_values.insert(0, weekly_counter.get(week_start, 0))
    
    # Saatlik verimlilik
    hourly_efficiency = []
    for h in saatler:
        hour_appointments = saat_counter.get(h, 0)
        hour_efficiency = (hour_appointments / max_appointments * 100) if max_appointments > 0 else 0
        hourly_efficiency.append(round(hour_efficiency, 1))

    return jsonify({
        "success": True,
        "peakHour": peak_hour,
        "avgCapacityUsage": round(avg_capacity_usage, 1),
        "efficiencyRate": round(efficiency_rate, 1),
        "hourlyData": {
            "labels": [f"{h:02d}" for h in saatler],
            "values": saat_deger
        },
        "weeklyData": {
            "labels": weekly_labels,
            "values": weekly_values
        },
        "hourlyEfficiency": hourly_efficiency
    })

@app.route('/api/raporlar/heatmap')
@login_required
def api_raporlar_heatmap():
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    defter_id = request.args.get('defter_id', '')
    
    try:
        start_date = datetime.strptime(baslangic, '%Y-%m-%d').date() if baslangic else (datetime.now().date() - timedelta(days=30))
        end_date = datetime.strptime(bitis, '%Y-%m-%d').date() if bitis else datetime.now().date()
    except ValueError:
        return jsonify({"success": False, "message": "Tarih formatı YYYY-MM-DD olmalı"}), 400

    # Tarihleri kapsayan datetime araligi
    start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    # Izin farkindaligi
    if session.get('is_admin', False):
        q = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_dt,
            Randevu.RandevuTarihi <= end_dt
        )
    else:
        q = db.session.query(Randevu).join(RandevuYetki).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_dt,
            Randevu.RandevuTarihi <= end_dt
        )
    
    # Defter filtresi ekle (Randevu.DefterID üzerinden)
    if defter_id:
        print(f"API Heatmap - Defter filtresi uygulanıyor: {defter_id}")
        q = q.filter(Randevu.DefterID == defter_id)
    else:
        print("API Heatmap - Defter filtresi uygulanmıyor")

    items = q.all()

    # Günlük ve saatlik dağılım
    heatmap_data = {
        'Monday': {},
        'Tuesday': {},
        'Wednesday': {},
        'Thursday': {},
        'Friday': {},
        'Saturday': {},
        'Sunday': {}
    }
    
    # Gün isimleri
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for r in items:
        # Gün adını al (0=Monday, 6=Sunday)
        day_name = day_names[r.RandevuTarihi.weekday()]
        hour = r.RandevuTarihi.hour
        
        # Sadece çalışma saatleri (9-18)
        if 9 <= hour <= 18:
            if hour not in heatmap_data[day_name]:
                heatmap_data[day_name][hour] = 0
            heatmap_data[day_name][hour] += 1
    
    return jsonify({
        "success": True,
        "heatmapData": heatmap_data
    })

# Personel Performans Raporu API
@app.route('/api/raporlar/personel-performans')
@login_required
def api_raporlar_personel_performans():
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    defter_id = request.args.get('defter_id', '')

    try:
        start_date = datetime.strptime(baslangic, '%Y-%m-%d').date() if baslangic else (datetime.now().date() - timedelta(days=30))
        end_date = datetime.strptime(bitis, '%Y-%m-%d').date() if bitis else datetime.now().date()
    except ValueError:
        return jsonify({"success": False, "message": "Tarih formatı YYYY-MM-DD olmalı"}), 400

    start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    # İzin farkındalığı
    if session.get('is_admin', False):
        q = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_dt,
            Randevu.RandevuTarihi <= end_dt
        )
    else:
        q = db.session.query(Randevu).join(RandevuYetki).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_dt,
            Randevu.RandevuTarihi <= end_dt
        )

    if defter_id:
        q = q.filter(Randevu.DefterID == defter_id)

    items = q.all()

    # Personel bazında grupla
    performance = {}
    for r in items:
        user_id = r.OlusturanKullaniciID
        if user_id not in performance:
            performance[user_id] = {
                'kullaniciId': user_id,
                'adSoyad': f"{r.olusturan_kullanici.Ad} {r.olusturan_kullanici.Soyad}" if r.olusturan_kullanici else 'Bilinmiyor',
                'toplam': 0,
                'durumlar': defaultdict(int)
            }
        performance[user_id]['toplam'] += 1
        durum = r.Durum or 'Bilinmiyor'
        performance[user_id]['durumlar'][durum] += 1

    # Sonuçları listeye çevir ve toplam sayıya göre sırala
    rows = []
    for _, info in performance.items():
        rows.append({
            'kullaniciId': info['kullaniciId'],
            'adSoyad': info['adSoyad'],
            'toplam': info['toplam'],
            'beklemede': info['durumlar'].get('Beklemede', 0),
            'tamamlandi': info['durumlar'].get('Tamamlandı', 0),
            'iptal': info['durumlar'].get('İptal', 0) + info['durumlar'].get('Iptal', 0)
        })
    rows.sort(key=lambda x: x['toplam'], reverse=True)

    labels = [r['adSoyad'] for r in rows]
    counts = [r['toplam'] for r in rows]

    return jsonify({
        'success': True,
        'labels': labels,
        'counts': counts,
        'rows': rows
    })

# Duplicate endpoint removed - using /api/musteri-ara instead

# ==================== MÜŞTERİ DÜZENLEME API ====================

@app.route('/api/musteri/<int:musteri_id>')
def api_musteri_get(musteri_id):
    """Müşteri bilgilerini getir"""
    try:
        # Manuel session kontrolü - daha esnek
        # user_id kullan, kullanici_id değil
        kullanici_id = session.get('user_id')
        if not kullanici_id or not session.get('firma_id'):
            return jsonify({'success': False, 'message': 'Oturum süresi dolmuş. Lütfen tekrar giriş yapın.', 'redirect': '/login'}), 401
        
        firma_id = session.get('firma_id')
        
        # Müşteriyi bul
        musteri = Musteri.query.filter(
            Musteri.MusteriID == musteri_id,
            Musteri.FirmaID == firma_id,
            Musteri.Aktif == True
        ).first()
        
        if not musteri:
            return jsonify({'success': False, 'message': 'Müşteri bulunamadı'}), 404
        
        # Müşteri bilgilerini döndür
        return jsonify({
            'success': True,
            'musteri': {
                'MusteriID': musteri.MusteriID,
                'MusteriAdi': musteri.MusteriAdi,
                'MusteriSoyadi': musteri.MusteriSoyadi,
                'Telefon': musteri.Telefon,
                'Email': musteri.Email,
                'Yas': musteri.Yas,
                'Cinsiyet': musteri.Cinsiyet,
                'DogumTarihi': musteri.DogumTarihi.isoformat() if musteri.DogumTarihi else None,
                'Sehir': musteri.Sehir,
                'Ilce': musteri.Ilce,
                'Adres': musteri.Adres,
                'Notlar': musteri.Notlar
            }
        })
        
    except Exception as e:
        print(f"Müşteri getirme hatası: {e}")
        return jsonify({'success': False, 'message': 'Sunucu hatası'}), 500

@app.route('/api/musteri/<int:musteri_id>/update', methods=['POST'])
def api_musteri_update(musteri_id):
    """Müşteri bilgilerini güncelle"""
    try:
        # Manuel session kontrolü - daha esnek
        # user_id kullan, kullanici_id değil
        kullanici_id = session.get('user_id')
        if not kullanici_id or not session.get('firma_id'):
            return jsonify({'success': False, 'message': 'Oturum süresi dolmuş. Lütfen tekrar giriş yapın.', 'redirect': '/login'}), 401
        
        firma_id = session.get('firma_id')
        kullanici_id = session.get('user_id')
        
        # Müşteriyi bul
        musteri = Musteri.query.filter(
            Musteri.MusteriID == musteri_id,
            Musteri.FirmaID == firma_id,
            Musteri.Aktif == True
        ).first()
        
        if not musteri:
            return jsonify({'success': False, 'message': 'Müşteri bulunamadı'}), 404
        
        # Form verilerini al
        data = request.get_json()
        
        # Eski verileri kaydet (log için)
        old_data = {
            'MusteriAdi': musteri.MusteriAdi,
            'MusteriSoyadi': musteri.MusteriSoyadi,
            'Telefon': musteri.Telefon,
            'Email': musteri.Email,
            'Yas': musteri.Yas,
            'Cinsiyet': musteri.Cinsiyet,
            'DogumTarihi': musteri.DogumTarihi.isoformat() if musteri.DogumTarihi else None,
            'Sehir': musteri.Sehir,
            'Ilce': musteri.Ilce,
            'Adres': musteri.Adres,
            'Notlar': musteri.Notlar
        }
        
        # Validasyon
        if not data.get('musteri_adi') or not data.get('musteri_soyadi'):
            return jsonify({'success': False, 'message': 'Ad ve soyad zorunludur'}), 400
        
        # Telefon validasyonu
        if data.get('telefon'):
            phone = str(data['telefon']).strip()
            if phone:
                # Sıfırları temizle
                if phone.startswith('0'):
                    phone = phone[1:]
                if len(phone) == 10 and phone.startswith('5'):
                    data['telefon'] = phone
                else:
                    return jsonify({'success': False, 'message': 'Geçersiz telefon numarası formatı'}), 400
        
        # Müşteri bilgilerini güncelle
        musteri.MusteriAdi = data.get('musteri_adi', '').strip()
        musteri.MusteriSoyadi = data.get('musteri_soyadi', '').strip()
        musteri.Telefon = data.get('telefon', '').strip() or None
        musteri.Email = data.get('email', '').strip() or None
        musteri.Yas = data.get('yas') or None
        musteri.Cinsiyet = data.get('cinsiyet', '').strip() or None
        musteri.Sehir = data.get('sehir', '').strip() or None
        musteri.Ilce = data.get('ilce', '').strip() or None
        musteri.Adres = data.get('adres', '').strip() or None
        musteri.Notlar = data.get('notlar', '').strip() or None
        
        # Doğum tarihi
        if data.get('dogum_tarihi'):
            try:
                musteri.DogumTarihi = datetime.strptime(data['dogum_tarihi'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'message': 'Geçersiz doğum tarihi formatı'}), 400
        else:
            musteri.DogumTarihi = None
        
        # Veritabanına kaydet
        db.session.commit()
        
        # Log kaydı
        new_data = {
            'MusteriAdi': musteri.MusteriAdi,
            'MusteriSoyadi': musteri.MusteriSoyadi,
            'Telefon': musteri.Telefon,
            'Email': musteri.Email,
            'Yas': musteri.Yas,
            'Cinsiyet': musteri.Cinsiyet,
            'DogumTarihi': musteri.DogumTarihi.isoformat() if musteri.DogumTarihi else None,
            'Sehir': musteri.Sehir,
            'Ilce': musteri.Ilce,
            'Adres': musteri.Adres,
            'Notlar': musteri.Notlar
        }
        
        # Log kaydı oluştur
        log_entry = KullaniciLog(
            KullaniciID=session['user_id'],
            IslemTipi='UPDATE',
            TabloAdi='Musteri',
            KayitID=musteri_id,
            IPAdresi=request.remote_addr,
            EskiVeri=json.dumps(old_data, ensure_ascii=False),
            YeniVeri=json.dumps(new_data, ensure_ascii=False),
            IslemDetayi=f'Müşteri güncellendi: {musteri.MusteriAdi} {musteri.MusteriSoyadi}',
            OlusturmaTarihi=datetime.now()
        )
        db.session.add(log_entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Müşteri başarıyla güncellendi'
        })
        
    except Exception as e:
        print(f"Müşteri güncelleme hatası: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Sunucu hatası'}), 500

# ==================== EXCEL İMPORT SİSTEMİ ====================

# Upload klasörü
UPLOAD_FOLDER = 'uploads/excel_imports'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_phone(phone):
    """Telefon numarası validasyonu"""
    # Boş değer kontrolü
    if phone is None or phone == '' or (isinstance(phone, float) and pd.isna(phone)):
        return False, 'Telefon numarası boş olamaz'
    
    # String'e çevir ve boşlukları temizle
    phone_str = str(phone).strip()
    
    # Boş string kontrolü (nan, None, empty string)
    if not phone_str or phone_str.lower() in ['nan', 'none', '']:
        return False, 'Telefon numarası boş olamaz'
    
    # Bilimsel notasyonu düzelt
    if 'e' in phone_str.lower():
        try:
            phone_str = str(int(float(phone_str)))
        except:
            pass
    
    # Float formatındaysa (nokta varsa) int'e çevir
    if '.' in phone_str:
        try:
            phone_str = str(int(float(phone_str)))
        except:
            pass
    
    # Sadece rakamları al
    phone_clean = re.sub(r'\D', '', phone_str)
    
    # 10 haneli (5XXXXXXXXX) veya 11 haneli (05XXXXXXXXX) olmalı
    if len(phone_clean) == 10 and phone_clean.startswith('5'):
        # 10 haneli format kabul edilir, 0 eklenmez
        pass
    elif len(phone_clean) == 11 and phone_clean.startswith('05'):
        # 11 haneli formatı 10 haneliye çevir (sıfırı kaldır)
        phone_clean = phone_clean[1:]
    else:
        return False, f'Telefon 10 (5XXXXXXXXX) veya 11 (05XXXXXXXXX) haneli olmalıdır'
    
    return True, phone_clean

def validate_email(email):
    """Email validasyonu"""
    if not email or pd.isna(email):
        return True, None  # Email opsiyonel
    
    email = str(email).strip()
    if not email:
        return True, None
    
    # Basit email regex
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return False, 'Geçersiz email formatı'
    
    return True, email

def validate_date(date_str):
    """Tarih validasyonu"""
    if not date_str or pd.isna(date_str):
        return True, None  # Tarih opsiyonel
    
    date_str = str(date_str).strip()
    if not date_str:
        return True, None
    
    # Farklı tarih formatlarını dene (Türk formatı öncelikli)
    date_formats = ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d']
    
    for date_format in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, date_format)
            return True, parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return False, 'Geçersiz tarih formatı (GG.AA.YYYY veya GG/AA/YYYY kullanın, örn: 18.05.1974)'

@app.route('/musteriler/import')
@login_required
def musteriler_import():
    """Müşteri Excel import sayfası"""
    return render_template('musteriler_import.html')

@app.route('/api/musteri-import/template')
@login_required
def musteri_import_template():
    """Excel template dosyasını kullanıcının diline göre oluştur ve indir"""
    from flask_babel import get_locale
    
    # Kullanıcının dil seçimini al
    locale = str(get_locale())
    
    # Dil bazlı çeviriler
    translations = {
        'tr': {
            'columns': ['Ad', 'Soyad', 'Ülke Kodu', 'Telefon', 'Email', 'Cinsiyet', 'Doğum Tarihi', 'Adres'],
            'sample_data': {
                'Ad': ['Ahmet', 'Ayşe', 'Mehmet'],
                'Soyad': ['Yılmaz', 'Demir', 'Kaya'],
                'Ülke Kodu': ['90', '90', '90'],
                'Telefon': ['5551234567', '5559876543', '5551112233'],
                'Email': ['ahmet@mail.com', 'ayse@mail.com', 'mehmet@mail.com'],
                'Cinsiyet': ['Erkek', 'Kadın', 'Erkek'],
                'Doğum Tarihi': ['15.05.1990', '20.08.1985', '10.03.1995'],
                'Adres': ['İstanbul, Kadıköy', 'Ankara, Çankaya', 'İzmir, Karşıyaka']
            },
            'guide_title': 'Müşteri İçe Aktarma - Kullanım Kılavuzu',
            'guide_sheet': 'Kullanım Kılavuzu',
            'customers_sheet': 'Müşteriler'
        },
        'en': {
            'columns': ['Name', 'Surname', 'Country Code', 'Phone', 'Email', 'Gender', 'Birth Date', 'Address'],
            'sample_data': {
                'Name': ['John', 'Jane', 'Michael'],
                'Surname': ['Smith', 'Doe', 'Johnson'],
                'Country Code': ['90', '90', '90'],
                'Phone': ['5551234567', '5559876543', '5551112233'],
                'Email': ['john@mail.com', 'jane@mail.com', 'michael@mail.com'],
                'Gender': ['Male', 'Female', 'Male'],
                'Birth Date': ['15.05.1990', '20.08.1985', '10.03.1995'],
                'Address': ['Istanbul, Kadikoy', 'Ankara, Cankaya', 'Izmir, Karsiyaka']
            },
            'guide_title': 'Customer Import - User Guide',
            'guide_sheet': 'User Guide',
            'customers_sheet': 'Customers'
        },
        'de': {
            'columns': ['Vorname', 'Nachname', 'Ländercode', 'Telefon', 'E-Mail', 'Geschlecht', 'Geburtsdatum', 'Adresse'],
            'sample_data': {
                'Vorname': ['Hans', 'Anna', 'Michael'],
                'Nachname': ['Schmidt', 'Müller', 'Weber'],
                'Ländercode': ['90', '90', '90'],
                'Telefon': ['5551234567', '5559876543', '5551112233'],
                'E-Mail': ['hans@mail.com', 'anna@mail.com', 'michael@mail.com'],
                'Geschlecht': ['Männlich', 'Weiblich', 'Männlich'],
                'Geburtsdatum': ['15.05.1990', '20.08.1985', '10.03.1995'],
                'Adresse': ['Istanbul, Kadikoy', 'Ankara, Cankaya', 'Izmir, Karsiyaka']
            },
            'guide_title': 'Kundenimport - Benutzerhandbuch',
            'guide_sheet': 'Benutzerhandbuch',
            'customers_sheet': 'Kunden'
        },
        'fr': {
            'columns': ['Prénom', 'Nom', 'Code Pays', 'Téléphone', 'E-mail', 'Genre', 'Date de Naissance', 'Adresse'],
            'sample_data': {
                'Prénom': ['Pierre', 'Marie', 'Jean'],
                'Nom': ['Martin', 'Dubois', 'Durand'],
                'Code Pays': ['90', '90', '90'],
                'Téléphone': ['5551234567', '5559876543', '5551112233'],
                'E-mail': ['pierre@mail.com', 'marie@mail.com', 'jean@mail.com'],
                'Genre': ['Homme', 'Femme', 'Homme'],
                'Date de Naissance': ['15.05.1990', '20.08.1985', '10.03.1995'],
                'Adresse': ['Istanbul, Kadikoy', 'Ankara, Cankaya', 'Izmir, Karsiyaka']
            },
            'guide_title': 'Importation de Clients - Guide d\'Utilisation',
            'guide_sheet': 'Guide d\'Utilisation',
            'customers_sheet': 'Clients'
        }
    }
    
    # Varsayılan olarak Türkçe
    lang_data = translations.get(locale, translations['tr'])
    
    # DataFrame oluştur
    df = pd.DataFrame(lang_data['sample_data'])
    
    # Geçici dosya oluştur
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    temp_path = temp_file.name
    temp_file.close()
    
    # Excel'e yaz
    df.to_excel(temp_path, index=False, sheet_name=lang_data['customers_sheet'])
    
    # Workbook'u yükle ve stil ekle
    wb = load_workbook(temp_path)
    ws = wb[lang_data['customers_sheet']]
    
    # Başlık stili
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF', size=12)
    header_alignment = Alignment(horizontal='center', vertical='center')
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Başlık satırına stil uygula
    for col in range(1, len(df.columns) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = border
    
    # Kolon genişliklerini ayarla
    for col in range(1, len(df.columns) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 20
    
    # Veri satırlarına border ekle ve telefon+ülke kodu kolonlarını TEXT formatına çevir
    telefon_col_index = None
    ulke_kodu_col_index = None
    
    for col_idx, col_name in enumerate(df.columns, start=1):
        col_lower = str(col_name).lower()
        if 'telefon' in col_lower or 'phone' in col_lower or 'téléphone' in col_lower:
            if 'kod' not in col_lower and 'code' not in col_lower:  # "Ülke Kodu" değilse
                telefon_col_index = col_idx
        elif 'kod' in col_lower or 'code' in col_lower:
            ulke_kodu_col_index = col_idx
    
    for row in range(2, len(df) + 2):
        for col in range(1, len(df.columns) + 1):
            cell = ws.cell(row=row, column=col)
            cell.border = border
            # Telefon ve ülke kodu kolonlarını TEXT olarak formatla
            if col == telefon_col_index or col == ulke_kodu_col_index:
                cell.number_format = '@'  # TEXT format
    
    # Kaydet
    wb.save(temp_path)
    
    # Dosya adını dile göre ayarla
    filename = f'customer_import_template_{locale}.xlsx'
    
    return send_file(temp_path, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/api/musteri-import/upload', methods=['POST'])
@login_required
def musteri_import_upload():
    """Excel dosyasını yükle ve parse et"""
    try:
        # Dosya kontrolü
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Dosya seçilmedi'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Dosya seçilmedi'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'Sadece .xlsx veya .xls dosyaları yüklenebilir'}), 400
        
        # Upload klasörünü oluştur
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        
        # Güvenli dosya adı oluştur
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{session['user_id']}_{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Dosyayı kaydet
        file.save(filepath)
        
        # Excel'i oku - telefon kolonunu string olarak oku
        df = pd.read_excel(filepath, sheet_name=0, dtype=str, keep_default_na=False)
        
        # Boş satırları temizle
        df = df.dropna(how='all')
        
        # Kolonları al
        columns = df.columns.tolist()
        
        # İlk 5 satırı önizleme için al
        preview_data = df.head(5).fillna('').to_dict('records')
        
        return jsonify({
            'success': True,
            'filename': unique_filename,
            'filepath': filepath,
            'columns': columns,
            'preview': preview_data,
            'total_rows': len(df),
            'message': f'{len(df)} satır müşteri verisi yüklendi'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Dosya yüklenirken hata: {str(e)}'}), 500

@app.route('/api/musteri-import/preview', methods=['POST'])
@login_required
def musteri_import_preview():
    """Kolon eşleştirmesi sonrası önizleme ve validasyon"""
    try:
        data = request.json
        filepath = data.get('filepath')
        column_mapping = data.get('column_mapping')  # {'excel_column': 'db_field'}
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({'success': False, 'message': 'Dosya bulunamadı'}), 400
        
        # Excel'i oku - tüm kolonları string olarak oku
        df = pd.read_excel(filepath, sheet_name=0, dtype=str, keep_default_na=False)
        df = df.dropna(how='all')
        
        # Validasyon sonuçları
        validated_data = []
        errors_count = 0
        warnings_count = 0
        
        # Mevcut telefon numaralarını al (duplicate kontrolü için)
        existing_phones = set()
        mevcut_musteriler = Musteri.query.filter_by(
            FirmaID=session['firma_id'],
            Aktif=True
        ).all()
        for m in mevcut_musteriler:
            if m.Telefon:
                # Telefon numarasını normalize et (hem 10 hem 11 haneli formatları kabul et)
                phone_normalized = m.Telefon.strip()
                if phone_normalized.startswith('0') and len(phone_normalized) == 11:
                    # 11 haneli: 0531714415 -> 531714415
                    existing_phones.add(phone_normalized[1:])
                    existing_phones.add(phone_normalized)  # Orijinal formatı da ekle
                elif len(phone_normalized) == 10 and phone_normalized.startswith('5'):
                    # 10 haneli: 531714415 -> 0531714415
                    existing_phones.add(phone_normalized)
                    existing_phones.add('0' + phone_normalized)  # 0 eklenmiş formatı da ekle
                else:
                    existing_phones.add(phone_normalized)
        
        # Dosyadaki telefon numaralarını takip et (dosya içi duplicate kontrolü)
        file_phones = set()
        
        for idx, row in df.iterrows():
            row_data = {
                'row_number': idx + 2,  # Excel satır numarası (1=header)
                'data': {},
                'errors': [],
                'warnings': [],
                'status': 'valid'
            }
            
            # Her kolon için veriyi al ve validate et
            for excel_col, db_field in column_mapping.items():
                if excel_col not in df.columns:
                    continue
                
                value = row[excel_col]
                
                # Ad validasyonu
                if db_field == 'MusteriAdi':
                    if pd.isna(value) or str(value).strip() == '':
                        row_data['errors'].append('Ad boş olamaz')
                        row_data['status'] = 'error'
                    else:
                        row_data['data']['MusteriAdi'] = str(value).strip()
                
                # Soyad validasyonu
                elif db_field == 'MusteriSoyadi':
                    if pd.isna(value) or str(value).strip() == '':
                        row_data['errors'].append('Soyad boş olamaz')
                        row_data['status'] = 'error'
                    else:
                        row_data['data']['MusteriSoyadi'] = str(value).strip()
                
                # Telefon validasyonu
                elif db_field == 'Telefon':
                    valid, result = validate_phone(value)
                    if not valid:
                        row_data['errors'].append(result)
                        row_data['status'] = 'error'
                    else:
                        row_data['data']['Telefon'] = result
                        
                        # Duplicate kontrolü - normalize edilmiş telefon ile kontrol et
                        phone_for_check = result
                        if len(result) == 10 and result.startswith('5'):
                            # 10 haneli format için 11 haneli versiyonunu da kontrol et
                            phone_11_digit = '0' + result
                            if phone_for_check in existing_phones or phone_11_digit in existing_phones:
                                row_data['warnings'].append('Bu telefon numarası sistemde zaten kayıtlı')
                                if row_data['status'] != 'error':
                                    row_data['status'] = 'duplicate'
                        elif len(result) == 11 and result.startswith('05'):
                            # 11 haneli format için 10 haneli versiyonunu da kontrol et
                            phone_10_digit = result[1:]
                            if phone_for_check in existing_phones or phone_10_digit in existing_phones:
                                row_data['warnings'].append('Bu telefon numarası sistemde zaten kayıtlı')
                                if row_data['status'] != 'error':
                                    row_data['status'] = 'duplicate'
                        elif result in existing_phones:
                            row_data['warnings'].append('Bu telefon numarası sistemde zaten kayıtlı')
                            if row_data['status'] != 'error':
                                row_data['status'] = 'duplicate'
                        elif result in file_phones:
                            row_data['warnings'].append('Bu telefon numarası dosyada birden fazla kez var')
                            if row_data['status'] != 'error':
                                row_data['status'] = 'warning'
                        else:
                            file_phones.add(result)
                
                # Email validasyonu
                elif db_field == 'Email':
                    valid, result = validate_email(value)
                    if not valid:
                        row_data['errors'].append(result)
                        row_data['status'] = 'error'
                    else:
                        row_data['data']['Email'] = result
                
                # Ülke Kodu (opsiyonel, sadece kaydet)
                elif db_field == 'UlkeKodu':
                    if not pd.isna(value) and str(value).strip():
                        row_data['data']['UlkeKodu'] = str(value).strip()
                
                # Cinsiyet
                elif db_field == 'Cinsiyet':
                    if not pd.isna(value) and str(value).strip():
                        cinsiyet = str(value).strip()
                        cinsiyet_lower = cinsiyet.lower()
                        
                        # Erkek için tüm dillerdeki değerler
                        erkek_values = [
                            # Türkçe
                            'erkek', 'e', 'e.',
                            # İngilizce
                            'male', 'm', 'm.', 'man', 'men',
                            # Fransızca
                            'homme', 'masculin', 'mâle',
                            # Almanca
                            'männlich', 'mann', 'm'
                        ]
                        
                        # Kadın için tüm dillerdeki değerler
                        kadin_values = [
                            # Türkçe
                            'kadın', 'kadýn', 'k', 'k.',
                            # İngilizce
                            'female', 'f', 'f.', 'woman', 'women',
                            # Fransızca
                            'femme', 'féminin', 'femelle',
                            # Almanca
                            'weiblich', 'frau', 'w'
                        ]
                        
                        if cinsiyet_lower in erkek_values:
                            row_data['data']['Cinsiyet'] = 'Erkek'
                        elif cinsiyet_lower in kadin_values:
                            row_data['data']['Cinsiyet'] = 'Kadın'
                        else:
                            row_data['warnings'].append(f'Bilinmeyen cinsiyet: {cinsiyet}')
                            row_data['data']['Cinsiyet'] = None
                
                # Doğum tarihi
                elif db_field == 'DogumTarihi':
                    valid, result = validate_date(value)
                    if not valid:
                        row_data['errors'].append(result)
                        if row_data['status'] != 'error':
                            row_data['status'] = 'warning'
                    else:
                        row_data['data']['DogumTarihi'] = result
                
                # Diğer alanlar (Adres, Notlar)
                else:
                    if not pd.isna(value) and str(value).strip():
                        row_data['data'][db_field] = str(value).strip()
            
            # İstatistikleri güncelle
            if row_data['status'] == 'error':
                errors_count += 1
            elif row_data['status'] in ['duplicate', 'warning']:
                warnings_count += 1
            
            validated_data.append(row_data)
        
        return jsonify({
            'success': True,
            'data': validated_data,
            'stats': {
                'total': len(validated_data),
                'valid': len([d for d in validated_data if d['status'] == 'valid']),
                'errors': errors_count,
                'warnings': warnings_count,
                'duplicates': len([d for d in validated_data if d['status'] == 'duplicate'])
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Önizleme hatası: {str(e)}'}), 500

@app.route('/api/musteri-import/process', methods=['POST'])
@login_required
def musteri_import_process():
    """Validasyondan geçen verileri işle ve kaydet"""
    try:
        data = request.json
        validated_data = data.get('data', [])
        import_options = data.get('options', {})
        
        # Import seçenekleri
        skip_errors = import_options.get('skip_errors', True)
        update_duplicates = import_options.get('update_duplicates', False)
        skip_duplicates = import_options.get('skip_duplicates', True)
        
        # Sonuçlar
        results = {
            'success': 0,
            'skipped': 0,
            'updated': 0,
            'errors': 0,
            'details': []
        }
        
        for row in validated_data:
            row_number = row['row_number']
            status = row['status']
            row_data = row['data']
            
            try:
                # Hatalı kayıtları atla
                if status == 'error':
                    if skip_errors:
                        results['skipped'] += 1
                        results['details'].append({
                            'row': row_number,
                            'status': 'skipped',
                            'message': 'Validasyon hatası nedeniyle atlandı'
                        })
                        continue
                    else:
                        results['errors'] += 1
                        results['details'].append({
                            'row': row_number,
                            'status': 'error',
                            'message': ', '.join(row['errors'])
                        })
                        continue
                
                # Duplicate kontrolü
                if status == 'duplicate':
                    telefon = row_data.get('Telefon')
                    existing = Musteri.query.filter_by(
                        FirmaID=session['firma_id'],
                        Telefon=telefon,
                        Aktif=True
                    ).first()
                    
                    if existing and update_duplicates:
                        # Mevcut kaydı güncelle
                        for key, value in row_data.items():
                            if value is not None:
                                setattr(existing, key, value)
                        
                        db.session.commit()
                        
                        # Güncellenen müşteri için log
                        update_log = KullaniciLog(
                            KullaniciID=session['user_id'],
                            IslemTipi='musteri_excel_import_update',
                            TabloAdi='Musteri',
                            KayitID=existing.MusteriID,
                            EskiVeri=json.dumps({
                                'MusteriAdi': existing.MusteriAdi,
                                'MusteriSoyadi': existing.MusteriSoyadi,
                                'Telefon': existing.Telefon,
                                'Email': existing.Email
                            }, ensure_ascii=False),
                            YeniVeri=json.dumps({
                                'MusteriAdi': row_data.get('MusteriAdi'),
                                'MusteriSoyadi': row_data.get('MusteriSoyadi'),
                                'Telefon': row_data.get('Telefon'),
                                'Email': row_data.get('Email')
                            }, ensure_ascii=False),
                            IslemDetayi=f'Excel import ile müşteri güncellendi: {row_data.get("MusteriAdi")} {row_data.get("MusteriSoyadi")} (Telefon: {row_data.get("Telefon")})',
                            IPAdresi=get_client_ip(),
                            UserAgent=request.headers.get('User-Agent', '')
                        )
                        db.session.add(update_log)
                        db.session.commit()
                        
                        results['updated'] += 1
                        results['details'].append({
                            'row': row_number,
                            'status': 'updated',
                            'message': f'Mevcut müşteri güncellendi: {row_data.get("MusteriAdi")} {row_data.get("MusteriSoyadi")}'
                        })
                        continue
                    elif skip_duplicates:
                        results['skipped'] += 1
                        results['details'].append({
                            'row': row_number,
                            'status': 'skipped',
                            'message': 'Duplicate kayıt atlandı'
                        })
                        continue
                
                # Yeni müşteri oluştur
                yeni_musteri = Musteri(
                    FirmaID=session['firma_id'],
                    MusteriAdi=row_data.get('MusteriAdi'),
                    MusteriSoyadi=row_data.get('MusteriSoyadi'),
                    Telefon=row_data.get('Telefon'),
                    Email=row_data.get('Email'),
                    Cinsiyet=row_data.get('Cinsiyet'),
                    DogumTarihi=row_data.get('DogumTarihi'),
                    Adres=row_data.get('Adres'),
                    Notlar=row_data.get('Notlar'),
                    Aktif=True
                )
                
                db.session.add(yeni_musteri)
                db.session.commit()
                
                # Her müşteri için ayrı log
                musteri_log = KullaniciLog(
                    KullaniciID=session['user_id'],
                    IslemTipi='musteri_excel_import_add',
                    TabloAdi='Musteri',
                    KayitID=yeni_musteri.MusteriID,
                    YeniVeri=json.dumps({
                        'MusteriAdi': row_data.get('MusteriAdi'),
                        'MusteriSoyadi': row_data.get('MusteriSoyadi'),
                        'Telefon': row_data.get('Telefon'),
                        'Email': row_data.get('Email'),
                        'Cinsiyet': row_data.get('Cinsiyet'),
                        'DogumTarihi': row_data.get('DogumTarihi'),
                        'Adres': row_data.get('Adres'),
                        'Notlar': row_data.get('Notlar')
                    }, ensure_ascii=False),
                    IslemDetayi=f'Excel import ile müşteri eklendi: {row_data.get("MusteriAdi")} {row_data.get("MusteriSoyadi")} (Telefon: {row_data.get("Telefon")})',
                    IPAdresi=get_client_ip(),
                    UserAgent=request.headers.get('User-Agent', '')
                )
                db.session.add(musteri_log)
                db.session.commit()
                
                results['success'] += 1
                results['details'].append({
                    'row': row_number,
                    'status': 'success',
                    'message': f'Müşteri eklendi: {row_data.get("MusteriAdi")} {row_data.get("MusteriSoyadi")}'
                })
                
            except Exception as e:
                db.session.rollback()
                results['errors'] += 1
                results['details'].append({
                    'row': row_number,
                    'status': 'error',
                    'message': f'Kayıt hatası: {str(e)}'
                })
        
        # Genel Excel import log kaydı
        log_mesaj = f"Excel import tamamlandı: {results['success']} müşteri eklendi, {results['updated']} müşteri güncellendi, {results['skipped']} kayıt atlandı, {results['errors']} hata oluştu"
        yeni_log = KullaniciLog(
            KullaniciID=session['user_id'],
            IslemTipi='musteri_excel_import_summary',
            TabloAdi='Musteri',
            IslemDetayi=log_mesaj,
            IPAdresi=get_client_ip(),
            UserAgent=request.headers.get('User-Agent', '')
        )
        db.session.add(yeni_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'results': results,
            'message': log_mesaj
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'İşlem hatası: {str(e)}'}), 500

# ==================== TODO SİSTEMİ ====================

@app.route('/gorevler')
@login_required
def gorevler():
    """Görev listesi sayfası - Randevu bazlı görevler"""
    firma_id = session['firma_id']
    
    # Kullanıcının randevu bazlı TÜM görevlerini getir (tamamlananlar dahil).
    # Ekranda varsayılan olarak tamamlananlar JS ile gizlenecek; filtre 'Tamamlandı' seçildiğinde gösterilecek.
    user_todos = (Todo.query
        .filter_by(KullaniciID=session['user_id'], Tip='Randevu')
        .order_by(Todo.Oncelik.desc(), Todo.OlusturmaTarihi.desc())
        .all())
    
    # Firma bazlı durumları getir
    durumlar = TodoDurum.query.filter_by(FirmaID=firma_id, Aktif=True).order_by(TodoDurum.Sira).all()
    
    # Her durum için sayıları DB'den güvenilir şekilde hesapla (tamamlananlar dahil)
    from sqlalchemy import func
    counts_by_name = dict(
        db.session.query(TodoDurum.DurumAdi, func.count(Todo.TodoID))
        .join(Todo, Todo.DurumID == TodoDurum.DurumID)
        .filter(Todo.KullaniciID == session['user_id'], Todo.Tip == 'Randevu')
        .group_by(TodoDurum.DurumAdi)
        .all()
    )
    durum_istatistikleri = [
        {
            'durum': durum,
            'sayi': int(counts_by_name.get(durum.DurumAdi, 0) or 0)
        }
        for durum in durumlar
    ]
    
    # Toplam görev sayısı
    toplam_gorev = len(user_todos)
    
    # Yaklaşan hatırlatmalar (bugünden itibaren 3 gün)
    bugun = datetime.now().date()
    uc_gun_sonra = bugun + timedelta(days=3)
    yaklasan_gorevler = [t for t in user_todos 
                        if t.HatirlatmaTarihi and (not t.durum or t.durum.DurumAdi != 'Tamamlandı')
                        and bugun <= t.HatirlatmaTarihi.date() <= uc_gun_sonra]
    
    # Bu ayın ilk ve son gününü hesapla
    from datetime import date
    today = date.today()
    first_day_of_month = date(today.year, today.month, 1)
    if today.month == 12:
        last_day_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)
    
    return render_template('gorevler.html', 
                         gorevler=user_todos,
                         toplam_gorev=toplam_gorev,
                         durum_istatistikleri=durum_istatistikleri,
                         yaklasan_gorevler=yaklasan_gorevler,
                         first_day_of_month=first_day_of_month,
                         last_day_of_month=last_day_of_month)

@app.route('/gorev-raporlar')
@login_required
def gorev_raporlar():
    """Görev raporları sayfası"""
    return render_template('gorev_raporlar.html')

@app.route('/todos')
@login_required
def todos():
    """Todo listesi sayfası - Kişisel yapılacaklar"""
    # Kullanıcının sadece kişisel yapılacaklarını getir
    user_todos = Todo.query.filter_by(KullaniciID=session['user_id'], Tip='Kisisel').order_by(
        Todo.Oncelik.desc(), Todo.OlusturmaTarihi.desc()
    ).all()
    
    # İstatistikler
    toplam_todo = len(user_todos)
    tamamlanan_todo = len([t for t in user_todos if t.durum and t.durum.DurumAdi == 'Tamamlandı'])
    beklemede_todo = len([t for t in user_todos if t.durum and t.durum.DurumAdi == 'Beklemede'])
    devam_eden_todo = len([t for t in user_todos if t.durum and t.durum.DurumAdi == 'Devam Ediyor'])
    
    # Yaklaşan hatırlatmalar (bugünden itibaren 3 gün)
    bugun = datetime.now().date()
    uc_gun_sonra = bugun + timedelta(days=3)
    yaklasan_todos = [t for t in user_todos 
                     if t.HatirlatmaTarihi and (not t.durum or t.durum.DurumAdi != 'Tamamlandı')
                     and bugun <= t.HatirlatmaTarihi.date() <= uc_gun_sonra]
    
    return render_template('todos.html', 
                         todos=user_todos,
                         toplam_todo=toplam_todo,
                         tamamlanan_todo=tamamlanan_todo,
                         beklemede_todo=beklemede_todo,
                         devam_eden_todo=devam_eden_todo,
                         yaklasan_todos=yaklasan_todos)

def create_default_todo_durumlar(firma_id, durum_adi):
    """Yapılacaklar için varsayılan durumları oluştur"""
    try:
        # Varsayılan durumları oluştur
        default_durumlar = [
            {'DurumAdi': 'Beklemede', 'Renk': '#ffc107', 'Sira': 1, 'Aktif': True},
            {'DurumAdi': 'Devam Ediyor', 'Renk': '#17a2b8', 'Sira': 2, 'Aktif': True},
            {'DurumAdi': 'Tamamlandı', 'Renk': '#28a745', 'Sira': 3, 'Aktif': True}
        ]
        
        for durum_data in default_durumlar:
            # Durum zaten var mı kontrol et
            existing = TodoDurum.query.filter_by(
                DurumAdi=durum_data['DurumAdi'], 
                FirmaID=firma_id
            ).first()
            
            if not existing:
                yeni_durum = TodoDurum(
                    DurumAdi=durum_data['DurumAdi'],
                    Renk=durum_data['Renk'],
                    Sira=durum_data['Sira'],
                    Aktif=durum_data['Aktif'],
                    FirmaID=firma_id
                )
                db.session.add(yeni_durum)
        
        db.session.commit()
        
        # İstenen durumun ID'sini döndür
        durum = TodoDurum.query.filter_by(DurumAdi=durum_adi, FirmaID=firma_id).first()
        return durum.DurumID if durum else None
        
    except Exception as e:
        print(f"Varsayılan durumlar oluşturulurken hata: {e}")
        db.session.rollback()
        return None

@app.route('/todos/ekle', methods=['POST'])
@login_required
def todo_ekle():
    """Yeni todo ekle"""
    try:
        data = request.get_json()
        print(f"Todo ekleme isteği: {data}")  # Debug log
        
        # Tarih formatlarını parse et
        bitis_tarihi = None
        if data.get('bitis_tarihi'):
            bitis_tarihi = datetime.strptime(data['bitis_tarihi'], '%Y-%m-%d')
        
        hatirlatma_tarihi = None
        if data.get('hatirlatma_tarihi'):
            hatirlatma_tarihi = datetime.strptime(data['hatirlatma_tarihi'], '%Y-%m-%d')
        
        # Randevu tarihini parse et
        randevu_tarihi = None
        if data.get('randevu_tarihi'):
            randevu_tarihi = datetime.strptime(data['randevu_tarihi'], '%Y-%m-%d').date()
        
        # Durum ID'sini al - önce durum_id, sonra durum adından
        durum_id = None
        if data.get('durum_id'):
            # Direkt durum ID'si gönderilmiş
            durum_id = int(data['durum_id'])
            print(f"Durum ID direkt alındı: {durum_id}")
        elif data.get('durum'):
            # Durum adından ID'yi bul (firma kontrolü yok)
            durum = TodoDurum.query.filter_by(DurumAdi=data['durum']).first()
            if durum:
                durum_id = durum.DurumID
                print(f"Durum adından ID bulundu: {durum_id}")
            else:
                # Eğer durum bulunamazsa varsayılan durumları oluştur
                durum_id = create_default_todo_durumlar(session['firma_id'], data['durum'])
                print(f"Varsayılan durum oluşturuldu: {durum_id}")
        
        print(f"Final durum_id: {durum_id}")
        
        # Tip belirleme
        todo_tip = data.get('tip', 'Kisisel')
        
        # Yeni todo oluştur
        yeni_todo = Todo(
            KullaniciID=session['user_id'],
            Baslik=data['baslik'],
            Aciklama=data.get('aciklama', ''),
            Oncelik=data.get('oncelik', 'Orta'),
            DurumID=durum_id,  # Yeni durum sistemi
            Tip=todo_tip,  # Kisisel veya Randevu
            BitisTarihi=bitis_tarihi,
            HatirlatmaTarihi=hatirlatma_tarihi,
            # Müşteri bilgileri
            MusteriAdi=data.get('musteri_adi', ''),
            MusteriSoyadi=data.get('musteri_soyadi', ''),
            MusteriTelefon=data.get('musteri_telefon', ''),
            MusteriEmail=data.get('musteri_email', ''),
            # Randevu bilgileri (eğer görev ise)
            RandevuTarihi=randevu_tarihi,
            RandevuDefteriID=data.get('randevu_defteri_id'),
            RandevuSaati=data.get('selected_randevu_saat'),
            AtananKullaniciID=data.get('kullanici_id')
        )
        
        print(f"Todo oluşturuluyor: {yeni_todo}")  # Debug log
        db.session.add(yeni_todo)
        db.session.flush()  # ID'yi almak için
        
        # Eğer randevu bilgileri varsa randevu oluştur
        if (data.get('randevu_tarihi') and data.get('randevu_defteri_id') and 
            data.get('selected_randevu_saat')):
            
            try:
                # Randevu tarihini parse et
                randevu_dt = datetime.strptime(f"{data['randevu_tarihi']} {data['selected_randevu_saat']}", '%Y-%m-%d %H:%M')
                
                # Randevu defterini kontrol et
                defter_ayar = RandevuDefterAyar.query.filter_by(
                    AyarID=data['randevu_defteri_id'], 
                    FirmaID=session['firma_id'], 
                    Aktif=True
                ).first()
                
                if defter_ayar:
                    # Çakışma kontrolü
                    randevu_suresi = defter_ayar.SlotDakika  # Defter ayarındaki slot dakikası
                    randevu_bas = randevu_dt
                    randevu_bit = randevu_dt + timedelta(minutes=randevu_suresi)
                    
                    # Mevcut randevularla çakışma kontrolü
                    day_start_chk = datetime(randevu_dt.year, randevu_dt.month, randevu_dt.day, 0, 0)
                    day_end_chk = day_start_chk + timedelta(days=1)
                    
                    existing_randevular = Randevu.query.filter(
                        Randevu.FirmaID == session['firma_id'],
                        Randevu.DefterID == data['randevu_defteri_id'],
                        Randevu.RandevuTarihi >= day_start_chk,
                        Randevu.RandevuTarihi < day_end_chk,
                        Randevu.Durum != 'Iptal'
                    ).all()
                    
                    cakisma_var = False
                    for r in existing_randevular:
                        r_start = r.RandevuTarihi
                        r_dur = r.RandevuSuresi or 60
                        r_end = r_start + timedelta(minutes=int(r_dur))
                        if r_start < randevu_bit and randevu_bas < r_end:
                            cakisma_var = True
                            break
                    
                    if not cakisma_var:
                        # Randevu oluştur
                        randevu = Randevu(
                            RandevuBaslik=data['baslik'],
                            RandevuAciklamasi=data.get('aciklama', ''),
                            RandevuTarihi=randevu_dt,
                            RandevuSuresi=randevu_suresi,
                            MusteriAdi=data.get('musteri_adi', ''),
                            MusteriSoyadi=data.get('musteri_soyadi', 'Müşteri'),
                            MusteriTelefon=data.get('musteri_telefon', ''),
                            MusteriEmail=data.get('musteri_email', ''),
                            OlusturanKullaniciID=session['user_id'],
                            FirmaID=session['firma_id'],
                            DefterID=data['randevu_defteri_id'],
                            GorevID=yeni_todo.TodoID  # Görev ID'sini bağla
                        )
                        
                        db.session.add(randevu)
                        db.session.flush()  # Randevu ID'sini almak için
                        
                        # Todo'ya RandevuID'yi ekle
                        yeni_todo.RandevuID = randevu.RandevuID
                        
                        # Kullanıcıya randevu yetkisi ver
                        try:
                            randevu_yetki = RandevuYetki(
                                RandevuID=randevu.RandevuID,
                                KullaniciID=session['user_id'],
                                GoruntulemeYetkisi=True,
                                DuzenlemeYetkisi=True,
                                SilmeYetkisi=True
                            )
                            db.session.add(randevu_yetki)
                        except Exception as yetki_error:
                            print(f"Randevu yetkisi ekleme hatası: {yetki_error}")
                        
                        print(f"Randevu oluşturuldu: {randevu_dt} - {data['selected_randevu_saat']}")
                    else:
                        print("Randevu oluşturulamadı: Çakışma var")
                else:
                    print("Randevu defteri bulunamadı")
                    
            except Exception as randevu_error:
                print(f"Randevu oluşturma hatası: {randevu_error}")
                # Randevu hatası olsa bile todo'yu kaydet
        
        db.session.commit()
        print("Todo başarıyla kaydedildi")  # Debug log
        
        # Log ekle
        try:
            log_user_action(
                action_type='Todo Oluşturuldu',
                table_name='Todos',
                record_id=yeni_todo.TodoID,
                old_data=None,
                new_data={'baslik': data['baslik'], 'oncelik': data.get('oncelik', 'Orta')},
                detail=f"Başlık: {data['baslik']}"
            )
        except Exception as log_error:
            print(f"Log hatası (önemli değil): {log_error}")
        
        return jsonify({'success': True, 'message': 'Todo başarıyla eklendi!'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Todo ekleme hatası: {str(e)}")  # Debug log
        import traceback
        traceback.print_exc()  # Detaylı hata log'u
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/todos/<int:todo_id>/guncelle', methods=['GET', 'POST'])
@login_required
def todo_guncelle(todo_id):
    """Todo güncelle"""
    try:
        todo = Todo.query.filter_by(TodoID=todo_id, KullaniciID=session['user_id']).first()
        if not todo:
            return jsonify({'success': False, 'message': 'Todo bulunamadı!'}), 404
        
        # GET isteği - todo verilerini döndür
        if request.method == 'GET':
            return jsonify({
                'success': True,
                'todo': {
                    'TodoID': todo.TodoID,
                    'Baslik': todo.Baslik,
                    'Aciklama': todo.Aciklama,
                    'Oncelik': todo.Oncelik,
                    'DurumID': todo.DurumID,
                    'Durum': todo.durum.DurumAdi if todo.durum else None,
                    'BitisTarihi': todo.BitisTarihi.strftime('%Y-%m-%d') if todo.BitisTarihi else None,
                    'HatirlatmaTarihi': todo.HatirlatmaTarihi.strftime('%Y-%m-%d') if todo.HatirlatmaTarihi else None,
                    'AtananKullaniciID': todo.AtananKullaniciID,
                    'RandevuDefteriID': todo.RandevuDefteriID,
                    'MusteriAdi': todo.MusteriAdi,
                    'MusteriSoyadi': todo.MusteriSoyadi,
                    'Telefon': todo.MusteriTelefon,
                    'Email': todo.MusteriEmail
                }
            })
        
        data = request.get_json()
        old_data = {
            'baslik': todo.Baslik,
            'aciklama': todo.Aciklama,
            'oncelik': todo.Oncelik,
            'durum': todo.durum.DurumAdi if todo.durum else None,
            'bitis_tarihi': todo.BitisTarihi.isoformat() if todo.BitisTarihi else None,
            'hatirlatma_tarihi': todo.HatirlatmaTarihi.isoformat() if todo.HatirlatmaTarihi else None,
            'musteri_adi': todo.MusteriAdi,
            'musteri_soyadi': todo.MusteriSoyadi,
            'musteri_telefon': todo.MusteriTelefon,
            'musteri_email': todo.MusteriEmail
        }
        
        # Durum ID'sini al - durum adından ID'ye çevir
        durum_id = None
        if data.get('durum'):
            try:
                # Önce sayı olarak deneyelim
                durum_id = int(data['durum'])
            except (ValueError, TypeError):
                # Sayı değilse, durum adından ID bulalım
                try:
                    firma_id = session.get('firma_id')
                    if firma_id:
                        durum_obj = TodoDurum.query.filter_by(
                            FirmaID=firma_id,
                            DurumAdi=data['durum']
                        ).first()
                        if durum_obj:
                            durum_id = durum_obj.DurumID
                except Exception as e:
                    print(f"Durum arama hatası: {e}")
                    pass
        
        # Güncelle
        todo.Baslik = data['baslik']
        todo.Aciklama = data.get('aciklama', '')
        todo.Oncelik = data.get('oncelik', 'Orta')
        todo.DurumID = durum_id  # Yeni durum sistemi
        
        # Atanan kullanıcıyı güncelle
        if data.get('AtananKullaniciID'):
            todo.AtananKullaniciID = data['AtananKullaniciID']
        
        # Randevu defteri ID'sini güncelle
        if data.get('randevu_defteri_id'):
            todo.RandevuDefteriID = data['randevu_defteri_id']
        
        # Müşteri bilgilerini güncelle
        todo.MusteriAdi = data.get('musteri_adi', '')
        todo.MusteriSoyadi = data.get('musteri_soyadi', '')
        todo.MusteriTelefon = data.get('musteri_telefon', '')
        todo.MusteriEmail = data.get('musteri_email', '')
        
        # Tarih formatlarını parse et
        if data.get('bitis_tarihi'):
            todo.BitisTarihi = datetime.strptime(data['bitis_tarihi'], '%Y-%m-%d')
        else:
            todo.BitisTarihi = None
            
        if data.get('hatirlatma_tarihi'):
            todo.HatirlatmaTarihi = datetime.strptime(data['hatirlatma_tarihi'], '%Y-%m-%d')
        else:
            todo.HatirlatmaTarihi = None
        
        # Eğer durum "Tamamlandı" ise tamamlanma tarihini set et
        if todo.durum and todo.durum.DurumAdi == 'Tamamlandı' and not todo.TamamlanmaTarihi:
            todo.TamamlanmaTarihi = datetime.now()
        elif not todo.durum or todo.durum.DurumAdi != 'Tamamlandı':
            todo.TamamlanmaTarihi = None
        
        db.session.commit()
        
        # Log ekle
        try:
            log_user_action(
                action_type='Todo Güncellendi',
                table_name='Todos',
                record_id=todo_id,
                old_data=old_data,
                new_data=data,
                detail=f"Başlık: {data['baslik']}"
            )
        except Exception as log_error:
            print(f"Log hatası (önemli değil): {log_error}")
        
        return jsonify({'success': True, 'message': 'Todo başarıyla güncellendi!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/todos/<int:todo_id>/delete', methods=['DELETE'])
@login_required
def todo_delete(todo_id):
    """Todo sil"""
    try:
        todo = Todo.query.filter_by(TodoID=todo_id, KullaniciID=session['user_id']).first()
        if not todo:
            return jsonify({'success': False, 'message': 'Todo bulunamadı!'}), 404
        
        baslik = todo.Baslik
        
        # Önce bağlantılı randevuyu sil (eğer varsa)
        if todo.RandevuID:
            randevu = Randevu.query.filter_by(RandevuID=todo.RandevuID).first()
            if randevu:
                print(f"Bağlantılı randevu siliniyor: {randevu.RandevuID}")
                
                # Önce RandevuYetki kayıtlarını sil
                from app import RandevuYetki
                RandevuYetki.query.filter_by(RandevuID=randevu.RandevuID).delete()
                
                # GorevID'yi NULL yap (circular reference'ı kır)
                randevu.GorevID = None
                db.session.flush()
                
                # Randevu'yu sil
                db.session.delete(randevu)
        
        # Todo'yu sil
        db.session.delete(todo)
        db.session.commit()
        
        # Log ekle
        try:
            log_user_action(
                action_type='Todo Silindi',
                table_name='Todos',
                record_id=todo_id,
                old_data={'baslik': baslik, 'tip': todo.Tip},
                new_data=None,
                detail=f"Başlık: {baslik}"
            )
        except Exception as log_error:
            print(f"Log hatası (önemli değil): {log_error}")
        
        return jsonify({'success': True, 'message': 'Todo ve bağlantılı randevu başarıyla silindi!'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Todo silme hatası: {str(e)}")
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/todos/<int:todo_id>/durum', methods=['POST'])
@login_required
def todo_durum_degistir(todo_id):
    """Todo durumunu değiştir"""
    try:
        print(f"Todo durum değiştirme isteği: todo_id={todo_id}, user_id={session.get('user_id')}")
        
        todo = Todo.query.filter_by(TodoID=todo_id, KullaniciID=session['user_id']).first()
        if not todo:
            print(f"Todo bulunamadı: todo_id={todo_id}, user_id={session.get('user_id')}")
            return jsonify({'success': False, 'message': 'Todo bulunamadı!'}), 404
        
        data = request.get_json()
        print(f"Request data: {data}")
        yeni_durum_adi = data.get('durum')
        
        # Durum adından ID'yi bul
        yeni_durum_id = None
        if yeni_durum_adi:
            # Önce firmanın durumları içinde ara, yoksa genel kataloğa bak
            print(f"Firma ID: {session.get('firma_id')}")
            print(f"Aranan durum: {yeni_durum_adi}")
            
            durum = TodoDurum.query.filter_by(
                DurumAdi=yeni_durum_adi,
                FirmaID=session.get('firma_id'),
                Aktif=True
            ).first()
            if not durum:
                durum = TodoDurum.query.filter_by(DurumAdi=yeni_durum_adi, Aktif=True).first()
            if not durum:
                print(f"Geçersiz durum adı: {yeni_durum_adi}")
                return jsonify({'success': False, 'message': 'Geçersiz durum!'}), 400
            yeni_durum_id = durum.DurumID
            print(f"Bulunan durum: ID {durum.DurumID}, Ad: '{durum.DurumAdi}', Firma: {durum.FirmaID}")
        
        eski_durum = todo.durum.DurumAdi if todo.durum else 'Durum Yok'
        todo.DurumID = yeni_durum_id
        print(f"Durum değiştiriliyor: {eski_durum} -> {yeni_durum_id}")
        
        # Eğer durum "Tamamlandı" ise tamamlanma tarihini set et, KAYDI SİLME
        yeni_durum_adi = durum.DurumAdi if durum else None
        if yeni_durum_adi == 'Tamamlandı':
            if not todo.TamamlanmaTarihi:
                todo.TamamlanmaTarihi = datetime.now()
            
            # Bu todo ile ilgili bildirimleri sil
            deleted_notifications = Bildirim.query.filter(
                Bildirim.KullaniciID == todo.KullaniciID,
                Bildirim.Metin.contains(todo.Baslik),
                Bildirim.Tip == 'todo_reminder'
            ).delete(synchronize_session=False)
            print(f"Todo ile ilgili {deleted_notifications} bildirim silindi: {todo.Baslik}")
            
            # Kaydı silmeden değişiklikleri kaydet
            db.session.commit()
            print("Todo tamamlandı olarak işaretlendi (silinmedi)")
        else:
            todo.TamamlanmaTarihi = None
            db.session.commit()
            print("Todo durumu başarıyla güncellendi")
        
        # Log ekle
        if yeni_durum_adi == 'Tamamlandı':
            log_user_action(
                action_type='Todo Tamamlandı',
                table_name='Todos',
                record_id=todo_id,
                old_data={'durum': eski_durum},
                new_data={'durum': yeni_durum_adi, 'action': 'completed'},
                detail=f"Başlık: {todo.Baslik} - {eski_durum} → {yeni_durum_adi} (Silinmedi)"
            )
            return jsonify({'success': True, 'message': 'Görev tamamlandı olarak işaretlendi!'})
        else:
            log_user_action(
                action_type='Todo Durumu Değiştirildi',
                table_name='Todos',
                record_id=todo_id,
                old_data={'durum': eski_durum},
                new_data={'durum': yeni_durum_adi},
                detail=f"Başlık: {todo.Baslik} - {eski_durum} → {yeni_durum_adi}"
            )
            return jsonify({'success': True, 'message': f'Durum {yeni_durum_adi} olarak güncellendi!'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Todo durum değiştirme hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/api/gorev-raporlar')
@login_required
def api_gorev_raporlar():
    """Görev raporları API'si"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Kullanıcı bilgisi bulunamadı'}), 400
        
        # Filtre parametreleri
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        status_filter = request.args.get('status', 'all')
        user_filter = request.args.get('user', 'all')
        priority_filter = request.args.get('priority', 'all')
        type_filter = request.args.get('type', 'all')
        
        # Admin ise tüm görevleri, değilse sadece kendi görevlerini getir
        if session.get('is_admin', False):
            query = Todo.query
        else:
            query = Todo.query.filter_by(KullaniciID=user_id)
        
        # Tarih filtresi
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Son gün dahil
                query = query.filter(Todo.OlusturmaTarihi.between(start_dt, end_dt))
            except ValueError:
                pass
        
        # Durum filtresi
        if status_filter != 'all':
            query = query.filter(Todo.DurumID == status_filter)
        
        # Kullanıcı filtresi
        if user_filter != 'all':
            query = query.filter(Todo.KullaniciID == user_filter)
        
        # Öncelik filtresi
        if priority_filter != 'all':
            query = query.filter(Todo.Oncelik == priority_filter)
        
        # Tip filtresi
        if type_filter != 'all':
            query = query.filter(Todo.Tip == type_filter)
        
        gorevler = query.all()
        
        # İstatistikler
        total_tasks = len(gorevler)
        completed_tasks = len([g for g in gorevler if g.durum and g.durum.DurumAdi == 'Tamamlandı'])
        pending_tasks = len([g for g in gorevler if g.durum and g.durum.DurumAdi != 'Tamamlandı'])
        completion_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
        
        stats = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'pending_tasks': pending_tasks,
            'completion_rate': completion_rate
        }
        
        # Durum dağılımı (renkler TodoDurum.Renk değerlerinden)
        status_counts = {}
        status_colors_map = {}
        for gorev in gorevler:
            durum_adi = gorev.durum.DurumAdi if gorev.durum else 'Durum Yok'
            status_counts[durum_adi] = status_counts.get(durum_adi, 0) + 1
            if durum_adi not in status_colors_map:
                renk = (gorev.durum.Renk if gorev.durum and getattr(gorev.durum, 'Renk', None) else '#6c757d')
                status_colors_map[durum_adi] = renk
        # Listeleri aynı sırada üret
        status_labels = list(status_counts.keys())
        status_values = [status_counts[lbl] for lbl in status_labels]
        status_colors = [status_colors_map.get(lbl, '#6c757d') for lbl in status_labels]
        status_chart = {
            'labels': status_labels,
            'values': status_values,
            'colors': status_colors
        }
        
        # Öncelik dağılımı (sabit renkler)
        priority_counts = {}
        priority_colors_map = {
            'Yüksek': '#dc3545',    # Kırmızı
            'Orta': '#ffc107',      # Sarı
            'Düşük': '#28a745',     # Yeşil
            'Belirsiz': '#6c757d'   # Gri
        }
        for gorev in gorevler:
            priority = gorev.Oncelik or 'Belirsiz'
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        priority_labels = list(priority_counts.keys())
        priority_values = [priority_counts[lbl] for lbl in priority_labels]
        priority_colors = [priority_colors_map.get(lbl, '#6c757d') for lbl in priority_labels]
        
        priority_chart = {
            'labels': priority_labels,
            'values': priority_values,
            'colors': priority_colors
        }
        
        # Kullanıcı dağılımı
        user_counts = {}
        for gorev in gorevler:
            kullanici_adi = f"{gorev.kullanici.Ad} {gorev.kullanici.Soyad}" if gorev.kullanici else 'Bilinmeyen'
            user_counts[kullanici_adi] = user_counts.get(kullanici_adi, 0) + 1
        
        user_chart = {
            'labels': list(user_counts.keys()),
            'values': list(user_counts.values()),
            'colors': ['#007bff', '#28a745', '#ffc107', '#dc3545', '#6c757d', '#17a2b8', '#fd7e14', '#20c997']
        }
        
        # Kullanıcı tamamlanan görevler dağılımı
        user_completed_counts = {}
        for gorev in gorevler:
            if gorev.durum and gorev.durum.DurumAdi == 'Tamamlandı':
                kullanici_adi = f"{gorev.kullanici.Ad} {gorev.kullanici.Soyad}" if gorev.kullanici else 'Bilinmeyen'
                user_completed_counts[kullanici_adi] = user_completed_counts.get(kullanici_adi, 0) + 1
        
        user_completed_chart = {
            'labels': list(user_completed_counts.keys()),
            'values': list(user_completed_counts.values()),
            'colors': ['#28a745', '#007bff', '#ffc107', '#dc3545', '#6c757d', '#17a2b8', '#fd7e14', '#20c997']
        }
        
        # Aylık trend (son 12 ay)
        trend_data = {}
        for gorev in gorevler:
            month_key = gorev.OlusturmaTarihi.strftime('%Y-%m')
            if month_key not in trend_data:
                trend_data[month_key] = {'created': 0, 'completed': 0}
            trend_data[month_key]['created'] += 1
            
            if gorev.durum and gorev.durum.DurumAdi == 'Tamamlandı' and gorev.TamamlanmaTarihi:
                completed_month = gorev.TamamlanmaTarihi.strftime('%Y-%m')
                if completed_month not in trend_data:
                    trend_data[completed_month] = {'created': 0, 'completed': 0}
                trend_data[completed_month]['completed'] += 1
        
        # Son 12 ayı oluştur
        trend_labels = []
        trend_created = []
        trend_completed = []
        
        for i in range(12):
            date = datetime.now() - timedelta(days=30*i)
            month_key = date.strftime('%Y-%m')
            month_name = date.strftime('%b %Y')
            
            trend_labels.insert(0, month_name)
            trend_created.insert(0, trend_data.get(month_key, {}).get('created', 0))
            trend_completed.insert(0, trend_data.get(month_key, {}).get('completed', 0))
        
        trend_chart = {
            'labels': trend_labels,
            'created': trend_created,
            'completed': trend_completed
        }
        
        # Görev detayları
        tasks = []
        for gorev in gorevler:
            tasks.append({
                'baslik': gorev.Baslik,
                'durum': gorev.durum.DurumAdi if gorev.durum else 'Durum Yok',
                'durum_rengi': gorev.durum.Renk if gorev.durum and gorev.durum.Renk else '#6c757d',
                'oncelik': gorev.Oncelik or 'Belirsiz',
                'kullanici_adi': f"{gorev.kullanici.Ad} {gorev.kullanici.Soyad}" if gorev.kullanici else 'Bilinmeyen',
                'olusturma_tarihi': gorev.OlusturmaTarihi.isoformat() if gorev.OlusturmaTarihi else None,
                'bitis_tarihi': gorev.BitisTarihi.isoformat() if gorev.BitisTarihi else None,
                'musteri_adi': f"{gorev.MusteriAdi or ''} {gorev.MusteriSoyadi or ''}".strip() or None
            })
        
        return jsonify({
            'success': True,
            'stats': stats,
            'charts': {
                'status': status_chart,
                'priority': priority_chart,
                'user': user_chart,
                'user_completed': user_completed_chart,
                'trend': trend_chart
            },
            'tasks': tasks
        })
        
    except Exception as e:
        print(f"Görev raporları hatası: {e}")
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/api/gorev-bilgi/<int:gorev_id>', methods=['GET'])
@login_required
def gorev_bilgi(gorev_id):
    """Görev bilgilerini getir"""
    try:
        print(f"Görev bilgisi isteği: gorev_id={gorev_id}, user_id={session.get('user_id')}")
        
        # Görevi bul
        gorev = Todo.query.filter_by(TodoID=gorev_id, KullaniciID=session['user_id'], Tip='Randevu').first()
        print(f"Bulunan görev: {gorev}")
        
        if not gorev:
            return jsonify({'success': False, 'message': 'Görev bulunamadı!'}), 404
        
        # Durum bilgisini güvenli şekilde al
        durum_adi = None
        try:
            if gorev.durum:
                durum_adi = gorev.durum.DurumAdi
        except Exception as durum_error:
            print(f"Durum bilgisi alınırken hata: {durum_error}")
            durum_adi = None
        
        # Müşteri bilgilerini görevden al (yeni format)
        musteri_adi = gorev.MusteriAdi
        musteri_soyadi = gorev.MusteriSoyadi
        telefon = gorev.MusteriTelefon
        email = gorev.MusteriEmail
        
        # Eğer görevde müşteri bilgileri yoksa, eski formattan çıkar
        if not musteri_adi and gorev.Aciklama:
            # Açıklamadan müşteri adını çıkar
            if 'Müşteri:' in gorev.Aciklama:
                musteri_line = [line for line in gorev.Aciklama.split('\n') if 'Müşteri:' in line]
                if musteri_line:
                    musteri_full = musteri_line[0].split('Müşteri:')[1].strip()
                    ad_soyad = musteri_full.split(' ')
                    musteri_adi = ad_soyad[0] if len(ad_soyad) > 0 else None
                    musteri_soyadi = ' '.join(ad_soyad[1:]) if len(ad_soyad) > 1 else None
        
        # Eğer açıklamada müşteri adı yoksa, başlıktan çıkar
        if not musteri_adi and gorev.Baslik and 'Randevu:' in gorev.Baslik:
            baslik_parts = gorev.Baslik.split('Randevu:')[1]
            if baslik_parts:
                tarih_parts = baslik_parts.split(' - ')
                if len(tarih_parts) > 0:
                    musteri_full = tarih_parts[0].strip()
                    ad_soyad = musteri_full.split(' ')
                    musteri_adi = ad_soyad[0] if len(ad_soyad) > 0 else None
                    musteri_soyadi = ' '.join(ad_soyad[1:]) if len(ad_soyad) > 1 else None
        
        # Müşteri adı varsa ve telefon/email yoksa, müşteriler tablosundan al
        if musteri_adi and musteri_soyadi and (not telefon or not email):
            try:
                print(f"Müşteri aranıyor: {musteri_adi} {musteri_soyadi}, FirmaID: {session.get('firma_id')}")
                musteri = Musteri.query.filter_by(
                    MusteriAdi=musteri_adi,
                    MusteriSoyadi=musteri_soyadi,
                    FirmaID=session['firma_id']
                ).first()
                
                if musteri:
                    telefon = telefon or musteri.Telefon
                    email = email or musteri.Email
                    print(f"Müşteri bulundu: {musteri_adi} {musteri_soyadi}, Telefon: {telefon}, Email: {email}")
                else:
                    print(f"Müşteri bulunamadı: {musteri_adi} {musteri_soyadi}")
            except Exception as musteri_error:
                print(f"Müşteri arama hatası: {musteri_error}")
                import traceback
                traceback.print_exc()
        
        gorev_data = {
            'TodoID': gorev.TodoID,
            'Baslik': gorev.Baslik,
            'Aciklama': gorev.Aciklama,
            'Oncelik': gorev.Oncelik,
            'BitisTarihi': gorev.BitisTarihi.strftime('%Y-%m-%d') if gorev.BitisTarihi else None,
            'HatirlatmaTarihi': gorev.HatirlatmaTarihi.strftime('%Y-%m-%d') if gorev.HatirlatmaTarihi else None,
            'RandevuTarihi': None,  # Şimdilik None
            'RandevuSaati': None,  # Şimdilik None
            'Durum': durum_adi,
            'MusteriAdi': musteri_adi,
            'MusteriSoyadi': musteri_soyadi,
            'Telefon': telefon,
            'Email': email
        }
        
        print(f"Görev verisi: {gorev_data}")
        
        return jsonify({
            'success': True,
            'gorev': gorev_data
        })
        
    except Exception as e:
        print(f"Görev bilgisi API hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/api/randevu-defterleri', methods=['GET'])
@login_required
def api_randevu_defterleri():
    """Randevu defterlerini getir"""
    try:
        print(f"Randevu defterleri isteği: firma_id={session.get('firma_id')}")
        
        defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
        print(f"Bulunan defterler: {len(defterler)}")
        
        defter_listesi = []
        for d in defterler:
            defter_listesi.append({
                'AyarID': d.AyarID, 
                'DefterAdi': d.DefterAdi,
                'SlotDakika': d.SlotDakika
            })
        
        print(f"Defter listesi: {defter_listesi}")
        
        return jsonify({
            'success': True,
            'defterler': defter_listesi
        })
    except Exception as e:
        print(f"Randevu defterleri API hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/api/randevu-slotlari', methods=['GET'])
@login_required
def api_randevu_slotlari():
    """Randevu slotlarını getir"""
    try:
        tarih = request.args.get('tarih')
        defter_id = request.args.get('defter_id')
        
        if not tarih or not defter_id:
            return jsonify({'success': False, 'message': 'Tarih ve defter ID gerekli!'}), 400
        
        # Defter ayarlarını al
        defter_ayar = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=session['firma_id']).first()
        if not defter_ayar:
            return jsonify({'success': False, 'message': 'Defter bulunamadı!'}), 404
        
        # Mevcut randevuları kontrol et
        tarih_obj = datetime.strptime(tarih, '%Y-%m-%d').date()
        tarih_baslangic = datetime.combine(tarih_obj, datetime.min.time())
        tarih_bitis = datetime.combine(tarih_obj, datetime.max.time())
        
        existing_randevular = Randevu.query.filter(
            Randevu.RandevuTarihi >= tarih_baslangic,
            Randevu.RandevuTarihi <= tarih_bitis,
            Randevu.DefterID == defter_id,
            Randevu.FirmaID == session['firma_id']
        ).all()
        
        # Mevcut saatleri al
        occupied_slots = []
        for r in existing_randevular:
            if r.RandevuTarihi:
                # Saat bilgisini al
                saat_str = r.RandevuTarihi.strftime('%H:%M')
                occupied_slots.append(saat_str)
        
        print(f"Mevcut randevular: {len(existing_randevular)}")
        print(f"Dolu slotlar: {occupied_slots}")
        
        # Çalışma günlerini kontrol et
        calisma_gunleri = defter_ayar.CalismaGunleri or '1,2,3,4,5'  # Varsayılan: Pazartesi-Cuma
        calisma_gunleri_list = [int(g.strip()) for g in calisma_gunleri.split(',')]
        
        # Bugünün haftanın günü (1=Pazartesi, 7=Pazar)
        bugun_gun = tarih_obj.weekday() + 1  # Python'da 0=Pazartesi, bizim sistemde 1=Pazartesi
        
        if bugun_gun not in calisma_gunleri_list:
            print(f"Bugün çalışma günü değil: {bugun_gun}, Çalışma günleri: {calisma_gunleri_list}")
            return jsonify({
                'success': True,
                'slotlar': [],
                'mesaj': 'Bu gün çalışma günü değil!'
            })
        
        # Defter ayarlarından çalışma saatlerini ve slot süresini al
        baslangic_saati = defter_ayar.BaslangicSaati or '09:00'
        bitis_saati = defter_ayar.BitisSaati or '18:00'
        slot_dakika = defter_ayar.SlotDakika or 30
        
        # Başlangıç ve bitiş saatlerini parse et
        baslangic_hour, baslangic_minute = map(int, baslangic_saati.split(':'))
        bitis_hour, bitis_minute = map(int, bitis_saati.split(':'))
        
        # Tüm slotları oluştur (hem müsait hem dolu)
        all_slots = []
        available_slots = []
        current_hour = baslangic_hour
        current_minute = baslangic_minute
        
        while (current_hour < bitis_hour) or (current_hour == bitis_hour and current_minute < bitis_minute):
            slot = f"{current_hour:02d}:{current_minute:02d}"
            all_slots.append(slot)
            
            if slot not in occupied_slots:
                available_slots.append(slot)
            
            # Sonraki slot için dakika ekle
            current_minute += slot_dakika
            if current_minute >= 60:
                current_hour += 1
                current_minute -= 60
        
        print(f"Defter: {defter_ayar.DefterAdi}, Slot süresi: {slot_dakika} dk, Başlangıç: {baslangic_saati}, Bitiş: {bitis_saati}")
        print(f"Oluşturulan slotlar: {all_slots[:5]}...")  # İlk 5 slotu göster
        
        return jsonify({
            'success': True,
            'slotlar': available_slots,
            'dolu_slotlar': occupied_slots,
            'tum_slotlar': all_slots
        })
        
    except Exception as e:
        print(f"Slot oluşturma hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/api/gorev-to-randevu/<int:gorev_id>', methods=['POST'])
@login_required
def gorev_to_randevu(gorev_id):
    """Görevi randevu defterine taşı"""
    try:
        # Görevi bul
        gorev = Todo.query.filter_by(TodoID=gorev_id, KullaniciID=session['user_id'], Tip='Randevu').first()
        if not gorev:
            return jsonify({'success': False, 'message': 'Görev bulunamadı!'}), 404
        
        # Görev tipini 'Randevu' olarak değiştir (zaten Randevu ama emin olmak için)
        gorev.Tip = 'Randevu'
        
        # Randevu defteri için gerekli alanları ekle/güncelle
        if not gorev.RandevuTarihi:
            gorev.RandevuTarihi = gorev.BitisTarihi or datetime.now().date()
        
        if not gorev.RandevuSaati:
            gorev.RandevuSaati = '09:00'  # Varsayılan saat
        
        # Durumu 'Beklemede' yap
        beklemede_durum = TodoDurum.query.filter_by(DurumAdi='Beklemede', FirmaID=session['firma_id']).first()
        if beklemede_durum:
            gorev.DurumID = beklemede_durum.DurumID
        
        db.session.commit()
        
        # Log ekle
        try:
            log_user_action(
                action_type='Görev Randevu Defterine Taşındı',
                table_name='Todos',
                record_id=gorev_id,
                old_data={'tip': 'Randevu'},
                new_data={'tip': 'Randevu', 'randevu_tarihi': str(gorev.RandevuTarihi), 'randevu_saati': gorev.RandevuSaati},
                detail=f"Başlık: {gorev.Baslik} - Randevu Tarihi: {gorev.RandevuTarihi}"
            )
        except Exception as log_error:
            print(f"Log hatası (önemli değil): {log_error}")
        
        return jsonify({'success': True, 'message': 'Görev başarıyla randevu defterine taşındı!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/todos/<int:todo_id>/sil', methods=['DELETE'])
@login_required
def todo_sil(todo_id):
    """Todo sil"""
    try:
        todo = Todo.query.filter_by(TodoID=todo_id, KullaniciID=session['user_id']).first()
        if not todo:
            return jsonify({'success': False, 'message': 'Todo bulunamadı!'}), 404
        
        baslik = todo.Baslik
        
        # Önce bağlantılı randevuyu sil (eğer varsa)
        if todo.RandevuID:
            randevu = Randevu.query.filter_by(RandevuID=todo.RandevuID).first()
            if randevu:
                print(f"Bağlantılı randevu siliniyor: {randevu.RandevuID}")
                
                # Önce RandevuYetki kayıtlarını sil
                from app import RandevuYetki
                RandevuYetki.query.filter_by(RandevuID=randevu.RandevuID).delete()
                
                # GorevID'yi NULL yap (circular reference'ı kır)
                randevu.GorevID = None
                db.session.flush()
                
                # Randevu'yu sil
                db.session.delete(randevu)
        
        # Todo'yu sil
        db.session.delete(todo)
        db.session.commit()
        
        # Log ekle
        try:
            log_user_action(
                action_type='Todo Silindi',
                table_name='Todos',
                record_id=todo_id,
                old_data={'baslik': baslik, 'durum': todo.durum.DurumAdi if todo.durum else 'Durum Yok'},
                new_data=None,
                detail=f"Başlık: {baslik}"
            )
        except Exception as log_error:
            print(f"Log hatası (önemli değil): {log_error}")
        
        return jsonify({'success': True, 'message': 'Todo ve bağlantılı randevu başarıyla silindi!'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Todo silme hatası: {str(e)}")
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@app.route('/todos/api')
@login_required
def todos_api():
    """Todo verilerini API olarak döndür (dashboard için)"""
    try:
        # Kullanıcının todolarını getir
        todos = Todo.query.filter_by(KullaniciID=session['user_id']).all()
        
        result = []
        for todo in todos:
            result.append({
                'id': todo.TodoID,
                'baslik': todo.Baslik,
                'aciklama': todo.Aciklama,
                'oncelik': todo.Oncelik,
                'durum': todo.durum.DurumAdi if todo.durum else 'Durum Yok',
                'bitis_tarihi': todo.BitisTarihi.isoformat() if todo.BitisTarihi else None,
                'hatirlatma_tarihi': todo.HatirlatmaTarihi.isoformat() if todo.HatirlatmaTarihi else None,
                'olusturma_tarihi': todo.OlusturmaTarihi.isoformat(),
                'tamamlanma_tarihi': todo.TamamlanmaTarihi.isoformat() if todo.TamamlanmaTarihi else None
            })
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== TODO BİLDİRİM SİSTEMİ ====================

def check_todo_reminders():
    """Todo hatırlatmalarını kontrol et ve bildirim oluştur"""
    try:
        bugun = datetime.now().date()
        simdi = datetime.now()
        
        # Bugün hatırlatma tarihi olan todoları bul
        hatirlatma_todos = Todo.query.filter(
            Todo.HatirlatmaTarihi == bugun
        ).all()
        
        # Tamamlanmamış todoları filtrele
        hatirlatma_todos = [todo for todo in hatirlatma_todos if not todo.durum or todo.durum.DurumAdi != 'Tamamlandı']
        
        yeni_bildirim_sayisi = 0
        
        for todo in hatirlatma_todos:
            # Bu todo için bugün zaten bildirim oluşturulmuş mu kontrol et
            existing_notification = Bildirim.query.filter(
                Bildirim.KullaniciID == todo.KullaniciID,
                Bildirim.Metin.contains(todo.Baslik),
                Bildirim.Tip == 'todo_reminder',
                Bildirim.OlusturmaTarihi >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            ).first()
            
            if not existing_notification:
                # Yeni bildirim oluştur
                bildirim = Bildirim(
                    KullaniciID=todo.KullaniciID,
                    FirmaID=1,  # Varsayılan firma ID
                    Metin=f'[HATIRLATMA] "{todo.Baslik}" gorevinin hatirlatma tarihi bugun!',
                    Tip='todo_reminder',
                    Okundu=False
                )
                db.session.add(bildirim)
                yeni_bildirim_sayisi += 1
                print(f"Todo hatırlatma bildirimi oluşturuldu: {todo.Baslik} (Kullanıcı: {todo.KullaniciID})")
        
        db.session.commit()
        
        if yeni_bildirim_sayisi > 0:
            print(f"Todo hatırlatma kontrolü tamamlandı. {yeni_bildirim_sayisi} yeni bildirim oluşturuldu.")
        else:
            print(f"Todo hatırlatma kontrolü tamamlandı. {len(hatirlatma_todos)} todo kontrol edildi, yeni bildirim yok.")
        
    except Exception as e:
        print(f"Todo hatırlatma kontrolünde hata: {str(e)}")
        db.session.rollback()

def todo_reminder_worker():
    """Todo hatırlatma worker'ı - her 5 dakikada bir çalışır"""
    while True:
        try:
            now = datetime.now()
            # Her 5 dakikada bir kontrol et
            check_todo_reminders()
            
            # 5 dakika bekle
            time.sleep(300)
            
        except Exception as e:
            print(f"Todo reminder worker hatası: {str(e)}")
            time.sleep(300)

# Şifre Hatırlatma Route'ları
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        
        # Kullanıcı kontrolü
        user = Kullanici.query.filter_by(KullaniciAdi=username, Email=email, Aktif=True).first()
        
        if user:
            # Reset token oluştur
            reset_token = secrets.token_urlsafe(32)
            
            # Token'ı veritabanına kaydet (geçici olarak session'da saklayalım)
            session[f'reset_token_{user.KullaniciID}'] = {
                'token': reset_token,
                'expires': datetime.now() + timedelta(hours=1)  # 1 saat geçerli
            }
            
            # Reset link'i oluştur
            reset_link = url_for('reset_password', token=reset_token, _external=True)
            
            # Email gönderme simülasyonu (gerçek uygulamada email gönderilir)
            print(f"Password reset link for {user.KullaniciAdi}: {reset_link}")
            
            flash(_('Password reset link has been sent to your email address.'), 'success')
            return redirect(url_for('login'))
        else:
            flash(_('Invalid username or email address.'), 'error')
    
    return redirect(url_for('login'))

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        # Token kontrolü
        valid_token = False
        user_id = None
        
        for key, value in session.items():
            if key.startswith('reset_token_') and value.get('token') == token:
                if value.get('expires', datetime.min) > datetime.now():
                    valid_token = True
                    user_id = key.replace('reset_token_', '')
                    break
        
        if not valid_token:
            flash(_('Invalid or expired reset token.'), 'error')
            return redirect(url_for('login'))
        
        return render_template('reset_password.html', token=token)
    
    elif request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash(_('Passwords do not match.'), 'error')
            return render_template('reset_password.html', token=token)
        
        if len(new_password) < 6:
            flash(_('Password must be at least 6 characters long.'), 'error')
            return render_template('reset_password.html', token=token)
        
        # Token kontrolü
        valid_token = False
        user_id = None
        
        for key, value in session.items():
            if key.startswith('reset_token_') and value.get('token') == token:
                if value.get('expires', datetime.min) > datetime.now():
                    valid_token = True
                    user_id = key.replace('reset_token_', '')
                    break
        
        if not valid_token:
            flash(_('Invalid or expired reset token.'), 'error')
            return redirect(url_for('login'))
        
        # Şifreyi güncelle
        user = Kullanici.query.get(user_id)
        if user:
            user.Sifre = new_password
            user.GuncellemeTarihi = datetime.now()
            db.session.commit()
            
            # Token'ı temizle
            session.pop(f'reset_token_{user_id}', None)
            
            flash(_('Password has been reset successfully. You can now login with your new password.'), 'success')
            return redirect(url_for('login'))
        else:
            flash(_('User not found.'), 'error')
            return redirect(url_for('login'))

# Avatar resimleri için özel route - 404'ü önlemek için
@app.route('/avatar/<int:user_id>')
def serve_user_avatar(user_id):
    """Kullanıcı avatar resmini gönder, yoksa varsayılan avatar'ı gönder"""
    import os
    avatar_path = os.path.join('static', 'uploads', 'users', f'user_{user_id}.jpg')
    
    # Avatar dosyası var mı kontrol et
    if os.path.exists(avatar_path) and os.path.isfile(avatar_path):
        return send_file(avatar_path, mimetype='image/jpeg')
    else:
        # Varsayılan avatar'ı gönder
        default_avatar = os.path.join('static', 'img', 'avatar-default.svg')
        if os.path.exists(default_avatar):
            return send_file(default_avatar, mimetype='image/svg+xml')
        else:
            # Varsayılan avatar da yoksa 404 döndür
            from flask import abort
            abort(404)

# Production'da WSGI server kullanıldığında da çalışması için
def initialize_app():
    """Uygulamayı başlat - WSGI server'lar için"""
    with app.app_context():
        print("[LOAD] Veritabani tablolari olusturuluyor/kontrol ediliyor...")
        db.create_all()
        print("[OK] Tablo kontrolu tamamlandi.\n")
        
        # Veritabanı ayarlarını SistemAyarlar'dan yükle
        print("[INFO] SistemAyarlar'dan veritabani ayarlari yukleniyor...")
        initialize_database_from_settings()
        print("[OK] Veritabani ayarlari yukleme islemi tamamlandi.\n")
    
    # Hatirlatma worker'i arka planda baslat
    worker_thread = threading.Thread(target=reminder_worker, daemon=True)
    worker_thread.start()
    
    # Todo hatırlatma worker'ını başlat
    todo_worker_thread = threading.Thread(target=todo_reminder_worker, daemon=True)
    todo_worker_thread.start()
    
    return app

# Development server için
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("[START] Flask uygulamasi baslatiliyor (Development Mode)...")
    print("=" * 60 + "\n")
    
    initialize_app()
    
    # Development modunda debug=True
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.environ.get('FLASK_PORT', 5000)))
else:
    # WSGI server'lar için (Gunicorn, uWSGI, etc.)
    initialize_app()
