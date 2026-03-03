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
from flask_wtf.csrf import CSRFProtect, CSRFError
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
from urllib.parse import quote_plus, urlparse, parse_qs, urlencode, urlunparse
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
import warnings

load_dotenv()
default_secret_key = 'dev-secret-key-change-in-production'
secret_key = os.environ.get('SECRET_KEY', default_secret_key)

# Production ortamında varsayılan SECRET_KEY kullanılıyorsa uyar
if secret_key == default_secret_key and not os.environ.get('FLASK_DEBUG', '').lower() == 'true':
    warnings.warn(
        "SECURITY WARNING: SECRET_KEY için varsayılan değer kullanılıyor! "
        "Production ortamında güçlü bir SECRET_KEY tanımlayın.",
        UserWarning
    )

from app.utils.logging import log_user_action, log_user_action_decorator, get_record_info, start_logger
from app.utils.tasks import reminder_worker, todo_reminder_worker
from app.utils.helpers import get_client_ip, format_ip_for_display
from app.extensions import db, csrf, babel
from app.models import SistemAyar

app = Flask(__name__, 
            template_folder='app/templates',
            static_folder='app/static')
app.config['SECRET_KEY'] = secret_key
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['LANGUAGES'] = ['tr', 'en', 'fr', 'de']
app.config['BABEL_TRANSLATION_DIRECTORIES'] = os.path.join(app.root_path, 'translations')

# Initialize extensions
# Initialize extensions
db.init_app(app)
csrf.init_app(app)

def get_locale():
    # Session varsa ve language set edilmişse onu kullan
    if session and session.get('language'):
        lang = session.get('language')
        print(f"[LOCALE DEBUG] Session language: {lang}")
        return lang
    # Yoksa request'ten en iyi eşleşmeyi bul
    best_match = request.accept_languages.best_match(['tr', 'en', 'de', 'fr'])
    print(f"[LOCALE DEBUG] Best match: {best_match}")
    return best_match

babel.init_app(app, locale_selector=get_locale)

# Blueprint'leri kaydet
from app.routes.auth import auth_bp
from app.routes.main import main_bp
from app.routes.settings import settings_bp
from app.routes.api import api_bp
from app.routes.randevu import randevu_bp
from app.routes.gorev import gorev_bp
from app.routes.musteri import musteri_bp
from app.routes.rapor import rapor_bp
from app.routes.kullanici_mesaj import kullanici_mesaj_bp

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(api_bp)
app.register_blueprint(randevu_bp)
app.register_blueprint(gorev_bp)
app.register_blueprint(musteri_bp)
app.register_blueprint(rapor_bp)
app.register_blueprint(kullanici_mesaj_bp)

from app.routes.instagram import instagram_bp
app.register_blueprint(instagram_bp)

from app.routes.ai import ai_bp
app.register_blueprint(ai_bp)

# Context processor - datetime'ı tüm şablonlarda kullanılabilir yap
@app.context_processor
def inject_datetime():
    from datetime import timedelta
    return {'datetime': datetime, 'timedelta': timedelta}


# CSRF token'ı JSON istekler için header'dan da oku
# Flask-WTF varsayılan olarak X-CSRFToken header'ını destekler

# CSRF error handler - JSON API endpoint'leri için JSON döndür
@app.errorhandler(CSRFError)
def csrf_error(e):
    """CSRF hatası durumunda JSON döndür (API endpoint'leri için)"""
    # Eğer JSON isteği ise veya Accept header'ı JSON içeriyorsa JSON döndür
    if request.is_json or 'application/json' in request.headers.get('Accept', ''):
        return jsonify({'success': False, 'error': f'CSRF validation failed: {e.description}'}), 400
    # Aksi halde basit mesaj döndür
    return jsonify({'success': False, 'error': f'CSRF validation failed: {e.description}'}), 400

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

# Veritabanı bağlantısı SistemAyarlar tablosundan alınacak
# .env dosyasında DATABASE_URL varsa sadece ilk başlangıç için kullanılır (SistemAyarlar tablosuna erişmek için)
# SistemAyarlar tablosundan okunan ayarlar önceliklidir
_db_uri = os.environ.get('DATABASE_URL')
if not _db_uri:
    # DATABASE_URL yoksa, SistemAyarlar tablosuna erişmek için varsayılan bir bağlantı gerekli
    # İlk kurulum için varsayılan MySQL bağlantısı kullanılabilir
    # Ancak bu durumda SistemAyarlar tablosuna erişmek için bağlantı bilgileri gerekli
    print("[INFO] DATABASE_URL .env dosyasinda bulunamadi.")
    print("[INFO] Veritabani bilgileri SistemAyarlar tablosundan alinacak.")
    print("[WARN] İlk kurulum için SistemAyarlar tablosuna erismek gerekiyor.")
    print("[WARN] SistemAyarlar tablosuna erismek icin gecici bir baglanti kullanilacak.")
    # Geçici olarak None kullan - initialize_database_from_settings() fonksiyonu bağlantıyı kuracak
    # Ancak SQLAlchemy için geçici bir URI gerekli, bu yüzden varsayılan bir değer kullan
    # SistemAyarlar tablosu MySQL veya MSSQL'de
    # En iyi çözüm: SistemAyarlar tablosuna erişmek için önce bir bağlantı kurmaya çalış
    # Ama şimdilik geçici bir URI kullan (initialize_database_from_settings() gerçek bağlantıyı kuracak)
    _db_uri = None  # None olarak bırak, initialize_database_from_settings() gerçek bağlantıyı kuracak

# MySQL URI'lerinden TrustServerCertificate parametresini temizle (MySQL için geçerli değil)
# _db_uri None olabilir (SistemAyarlar'dan okunacak)
if _db_uri and 'mysql' in _db_uri.lower():
    original_uri = _db_uri
    try:
        # URL'i parse et
        parsed = urlparse(_db_uri)
        # Query parametrelerini parse et
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        
        # TrustServerCertificate parametresini kaldır (case-insensitive)
        keys_to_remove = [k for k in query_params.keys() if k.lower() == 'trustservercertificate']
        if keys_to_remove:
            print(f"[INFO] MySQL URI'den TrustServerCertificate parametresi kaldiriliyor...")
            for key in keys_to_remove:
                del query_params[key]
        
        # Yeni query string oluştur
        new_query = urlencode(query_params, doseq=True)
        
        # Yeni URL'i oluştur
        new_parsed = parsed._replace(query=new_query)
        _db_uri = urlunparse(new_parsed)
        
        if original_uri != _db_uri:
            print(f"[OK] MySQL URI temizlendi: TrustServerCertificate parametresi kaldirildi")
    except Exception as e:
        # Parse hatası olursa, regex ile dene
        print(f"[WARN] URL parse hatası, regex ile temizleme deneniyor: {e}")
        _db_uri = re.sub(r'[&?]TrustServerCertificate=[^&]*', '', _db_uri, flags=re.IGNORECASE)
        _db_uri = re.sub(r'\?&', '?', _db_uri)
        if _db_uri.endswith('?'):
            _db_uri = _db_uri[:-1]

# TrustServerCertificate parametresini ekle (sadece MSSQL için)
if _db_uri and 'mssql' in _db_uri.lower() and 'TrustServerCertificate' not in _db_uri and 'trustservercertificate' not in _db_uri.lower():
    separator = '&' if '?' in _db_uri else '?'
    _db_uri = f"{_db_uri}{separator}TrustServerCertificate=yes"
# _db_uri None ise, SistemAyarlar'dan okunacak (initialize_database_from_settings() tarafından)
# İlk kurulum için veritabanına bağlanacak varsayılan fallback
if _db_uri is None:
    # Kullanıcının ayarlardan UI aracılığıyla .env dosyasını geçersiz kılması durumu için
    # Sırayla her iki database engine uri'ni de SistemAyarlar okumak için default fallback olarak atıyoruz.
    # initialize_database_from_settings() bu fallback'leri deneyip doğru database_type'a karar verecek
    _db_uri = 'mysql+pymysql://root:Sa19977991@localhost:3306/crandyx_crm_db?charset=utf8mb4'
    print("[INFO] Ilk kurulum icin MySQL baglantisi kullaniliyor (SistemAyarlar tablosuna erismek icin).")

app.config['SQLALCHEMY_DATABASE_URI'] = _db_uri
# Debug: MySQL URI'lerinde TrustServerCertificate olmamalı
if _db_uri and 'mysql' in _db_uri.lower() and ('TrustServerCertificate' in _db_uri or 'trustservercertificate' in _db_uri.lower()):
    print(f"[ERROR] MySQL URI'de hala TrustServerCertificate var! URI: {_db_uri[:100]}...")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# MySQL için connect_args'da TrustServerCertificate parametresini filtrele
engine_options = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 10,
    'max_overflow': 20,
    'pool_timeout': 60,
}
# MySQL için connect_args'ı ayarla - TrustServerCertificate parametresini filtrele
if _db_uri and 'mysql' in _db_uri.lower():
    # MySQL için connect_args'da TrustServerCertificate'ı filtrele
    # SQLAlchemy, query parametrelerini connect_args olarak geçirir
    # Bu yüzden connect_args'ı boş bırakarak query parametrelerinin geçirilmesini engelleyemeyiz
    # Ancak, SQLAlchemy'nin MySQL dialect'i query parametrelerini doğrudan pymysql.connect()'e geçirir
    # Bu yüzden URI'den temizlemek yeterli olmalı
    pass

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options

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
        # Eğer mevcut engine MSSQL ise ve bağlantı başarısız olursa, varsayılan DB stringlerine fallback at
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()
            if debug:
                print(f"   [INFO] Mevcut tablolar: {', '.join(table_names)}")
            if 'SistemAyarlar' not in table_names and 'sistemayarlar' not in [t.lower() for t in table_names]:
                if debug:
                    print("   [WARN] SistemAyarlar tablosu bulunamadi!")
                return None
        except Exception as inspect_err:
            if debug:
                print(f"   [WARN] Tablo kontrolu sirasinda hata (inspect): {inspect_err}")
                print(f"   [INFO] Standart fallback zinciri uygulanacak...")
        
        # SistemAyarlar tablosuna erişim - mevcut engine başarısız olursa default bağlantılarla doğrudan oku
        db_type_setting = None
        fallback_engine_used = None
        
        try:
            db_type_setting = SistemAyar.query.filter_by(AyarAdi='database_type').first()
        except Exception as query_err:
            if debug:
                print(f"   [WARN] ORM sorgusu basarisiz: {query_err}")
                print(f"   [INFO] Dogrudan SQL sorgusu ile varsayilan baglantilar deneniyor...")
            # Doğrudan SQL ile oku
            default_urllist = [
                'mssql+pyodbc://sa:YourPassword@localhost/Crandyx_CRM_DB?driver=ODBC+Driver+17+for+SQL+Server',
                'mysql+pymysql://root:Sa19977991@localhost:3306/crandyx_crm_db?charset=utf8mb4'
            ]
            
            for d_uri in default_urllist:
                try:
                    connect_args = {'connect_timeout': 3} if 'mysql' in d_uri else {}
                    temp_engine = create_engine(d_uri, connect_args=connect_args)
                    with temp_engine.connect() as conn:
                        result = conn.execute(text("SELECT AyarDegeri FROM sistemayarlar WHERE AyarAdi = 'database_type'"))
                        row = result.fetchone()
                        if row:
                            class SettingProxy:
                                def __init__(self, value):
                                    self.AyarDegeri = value
                            db_type_setting = SettingProxy(row[0])
                            fallback_engine_used = temp_engine
                            if debug:
                                print(f"   [OK] database_type SQL ile ({d_uri.split('://')[0]}) uzerinden okundu: {row[0]}")
                            break
                except Exception as iter_err:
                    if debug:
                        print(f"   [WARN] {d_uri.split('://')[0]} ile okuma basarisiz: {iter_err}")
        
        if debug:
            print(f"   database_type ayarı: {db_type_setting.AyarDegeri if db_type_setting else 'BULUNAMADI'}")
        if not db_type_setting or not db_type_setting.AyarDegeri:
            if debug:
                print("   [WARN] database_type ayari bulunamadi veya bos!")
                # Tüm SistemAyarlar kayıtlarını listele (debug için)
                try:
                    all_settings = SistemAyar.query.all()
                    print(f"   [INFO] SistemAyarlar'da toplam {len(all_settings)} kayit var:")
                    for setting in all_settings:
                        value = setting.AyarDegeri[:50] if setting.AyarDegeri and len(setting.AyarDegeri) > 50 else (setting.AyarDegeri or 'NULL')
                        print(f"      - {setting.AyarAdi} = {value}")
                except Exception as list_err:
                    if debug:
                        print(f"   [WARN] SistemAyarlar listesi okunamadi: {list_err}")
            return None
        
        db_type = db_type_setting.AyarDegeri.strip().lower()
        if debug:
            print(f"   [INFO] Veritabani tipi: {db_type}")
        
        # Eğer ORM tablosunda değilsek, dictionary fallback ile değerleri okuyalım
        fallback_settings = {}
        if fallback_engine_used:
            try:
                with fallback_engine_used.connect() as conn:
                    result = conn.execute(text("SELECT AyarAdi, AyarDegeri FROM sistemayarlar WHERE AyarAdi LIKE 'database_%'"))
                    settings_rows = result.fetchall()
                    if settings_rows:
                        fallback_settings = {row[0]: row[1] for row in settings_rows}
            except Exception as e:
                if debug:
                    print(f"   [WARN] SQL fallback okuma basarisiz: {e}")

        def get_setting(key):
            if fallback_engine_used:
                val = fallback_settings.get(key)
                class SettingProxy:
                    def __init__(self, value):
                        self.AyarDegeri = value
                return SettingProxy(val) if val is not None else None
            else:
                try:
                    return SistemAyar.query.filter_by(AyarAdi=key).first()
                except:
                    return None
                    
        if db_type == 'mysql':
            # MySQL ayarlarını al
            server_setting = get_setting('database_mysql_host')
            port_setting = get_setting('database_mysql_port')
            database_setting = get_setting('database_mysql_database')
            username_setting = get_setting('database_mysql_username')
            password_setting = get_setting('database_mysql_password')
            
            if not all([server_setting, database_setting, username_setting]):
                if debug:
                    print(f"   [WARN] Eksik MySQL ayarlari: server={bool(server_setting)}, database={bool(database_setting)}, username={bool(username_setting)}")
                return None
            
            server = server_setting.AyarDegeri or 'localhost'
            port = int(port_setting.AyarDegeri) if port_setting and port_setting.AyarDegeri else 3306
            database = database_setting.AyarDegeri
            username = username_setting.AyarDegeri
            password_encrypted = password_setting.AyarDegeri if password_setting else ''
            password = decrypt_password(password_encrypted)  # Şifreyi deşifrele
            charset_setting = get_setting('database_mysql_charset')
            charset = charset_setting.AyarDegeri if charset_setting and charset_setting.AyarDegeri else 'utf8mb4'
            
            mysql_uri = build_mysql_uri(server, database, username, password, port, charset)
            # MySQL URI'den TrustServerCertificate parametresini temizle (güvenlik için)
            if 'TrustServerCertificate' in mysql_uri or 'trustservercertificate' in mysql_uri.lower():
                try:
                    parsed = urlparse(mysql_uri)
                    query_params = parse_qs(parsed.query, keep_blank_values=True)
                    keys_to_remove = [k for k in query_params.keys() if k.lower() == 'trustservercertificate']
                    for key in keys_to_remove:
                        del query_params[key]
                    new_query = urlencode(query_params, doseq=True)
                    new_parsed = parsed._replace(query=new_query)
                    mysql_uri = urlunparse(new_parsed)
                except Exception:
                    pass  # Hata olursa orijinal URI'yi kullan
            return mysql_uri
        
        elif db_type == 'mssql':
            # MSSQL ayarlarını al
            server_setting = get_setting('database_mssql_server')
            port_setting = get_setting('database_mssql_port')
            database_setting = get_setting('database_mssql_database')
            username_setting = get_setting('database_mssql_username')
            password_setting = get_setting('database_mssql_password')
            driver_setting = get_setting('database_mssql_driver')
            
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

def initialize_database_from_settings():
    """SistemAyarlar tablosundan veritabanı ayarlarını oku ve bağlantıyı güncelle"""
    print("=" * 60)
    print("[INIT] Veritabani bilgileri SistemAyarlar tablosundan okunuyor...")
    print("=" * 60)
    
    # İlk olarak SistemAyarlar tablosunun var olduğundan emin ol
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()
        
        if 'SistemAyarlar' not in table_names and 'sistemayarlar' not in [t.lower() for t in table_names]:
            print("[WARN] SistemAyarlar tablosu bulunamadi, olusturuluyor...")
            db.create_all()
            print("[OK] SistemAyarlar tablosu olusturuldu.")
    except Exception as e:
        print(f"[WARN] Tablo kontrolu yapilamadi: {e}")
    
    # SistemAyarlar'dan URI oku
    print("[CHECK] SistemAyarlar'dan veritabani ayarlari okunmaya baslaniyor...")
    new_uri = get_database_uri_from_settings(debug=True)
    
    if new_uri:
        print(f"[INFO] Veritabani ayarlari SistemAyarlar'dan yuklendi: {new_uri[:50]}...")
        
        # Eski engine'i kapat
        try:
            db.engine.dispose()
            print("[UPDATE] Eski veritabani baglantisi kapatildi.")
        except Exception as e:
            print(f"[WARN] Engine dispose hatasi: {e}")
        
        # Yeni engine oluştur
        try:
            # Flask-SQLAlchemy için app config'i güncelle
            app.config['SQLALCHEMY_DATABASE_URI'] = new_uri
            
            # Yeni engine oluştur
            new_engine = create_engine(
                new_uri,
                pool_pre_ping=True,
                pool_recycle=300
            )
            
            # Flask-SQLAlchemy'nin engine'ini güncelle
            db.engine = new_engine
            
            # Session registry'yi güncelle
            db.session.remove()
            db.session.configure(bind=new_engine)
            
            # Metadata'yı güncelle
            db.metadata.bind = new_engine
            
            print("[OK] Veritabani baglantisi SistemAyarlar'dan guncellendi.")
            print(f"   [LINK] Yeni URI: {new_uri[:50]}...")
            print(f"   [OK] SQLAlchemy engine, session registry ve metadata guncellendi.")
            
            # Bağlantıyı test et
            with new_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[OK] Veritabani baglantisi basariyla test edildi!")
            
            print("=" * 60)
            print("[OK] initialize_database_from_settings() tamamlandi!")
            print("=" * 60)
            print()
            
            return new_engine
            
        except Exception as e:
            print(f"[ERROR] Yeni engine olusturma hatasi: {e}")
            import traceback
            traceback.print_exc()
            return None
    else:
        print("[WARN] SistemAyarlar'dan URI alinamadi, varsayilan baglanti kullaniliyor.")
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
            db_type_setting = None
            try:
                db_type_setting = SistemAyar.query.filter_by(AyarAdi='database_type').first()
            except Exception as e:
                # ORM fail olduysa raw DB bağlantısıyla config tablosunu oku
                default_urllist = [
                    'mssql+pyodbc://sa:YourPassword@localhost/Crandyx_CRM_DB?driver=ODBC+Driver+17+for+SQL+Server',
                    'mysql+pymysql://root:Sa19977991@localhost:3306/crandyx_crm_db?charset=utf8mb4'
                ]
                for d_uri in default_urllist:
                    try:
                        connect_args = {'connect_timeout': 3} if 'mysql' in d_uri else {}
                        temp_engine = create_engine(d_uri, connect_args=connect_args)
                        with temp_engine.connect() as conn:
                            result = conn.execute(text("SELECT AyarDegeri FROM sistemayarlar WHERE AyarAdi = 'database_type'"))
                            row = result.fetchone()
                            if row:
                                class SettingProxy:
                                    def __init__(self, value):
                                        self.AyarDegeri = value
                                db_type_setting = SettingProxy(row[0])
                                break
                    except:
                        pass
                        
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
    """Uygulama başlangıcında SistemAyarlar'dan veritabanı bağlantısını yükle
    
    Bu fonksiyon SistemAyarlar tablosundan veritabanı bilgilerini okur ve bağlantıyı kurar.
    SistemAyarlar tablosunda veritabanı ayarları yoksa, mevcut bağlantıyı kullanmaya devam eder.
    """
    global _app_initialized
    
    if _app_initialized:
        return  # Zaten başlatıldı
    
    print("=" * 60)
    print("[INIT] Veritabani bilgileri SistemAyarlar tablosundan okunuyor...")
    print("=" * 60)
    try:
        with app.app_context():
            # Önce SistemAyarlar tablosunun var olup olmadığını kontrol et ve oluştur
            try:
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                
                # SistemAyarlar tablosu yoksa oluştur
                if 'SistemAyarlar' not in inspector.get_table_names():
                    # SistemAyarlar tablosunu oluşturmaya çalış
                    # Bu durumda SistemAyarlar tablosu zaten başka bir veritabanında olabilir
                    try:
                        # Sadece SistemAyarlar modelini kullanarak tablo oluştur
                        # SistemAyar modeli app.py dosyasında tanımlı
                        SistemAyar.__table__.create(bind=db.engine, checkfirst=True)
                        print("[OK] SistemAyarlar tablosu olusturuldu.")
                    except Exception as create_err:
                        print(f"[WARN] SistemAyarlar tablosu olusturulamadi: {create_err}")
                        print("[INFO] SistemAyarlar tablosu zaten baska bir veritabaninda olabilir.")
                        # Devam et, SistemAyarlar'dan okumayı dene
            except Exception as e:
                print(f"[WARN] SistemAyarlar tablosu kontrol edilemedi: {e}")
                import traceback
                traceback.print_exc()
                # Hata olsa bile devam et - belki SistemAyarlar tablosu farklı bir veritabanında
                print("[INFO] SistemAyarlar tablosuna erisilemedi, mevcut baglanti kullanilmaya devam edilecek.")
                _app_initialized = True
                return
            
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
                    # MySQL için connect_args'da TrustServerCertificate'ı filtrele
                    engine_kwargs = {
                        'pool_pre_ping': True,
                        'pool_recycle': 300
                    }
                    # MySQL için connect_args'ı ayarla - query parametrelerini filtrelemek için
                    # SQLAlchemy, query parametrelerini connect_args olarak geçirir
                    # Boş connect_args dict'i, query parametrelerinin geçirilmesini engellemez
                    # Bu yüzden URI'den temizlemek yeterli olmalı (zaten yukarıda yapıldı)
                    new_engine = create_engine(
                        db_uri_from_settings,
                        **engine_kwargs
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
                    print("[INFO] SistemAyarlar'da veritabani ayari yok.")
                    print("[INFO] Mevcut baglanti kullanilmaya devam edilecek.")
                    # SistemAyarlar'da ayar yoksa, mevcut bağlantıyı kullanmaya devam et
                    _app_initialized = True
                    return
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

# Asenkron loglama sistemi app/utils/logging.py içinde yönetiliyor
# start_logger(app) çağrısı __init__.py içinde yapılıyor

# IP adresi alma yardımcı fonksiyonu


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
        allowed = set(['sifre_degistir', 'logout', 'set_language', 'static', 'auth.sifre_degistir', 'auth.logout'])
        if request.endpoint not in allowed:
            return redirect(url_for('auth.sifre_degistir'))

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
    WhatsAppModulu = db.Column(db.Boolean, default=False) # WhatsApp modülüne erişim
    ProfilFotografi = db.Column(db.NVARCHAR(500))  # Profil fotoğrafı dosya yolu
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
    TestNumarasi = db.Column(db.String(20), nullable=True)  # Test için kayıtlı numara
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

# Instagram Ayarları
class FirmaInstagramAyar(db.Model):
    __tablename__ = 'FirmaInstagramAyarlari'
    
    InstagramAyarID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    FacebookPageID = db.Column(db.String(50), nullable=True)
    InstagramBusinessAccountID = db.Column(db.String(50), nullable=True)
    AccessToken = db.Column(db.Text, nullable=True)
    WebhookSecret = db.Column(db.String(100), nullable=True)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='instagram_ayarlar')
    
    def __repr__(self):
        return f'<FirmaInstagramAyar {self.InstagramAyarID} firma={self.FirmaID}>'

# WhatsApp Mesajları
class WhatsAppMesaj(db.Model):
    __tablename__ = 'WhatsAppMesajlar'
    
    MesajID = db.Column(db.Integer, primary_key=True)
    WhatsAppMessageID = db.Column(db.String(100), unique=True, nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    MusteriID = db.Column(db.Integer, db.ForeignKey('Musteriler.MusteriID'), nullable=True)
    GonderenTelefon = db.Column(db.String(20), nullable=False)
    AliciTelefon = db.Column(db.String(20), nullable=False)
    MesajMetni = db.Column(db.Text)
    Yyon = db.Column(db.String(10), nullable=False)  # 'GELEN' veya 'GIDEN'
    Okundu = db.Column(db.Boolean, default=False, nullable=False)
    Tarih = db.Column(db.DateTime, default=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='whatsapp_mesajlar')
    musteri = db.relationship('Musteri', backref='whatsapp_mesajlar')
    
    def __repr__(self):
        return f'<WhatsAppMesaj {self.MesajID}>'

# Instagram Mesajları (app.py'de tekrar tanımlama - badge için)
class InstagramMesaj(db.Model):
    __tablename__ = 'InstagramMesajlar'
    
    MesajID = db.Column(db.Integer, primary_key=True)
    InstagramMessageID = db.Column(db.String(100), unique=True, nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    MusteriID = db.Column(db.Integer, db.ForeignKey('Musteriler.MusteriID'), nullable=True)
    GonderenID = db.Column(db.String(50), nullable=False)
    AliciID = db.Column(db.String(50), nullable=False)
    MesajMetni = db.Column(db.Text)
    Yyon = db.Column(db.String(10), nullable=False)  # 'GELEN' veya 'GIDEN'
    Okundu = db.Column(db.Boolean, default=False, nullable=False)
    Tarih = db.Column(db.DateTime, default=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='instagram_mesajlar_app')
    musteri = db.relationship('Musteri', backref='instagram_mesajlar')
    
    def __repr__(self):
        return f'<InstagramMesaj {self.MesajID}>'

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

# GeoNames API entegrasyonu
import requests
import json

# GeoNames API Base URL
GEONAMES_API_BASE = "http://api.geonames.org"

# GeoNames Username (ücretsiz tier için)
GEONAMES_USERNAME = os.environ.get("GEONAMES_USERNAME", "blueblack")  # GeoNames username

# Eski CountryStateCity API desteği (fallback için)
CSC_API_BASE = "https://api.countrystatecity.in/v1"
CSC_API_KEY = os.environ.get("CSC_API_KEY", "")

def _csc_headers():
    """CountryStateCity API için header üretir (fallback için)."""
    key = (CSC_API_KEY or "").strip().replace(" ", "")
    return {"X-CSCAPI-KEY": key}

def get_countries():
    """Tüm ülkeleri getir - GeoNames API kullanır, seçilen dile göre"""
    if not GEONAMES_USERNAME or not GEONAMES_USERNAME.strip():
        print(f"[GeoNames] Username yok, fallback kullanılıyor (ülkeler için)")
        return get_fallback_countries()
    
    # Session'dan dil bilgisini al
    lang = 'tr'  # Varsayılan
    try:
        from flask import session, has_request_context
        if has_request_context() and session and session.get('language'):
            lang = session.get('language', 'tr')[:2]  # İlk 2 karakteri al (tr, en, fr, de)
            print(f"[GeoNames] get_countries: Session'dan dil alındı: {lang}")
        else:
            print(f"[GeoNames] get_countries: Session yok veya request context yok, varsayılan dil kullanılıyor: {lang}")
    except Exception as e:
        print(f"[GeoNames] get_countries: Session dil hatası: {e}, varsayılan dil kullanılıyor: {lang}")
    
    try:
        url = f"{GEONAMES_API_BASE}/countryInfoJSON"
        params = {
            "username": GEONAMES_USERNAME,
            "lang": lang  # GeoNames dil parametresi
        }
        response = requests.get(url, params=params, timeout=10)
        print(f"[GeoNames] GET {url} (lang={lang}) -> {response.status_code}")
        print(f"[GeoNames] Params: {params}")
        if response.status_code == 200:
            data = response.json()
            print(f"[GeoNames] Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            countries = data.get("geonames", [])
            print(f"[GeoNames] Countries count: {len(countries) if countries else 0}")
            if countries and len(countries) > 0:
                print(f"[GeoNames] First country sample: {countries[0]}")
            # Eğer API boş array döndürüyorsa fallback kullan
            if not countries or len(countries) == 0:
                print(f"[GeoNames] API boş array döndürdü (ülkeler), fallback kullanılıyor")
                print(f"[GeoNames] Response body: {response.text[:500]}")
                return get_fallback_countries()
            # GeoNames formatını bizim formatımıza çevir
            try:
                formatted_countries = []
                skipped_count = 0
                for country in countries:
                    iso2 = country.get("isoAlpha2") or country.get("countryCode", "")
                    name = country.get("countryName", "")
                    if iso2 and name:
                        formatted_countries.append({"iso2": iso2, "name": name})
                    else:
                        skipped_count += 1
                        if skipped_count <= 5:  # İlk 5 atlanan ülkeyi logla
                            print(f"[GeoNames] Country skipped (missing data): iso2={iso2}, name={name}, country={country}")
                
                if skipped_count > 0:
                    print(f"[GeoNames] Toplam {skipped_count} ülke atlandı (iso2 veya name eksik)")
                
                print(f"[GeoNames] API'den {len(formatted_countries)} ülke formatlandı (lang={lang})")
                if len(formatted_countries) > 0:
                    print(f"[GeoNames] First formatted country: {formatted_countries[0]}")
                    print(f"[GeoNames] Last formatted country: {formatted_countries[-1]}")
                    # Türkçe kontrolü için bazı ülkeleri logla
                    test_countries = ['TR', 'US', 'DE', 'FR', 'GB', 'PL']
                    for test_iso2 in test_countries:
                        test_country = next((c for c in formatted_countries if c.get('iso2') == test_iso2), None)
                        if test_country:
                            print(f"[GeoNames] {test_iso2}: {test_country.get('name')}")
                        else:
                            print(f"[GeoNames] {test_iso2}: Bulunamadı")
                    # Türkçe kontrolü için bazı ülkeleri logla
                    test_countries = ['TR', 'US', 'DE', 'FR', 'GB', 'PL']
                    for test_iso2 in test_countries:
                        test_country = next((c for c in formatted_countries if c.get('iso2') == test_iso2), None)
                        if test_country:
                            print(f"[GeoNames] {test_iso2}: {test_country.get('name')}")
                
                # Eğer formatlanmış ülke yoksa fallback kullan
                if len(formatted_countries) == 0:
                    print(f"[GeoNames] API'den formatlanmış ülke yok, fallback kullanılıyor")
                    return get_fallback_countries()
                
                print(f"[GeoNames] Returning {len(formatted_countries)} countries from API")
                return formatted_countries
            except Exception as e:
                print(f"[GeoNames] API veri formatlama hatası (ülkeler): {e}")
                import traceback
                traceback.print_exc()
                return get_fallback_countries()
        else:
            # Fallback: Statik liste
            print(f"[GeoNames] Countries non-200: {response.status_code}")
            try:
                print(f"[GeoNames] Response body: {response.text[:200]}")
            except Exception:
                pass
            return get_fallback_countries()
    except Exception as e:
        print(f"[GeoNames] API hatası (ülkeler): {e}")
        import traceback
        traceback.print_exc()
        return get_fallback_countries()

def get_states(country_iso2):
    """Belirli bir ülkenin eyaletlerini/şehirlerini getir - GeoNames API kullanır, seçilen dile göre"""
    if not GEONAMES_USERNAME or not GEONAMES_USERNAME.strip():
        if app.debug:
            print(f"GeoNames username yok, fallback kullanılıyor (TR için {len(get_fallback_states('TR'))} il)")
        return get_fallback_states(country_iso2)
    
    # Session'dan dil bilgisini al
    lang = 'tr'  # Varsayılan
    try:
        from flask import session
        if session and session.get('language'):
            lang = session.get('language', 'tr')[:2]  # İlk 2 karakteri al (tr, en, fr, de)
    except:
        pass
    
    try:
        # GeoNames'ta şehirler için searchJSON kullanılır
        # Türkiye için: featureClass=A (Administrative boundaries) ve featureCode=ADM1 (il seviyesi)
        url = f"{GEONAMES_API_BASE}/searchJSON"
        params = {
            "country": country_iso2,
            "featureClass": "A",  # Administrative boundaries
            "maxRows": 1000,
            "username": GEONAMES_USERNAME,
            "lang": lang  # GeoNames dil parametresi
        }
        
        # Ülkeye göre featureCode ekle (ADM1 = eyalet/il seviyesi)
        # Tüm ülkeler için ADM1 kullan (eyalet/il seviyesi idari birimler)
        params["featureCode"] = "ADM1"
        
        response = requests.get(url, params=params, timeout=10)
        print(f"[GeoNames] GET {url} -> {response.status_code}")
        print(f"[GeoNames] Params: {params}")
        if response.status_code == 200:
            data = response.json()
            places = data.get("geonames", [])
            # Debug: API yanıtını logla
            print(f"[GeoNames] API yanıtı (status 200): {len(places) if places else 0} place bulundu (country={country_iso2})")
            if not places or len(places) == 0:
                print(f"[GeoNames] API boş array döndürdü, response body: {response.text[:500]}")
            # Eğer API boş array döndürüyorsa fallback kullan
            if not places or len(places) == 0:
                print(f"[GeoNames] API boş array döndürdü, fallback kullanılıyor (country={country_iso2})")
                return get_fallback_states(country_iso2)
            # GeoNames formatını bizim formatımıza çevir
            try:
                formatted_states = []
                seen_codes = set()
                for place in places:
                    name = place.get("name", "")
                    if not name:
                        print(f"[GeoNames] Place skipped (no name): {place.get('geonameId', 'unknown')}")
                        continue
                    
                    # Ülkeye göre admin code belirleme
                    if country_iso2 == "TR":
                        # Türkiye için adminCode1'i iso2 olarak kullan (örn: 34 = İstanbul)
                        admin_code = place.get("adminCode1", "")
                    else:
                        # Diğer ülkeler için ISO3166_2 kodunu kullan (örn: DE için NW, BY, etc.)
                        admin_codes = place.get("adminCodes1", {})
                        if isinstance(admin_codes, dict):
                            admin_code = admin_codes.get("ISO3166_2", "")
                            if not admin_code:
                                print(f"[GeoNames] Place {name}: adminCodes1={admin_codes}, ISO3166_2 not found")
                        else:
                            admin_code = place.get("adminCode1", "")
                            print(f"[GeoNames] Place {name}: adminCodes1 is not dict, using adminCode1={admin_code}")
                    
                    # Eğer admin_code yoksa, name'in ilk harflerini kullan
                    if not admin_code:
                        # Name'den kısa kod oluştur (örn: "Nordrhein-Westfalen" -> "NW")
                        words = name.split()
                        if len(words) >= 2:
                            admin_code = (words[0][0] + words[1][0]).upper()
                        else:
                            admin_code = name[:2].upper()
                        print(f"[GeoNames] Place {name}: Generated admin_code={admin_code} from name")
                    
                    # Benzersiz kod kontrolü
                    code_key = f"{country_iso2}_{admin_code}"
                    if code_key not in seen_codes:
                        formatted_states.append({"iso2": admin_code, "name": name})
                        seen_codes.add(code_key)
                        if len(formatted_states) <= 5:
                            print(f"[GeoNames] Formatted state {len(formatted_states)}: iso2={admin_code}, name={name}")
                
                print(f"[GeoNames] API'den {len(formatted_states)} state formatlandı (country={country_iso2})")
                if len(formatted_states) > 0:
                    print(f"[GeoNames] First formatted state: {formatted_states[0]}")
                
                # Eğer yeterli veri yoksa fallback kullan
                if len(formatted_states) < 3:
                    print(f"[GeoNames] API yeterli veri döndürmedi ({len(formatted_states)} state), fallback kullanılıyor")
                    return get_fallback_states(country_iso2)
                print(f"[GeoNames] Returning {len(formatted_states)} states for {country_iso2}")
                return formatted_states
            except Exception as e:
                print(f"[GeoNames] API veri formatlama hatası: {e}, fallback kullanılıyor")
                import traceback
                traceback.print_exc()
                return get_fallback_states(country_iso2)
        else:
            # Fallback: Statik veriler
            if app.debug:
                try:
                    print(f"GeoNames states non-200: {response.status_code} body={response.text[:200]}")
                except Exception:
                    pass
            return get_fallback_states(country_iso2)
    except Exception as e:
        if app.debug:
            print(f"GeoNames API hatası (eyaletler): {e}")
        # Fallback: Statik veriler
        return get_fallback_states(country_iso2)

def get_cities(country_iso2, state_iso2=None):
    """Belirli bir ülke/eyaletin şehirlerini getir - GeoNames API kullanır, seçilen dile göre"""
    if not GEONAMES_USERNAME or not GEONAMES_USERNAME.strip():
        if app.debug:
            print(f"GeoNames username yok, fallback kullanılıyor (ilçeler için)")
        return get_fallback_cities(country_iso2, state_iso2)
    
    # Session'dan dil bilgisini al
    lang = 'tr'  # Varsayılan
    try:
        from flask import session
        if session and session.get('language'):
            lang = session.get('language', 'tr')[:2]  # İlk 2 karakteri al (tr, en, fr, de)
    except:
        pass
    
    try:
        # GeoNames'ta ilçeler için searchJSON kullanılır
        # featureClass=P: Populated places (şehirler/ilçeler)
        # Türkiye için daha iyi sonuç verir
        url = f"{GEONAMES_API_BASE}/searchJSON"
        params = {
            "country": country_iso2,
            "featureClass": "P",  # Populated places (şehirler/ilçeler)
            "maxRows": 1000,
            "username": GEONAMES_USERNAME,
            "lang": lang  # GeoNames dil parametresi
        }
        
        # Eğer state_iso2 (il/eyalet kodu) varsa, adminCode1 parametresi ekle
        actual_admin_code1 = state_iso2  # Varsayılan olarak state_iso2'yi kullan
        if state_iso2:
            # Türkiye için: state_iso2 direkt adminCode1 (örn: "34" = İstanbul)
            # Diğer ülkeler için: state_iso2 ISO3166_2 kodu olabilir (örn: "22" = Polonya için Pomeranian)
            # Önce state_iso2'yi adminCode1'e çevirmek için eyaletleri kontrol et
            if country_iso2 != "TR":
                # Diğer ülkeler için: ISO3166_2 kodunu adminCode1'e çevir
                try:
                    # Önce eyaletleri getir ve ISO3166_2 ile eşleşen adminCode1'i bul
                    states_url = f"{GEONAMES_API_BASE}/searchJSON"
                    states_params = {
                        "country": country_iso2,
                        "featureClass": "A",
                        "featureCode": "ADM1",
                        "maxRows": 100,
                        "username": GEONAMES_USERNAME,
                        "lang": lang
                    }
                    states_response = requests.get(states_url, params=states_params, timeout=5)
                    if states_response.status_code == 200:
                        states_data = states_response.json()
                        states_places = states_data.get("geonames", [])
                        for state_place in states_places:
                            state_admin_codes = state_place.get("adminCodes1", {})
                            if isinstance(state_admin_codes, dict):
                                state_iso3166_2 = state_admin_codes.get("ISO3166_2", "")
                                if state_iso3166_2 == state_iso2:
                                    actual_admin_code1 = state_place.get("adminCode1", state_iso2)
                                    print(f"[GeoNames] State ISO3166_2={state_iso2} -> adminCode1={actual_admin_code1} (country={country_iso2})")
                                    break
                except Exception as e:
                    print(f"[GeoNames] State lookup hatası: {e}, state_iso2 direkt kullanılıyor")
            
            params["adminCode1"] = actual_admin_code1
            
            # Türkiye için featureCode ekle (P.PPLA = başkent, P.PPL = şehir, P.PPLA2 = ilçe)
            # Ancak PPLA2 bazı iller için yeterli olmayabilir, bu yüzden önce PPLA2 dene, sonra tüm P'leri al
            if country_iso2 == "TR":
                # Önce PPLA2 ile dene (ilçe merkezleri)
                params["featureCode"] = "PPLA2"
                # maxRows ücretsiz serviste maksimum 1000
                params["maxRows"] = 1000
        
        response = requests.get(url, params=params, timeout=10)
        print(f"[GeoNames] GET {url} -> {response.status_code}")
        print(f"[GeoNames] Params: {params}")
        if response.status_code == 200:
            data = response.json()
            places = data.get("geonames", [])
            # Debug: API yanıtını logla
            print(f"[GeoNames] API yanıtı (status 200): {len(places) if places else 0} place bulundu (country={country_iso2}, state={state_iso2})")
            if not places or len(places) == 0:
                print(f"[GeoNames] API boş array döndürdü (ilçeler), response body: {response.text[:500]}")
            # Eğer API boş array döndürüyorsa, Türkiye için featureCode olmadan tekrar dene
            if not places or len(places) == 0:
                if country_iso2 == "TR" and state_iso2 and params.get("featureCode") == "PPLA2":
                    print(f"[GeoNames] PPLA2 ile sonuç yok, featureCode olmadan tekrar deneniyor (country={country_iso2}, state={state_iso2})")
                    # featureCode'u kaldır ve tekrar dene
                    params_no_fcode = params.copy()
                    params_no_fcode.pop("featureCode", None)
                    response2 = requests.get(url, params=params_no_fcode, timeout=10)
                    if response2.status_code == 200:
                        data2 = response2.json()
                        places = data2.get("geonames", [])
                        print(f"[GeoNames] featureCode olmadan {len(places) if places else 0} place bulundu")
                
                if not places or len(places) == 0:
                    print(f"[GeoNames] API boş array döndürdü (ilçeler), fallback kullanılıyor (country={country_iso2}, state={state_iso2})")
                    return get_fallback_cities(country_iso2, state_iso2)
            # GeoNames formatını bizim formatımıza çevir
            try:
                formatted_cities = []
                seen_names = set()
                for place in places:
                    name = place.get("name", "")
                    if not name:
                        continue
                    
                    # Eğer state_iso2 (il/eyalet kodu) varsa, adminCode1 kontrolü yap
                    if state_iso2:
                        # Belirli bir il/eyalet için şehirleri/ilçeleri getir
                        place_admin_code1 = place.get("adminCode1", "")
                        
                        # Türkiye için adminCode1 string olarak karşılaştır (örn: "34")
                        # Diğer ülkeler için ISO3166_2 kodunu kullan
                        if country_iso2 == "TR":
                            # Türkiye: adminCode1 string olarak karşılaştır
                            if place_admin_code1 == state_iso2:
                                if name not in seen_names:
                                    formatted_cities.append({"name": name})
                                    seen_names.add(name)
                                    if len(formatted_cities) <= 5:
                                        print(f"[GeoNames] City {len(formatted_cities)}: {name} (adminCode1={place_admin_code1}, state={state_iso2})")
                        else:
                            # Diğer ülkeler: adminCode1 ile karşılaştır (zaten actual_admin_code1'e çevrildi)
                            # API'den gelen place'ler zaten adminCode1 ile filtrelenmiş olmalı
                            # Ama yine de kontrol et
                            if place_admin_code1 == actual_admin_code1:
                                if name not in seen_names:
                                    formatted_cities.append({"name": name})
                                    seen_names.add(name)
                                    if len(formatted_cities) <= 5:
                                        print(f"[GeoNames] City {len(formatted_cities)}: {name} (adminCode1={place_admin_code1}, actual_admin_code1={actual_admin_code1})")
                    else:
                        # Tüm şehirleri/ilçeleri getir (state_iso2 yoksa)
                        if name not in seen_names:
                            formatted_cities.append({"name": name})
                            seen_names.add(name)
                
                print(f"[GeoNames] API'den {len(formatted_cities)} city formatlandı (country={country_iso2}, state={state_iso2})")
                if len(formatted_cities) > 0:
                    print(f"[GeoNames] First formatted city: {formatted_cities[0]}")
                
                # Eğer yeterli veri yoksa fallback kullan
                if len(formatted_cities) < 3:
                    print(f"[GeoNames] API yeterli veri döndürmedi ({len(formatted_cities)} city), fallback kullanılıyor")
                    return get_fallback_cities(country_iso2, state_iso2)
                
                print(f"[GeoNames] Returning {len(formatted_cities)} cities for {country_iso2}/{state_iso2}")
                return formatted_cities
            except Exception as e:
                print(f"[GeoNames] API veri formatlama hatası (ilçeler): {e}")
                import traceback
                traceback.print_exc()
                return get_fallback_cities(country_iso2, state_iso2)
        else:
            # Fallback: Statik veriler
            print(f"[GeoNames] Cities non-200: {response.status_code}")
            try:
                print(f"[GeoNames] Response body: {response.text[:200]}")
            except Exception:
                pass
            return get_fallback_cities(country_iso2, state_iso2)
    except Exception as e:
        print(f"[GeoNames] API hatası (şehirler): {e}")
        import traceback
        traceback.print_exc()
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
        print(f"[API] /api/states/{country_iso2} çağrıldı")
        states = get_states(country_iso2)
        print(f"[API] /api/states/{country_iso2} döndü: {len(states) if states else 0} state")
        return jsonify(states)
    except Exception as e:
        print(f"[API] /api/states/{country_iso2} hatası: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/cities/<country_iso2>')
@app.route('/api/cities/<country_iso2>/<state_iso2>')
def api_cities(country_iso2, state_iso2=None):
    """Belirli bir ülke/eyaletin şehirlerini getir"""
    try:
        print(f"[API] /api/cities/{country_iso2}/{state_iso2} çağrıldı")
        cities = get_cities(country_iso2, state_iso2)
        print(f"[API] /api/cities/{country_iso2}/{state_iso2} döndü: {len(cities) if cities else 0} city")
        return jsonify(cities)
    except Exception as e:
        print(f"[API] /api/cities/{country_iso2}/{state_iso2} hatası: {e}")
        import traceback
        traceback.print_exc()
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
        
        # Kullanici kontrolu - önce ORM ile dene
        user = None
        try:
            user = Kullanici.query.filter_by(KullaniciAdi=username, Aktif=True).first()
            if user:
                print(f"[DEBUG] Kullanici ORM ile bulundu: {username}")
        except Exception as orm_err:
            print(f"[DEBUG] ORM sorgusu basarisiz: {orm_err}")
            import traceback
            traceback.print_exc()
        
        # ORM başarısız olursa direkt SQL ile dene (tablo ismi küçük harf olabilir)
        if not user:
            try:
                # Dialect kontrolü - sadece MySQL/MSSQL için SQL fallback
                dialect_name = db.engine.dialect.name if hasattr(db.engine, 'dialect') else None
                if dialect_name in ('mysql', 'mssql'):
                    with db.engine.connect() as conn:
                        # Veritabanı bilgilerini göster (sadece MySQL için)
                        if dialect_name == 'mysql':
                            try:
                                current_db = conn.execute(text("SELECT DATABASE()")).scalar()
                                print(f"[DEBUG] Aktif veritabani: {current_db}")
                            except:
                                pass
                        
                        # Tablo ismini bul (küçük/büyük harf farkı olabilir)
                        from sqlalchemy import inspect
                        inspector = inspect(db.engine)
                        tables = inspector.get_table_names()
                        print(f"[DEBUG] Veritabanindaki tablolar ({len(tables)} adet): {sorted(tables)[:10]}...")
                        
                        kullanicilar_table = None
                        for table in tables:
                            if table.lower() == 'kullanicilar':
                                kullanicilar_table = table
                                break
                        
                        print(f"[DEBUG] Kullanicilar tablosu bulundu: {kullanicilar_table}")
                        
                        if kullanicilar_table:
                            # Önce kayıt sayısını kontrol et
                            count = conn.execute(text(f"SELECT COUNT(*) FROM `{kullanicilar_table}`")).scalar()
                            print(f"[DEBUG] Kullanicilar tablosundaki toplam kayit sayisi: {count}")
                            
                            result = conn.execute(text(f"""
                                SELECT KullaniciID, KullaniciAdi, Sifre, Ad, Soyad, Email, FirmaID, Admin, Aktif,
                                       COALESCE(RaporlarModulu, 1) as RaporlarModulu,
                                       COALESCE(AyarlarModulu, 0) as AyarlarModulu,
                                       COALESCE(LogModulu, 0) as LogModulu
                                FROM `{kullanicilar_table}`
                                WHERE KullaniciAdi = :username AND Aktif = 1
                            """), {"username": username})
                            user_data = result.fetchone()
                            
                            if user_data:
                                print(f"[DEBUG] Kullanici SQL ile bulundu: {username}")
                                # SQLAlchemy Row objesini Kullanici modeline benzer bir objeye dönüştür
                                class UserProxy:
                                    def __init__(self, row_data):
                                        self.KullaniciID = row_data[0]
                                        self.KullaniciAdi = row_data[1]
                                        self.Sifre = row_data[2]
                                        self.Ad = row_data[3]
                                        self.Soyad = row_data[4]
                                        self.Email = row_data[5]
                                        self.FirmaID = row_data[6]
                                        self.Admin = bool(row_data[7])
                                        self.Aktif = bool(row_data[8])
                                        self.RaporlarModulu = bool(row_data[9]) if len(row_data) > 9 else True
                                        self.AyarlarModulu = bool(row_data[10]) if len(row_data) > 10 else False
                                        self.LogModulu = bool(row_data[11]) if len(row_data) > 11 else False
                                
                                user = UserProxy(user_data)
                            else:
                                print(f"[DEBUG] Kullanici SQL ile bulunamadi: {username}")
                                # Tüm kullanıcıları listele (Aktif filtresi olmadan)
                                all_users = conn.execute(text(f"SELECT KullaniciAdi, Aktif FROM `{kullanicilar_table}`")).fetchall()
                                print(f"[DEBUG] Veritabanindaki tum kullanicilar (Aktif filtresi olmadan): {[u[0] for u in all_users]}")
                                
                                # Aktif olmayan kullanıcıları da kontrol et
                                inactive_user = conn.execute(text(f"""
                                    SELECT KullaniciAdi, Aktif FROM `{kullanicilar_table}` 
                                    WHERE KullaniciAdi = :username
                                """), {"username": username}).fetchone()
                                if inactive_user:
                                    print(f"[DEBUG] Kullanici bulundu ama Aktif={inactive_user[1]}: {username}")
                        else:
                            print(f"[DEBUG] Kullanicilar tablosu bulunamadi!")
                else:
                    print(f"[DEBUG] SQL fallback atlandi - dialect: {dialect_name} (sadece MySQL/MSSQL destekleniyor)")
            except Exception as sql_err:
                print(f"[DEBUG] SQL sorgusu basarisiz: {sql_err}")
                import traceback
                traceback.print_exc()
        
        # Kullanıcı bulunamadıysa hata ver
        if not user:
            print(f"[DEBUG] Kullanici bulunamadi: {username}")
            flash('Kullanıcı adı veya şifre hatalı!', 'error')
            return render_template('login.html')
        
        # Şifre kontrolü - hash'lenmiş şifreyi kontrol et
        if user.Sifre and check_password_hash(user.Sifre, password):
            print(f"[DEBUG] Sifre kontrolu basarili - giris onaylandi")
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
                # Admin kullanıcılar için otomatik WhatsApp ve Instagram yetkisi
                if user.Admin:
                    session['pending_whatsapp_modulu'] = True
                    session['pending_instagram_modulu'] = True
                else:
                    whatsapp_modulu_value = getattr(user, 'WhatsAppModulu', False)
                    session['pending_whatsapp_modulu'] = bool(whatsapp_modulu_value) if whatsapp_modulu_value is not None else False
                    instagram_modulu_value = getattr(user, 'InstagramModulu', False)
                    session['pending_instagram_modulu'] = bool(instagram_modulu_value) if instagram_modulu_value is not None else False
                
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
            # WhatsAppModulu kontrolü - Admin ise otomatik True
            whatsapp_modulu_value = getattr(user, 'WhatsAppModulu', False)
            # Admin kullanıcılar için otomatik WhatsApp yetkisi
            if user.Admin:
                session['whatsapp_modulu'] = True
            else:
                session['whatsapp_modulu'] = bool(whatsapp_modulu_value) if whatsapp_modulu_value is not None else False
            # InstagramModulu kontrolü - Admin ise otomatik True
            instagram_modulu_value = getattr(user, 'InstagramModulu', False)
            if user.Admin:
                session['instagram_modulu'] = True
            else:
                session['instagram_modulu'] = bool(instagram_modulu_value) if instagram_modulu_value is not None else False

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
    pending_whatsapp_modulu = request.form.get('pending_whatsapp_modulu') or session.get('pending_whatsapp_modulu')
    pending_instagram_modulu = request.form.get('pending_instagram_modulu') or session.get('pending_instagram_modulu')
    
    # Admin kontrolü - Admin ise otomatik True
    pending_is_admin_bool = pending_is_admin in [True, 'True', 'true', '1', 1]
    if pending_is_admin_bool:
        pending_whatsapp_modulu = True
        pending_instagram_modulu = True
    
    # Session'ı tamamen temizle
    session.clear()
    
    # Yeni oturum oluştur
    session['user_id'] = pending_user_id
    session['username'] = pending_username
    session['user_name'] = pending_user_name
    session['firma_id'] = pending_firma_id
    session['firma_adi'] = pending_firma_adi
    session['is_admin'] = pending_is_admin_bool
    session['raporlar_modulu'] = pending_raporlar_modulu
    session['ayarlar_modulu'] = pending_ayarlar_modulu
    session['log_modulu'] = pending_log_modulu
    session['whatsapp_modulu'] = pending_whatsapp_modulu if pending_whatsapp_modulu is not None else False
    session['instagram_modulu'] = pending_instagram_modulu if pending_instagram_modulu is not None else False
    
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
            whatsapp_modulu = 'whatsapp_modulu' in request.form
            
            # Varsayılan şifre 123 ve ilk girişte değişim zorunlu olacak
            u = Kullanici(KullaniciAdi=kullanici_adi, Email=email, FirmaID=firma_id,
                          Sifre=sifre or '123', Ad=ad, Soyad=soyad, Aktif=True,
                          RaporlarModulu=raporlar_modulu, AyarlarModulu=ayarlar_modulu,
                          LogModulu=log_modulu, WhatsAppModulu=whatsapp_modulu)
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
                    # Dosya yolunu relative path olarak kaydet (static/ ile başlamadan)
                    relative_path = f'uploads/users/user_{u.KullaniciID}.jpg'
                    out_path = os.path.join('static', relative_path)
                    img.save(out_path, format='JPEG', quality=85, optimize=True)
                    # Dosya yolunu veritabanına kaydet
                    u.ProfilFotografi = relative_path
                    db.session.commit()
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
                            # Dosya yolunu relative path olarak kaydet (static/ ile başlamadan)
                            relative_path = f'uploads/users/user_{u.KullaniciID}.jpg'
                            out_path = os.path.join('static', relative_path)
                            img.save(out_path, format='JPEG', quality=85, optimize=True)
                            # Dosya yolunu veritabanına kaydet
                            u.ProfilFotografi = relative_path
                            db.session.commit()
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
        whatsapp_modulu = 'whatsapp_modulu' in request.form
        
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
                kullanici.WhatsAppModulu = whatsapp_modulu
                
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
                        # Dosya yolunu relative path olarak kaydet (static/ ile başlamadan)
                        relative_path = f'uploads/users/user_{kullanici.KullaniciID}.jpg'
                        out_path = os.path.join('static', relative_path)
                        img.save(out_path, format='JPEG', quality=85, optimize=True)
                        # Dosya yolunu veritabanına kaydet
                        kullanici.ProfilFotografi = relative_path
                        db.session.commit()
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
                                # Dosya yolunu relative path olarak kaydet (static/ ile başlamadan)
                                relative_path = f'uploads/users/user_{kullanici.KullaniciID}.jpg'
                                out_path = os.path.join('static', relative_path)
                                img.save(out_path, format='JPEG', quality=85, optimize=True)
                                # Dosya yolunu veritabanına kaydet
                                kullanici.ProfilFotografi = relative_path
                                db.session.commit()
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
        FirmaID=session['firma_id'],
        Aktif=True
    ).order_by(MusteriKategori.KategoriID.asc()).all()
    
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
            TestNumarasi=request.form.get('test_numarasi'),
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
        whatsapp_ayar.TestNumarasi = request.form.get('test_numarasi')
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

# WhatsApp Bağlantı Test API
@app.route('/api/whatsapp/test', methods=['POST'])
@login_required
def whatsapp_test_connection():
    """WhatsApp bağlantısını test et"""
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        phone_number_id = data.get('phone_number_id')
        
        if not access_token or not phone_number_id:
            return jsonify({'success': False, 'error': 'Access Token ve Phone Number ID gerekli'}), 400
        
        import requests
        
        # Phone Number ID'yi doğrula
        url = f"https://graph.facebook.com/v24.0/{phone_number_id}"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        print(f"[WhatsApp Test] API isteği gönderiliyor: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"[WhatsApp Test] API yanıt kodu: {response.status_code}")
        print(f"[WhatsApp Test] API yanıt: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            verified_name = response_data.get('verified_name', 'Bilinmiyor')
            display_phone_number = response_data.get('display_phone_number', 'Bilinmiyor')
            code_verification_status = response_data.get('code_verification_status', 'Bilinmiyor')
            quality_rating = response_data.get('quality_rating', 'Bilinmiyor')
            
            message = f'<div class="alert alert-success mb-0">'
            message += f'<h6><i class="fas fa-check-circle"></i> Bağlantı Başarılı!</h6>'
            message += f'<hr class="my-2">'
            message += f'<strong>Doğrulanmış İsim:</strong> {verified_name}<br>'
            message += f'<strong>Telefon Numarası:</strong> {display_phone_number}<br>'
            message += f'<strong>Kod Doğrulama Durumu:</strong> {code_verification_status}'
            
            if code_verification_status == 'NOT_VERIFIED':
                message += '<hr class="my-2">'
                message += '<div class="alert alert-warning mb-0 mt-2">'
                message += '<small><i class="fas fa-info-circle"></i> <strong>Test Numarası:</strong> Bu bir test numarasıdır. Test numaraları ile mesaj göndermek için alıcı numarasının önce size mesaj göndermesi gerekir (24 saat kuralı) veya alıcı numarasının WhatsApp Business hesabınıza kayıtlı olması gerekir.</small>'
                message += '</div>'
            
            message += '</div>'
            
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            try:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Bilinmeyen hata')
                error_code = error_data.get('error', {}).get('code', 'Bilinmeyen kod')
                
                # Türkçe hata mesajları
                if error_code == 190:
                    error_message = "Access Token geçersiz veya süresi dolmuş. Lütfen yeni bir Access Token oluşturun."
                elif error_code == 133010:
                    error_message = "Phone Number ID kayıtlı değil veya Access Token bu Phone Number ID ile eşleşmiyor. Lütfen Meta Business Suite'te kontrol edin."
                elif error_code == 100:
                    error_message = f"Geçersiz parametreler: {error_message}"
                
                return jsonify({
                    'success': False,
                    'error': f'Hata (Kod: {error_code}): {error_message}'
                }), 400
            except:
                return jsonify({
                    'success': False,
                    'error': f'API hatası: {response.text}'
                }), 400
                
    except Exception as e:
        print(f"[WhatsApp Test] Hata: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Instagram Ayarları
@app.route('/ayarlar/instagram')
@login_required
def ayarlar_instagram():
    # Instagram modülü yetki kontrolü
    if not session.get('is_admin', False) and not session.get('instagram_modulu', False):
        flash('Instagram ayarlarına erişim yetkiniz yok!', 'error')
        return redirect(url_for('ayarlar'))
    
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
        
        instagram_ayar = FirmaInstagramAyar.query.filter_by(FirmaID=selected_firma_id).first()
        firmalar = Firma.query.filter_by(Aktif=True).all()
        return render_template('ayarlar/instagram.html', 
                             instagram_ayar=instagram_ayar, 
                             firma=firma,
                             firmalar=firmalar,
                             is_admin=True)
    else:
        # Normal kullanıcı sadece kendi firmasını görebilir
        firma = Firma.query.get(session['firma_id'])
        if not firma:
            flash('Firma bilgisi bulunamadı!', 'error')
            return redirect(url_for('ayarlar'))
        
        instagram_ayar = FirmaInstagramAyar.query.filter_by(FirmaID=session['firma_id']).first()
        return render_template('ayarlar/instagram.html', 
                             instagram_ayar=instagram_ayar, 
                             firma=firma,
                             is_admin=False)

@app.route('/ayarlar/instagram/ekle', methods=['POST'])
@login_required
def ayarlar_instagram_ekle():
    # Instagram modülü yetki kontrolü
    if not session.get('is_admin', False) and not session.get('instagram_modulu', False):
        flash('Instagram ayarlarına erişim yetkiniz yok!', 'error')
        return redirect(url_for('ayarlar'))
    
    try:
        # Admin ise formdan gelen firma_id'yi kullan
        hedef_firma_id = session['firma_id']
        try:
            if session.get('is_admin', False) and request.form.get('firma_id'):
                hedef_firma_id = int(request.form.get('firma_id'))
        except (ValueError, TypeError):
            pass
        
        # Mevcut ayar var mı kontrol et
        mevcut_ayar = FirmaInstagramAyar.query.filter_by(FirmaID=hedef_firma_id).first()
        if mevcut_ayar:
            flash('Bu firma için Instagram ayarı zaten mevcut!', 'error')
            return redirect(url_for('ayarlar_instagram'))
        
        # Yeni Instagram ayarı oluştur
        instagram_ayar = FirmaInstagramAyar(
            FirmaID=hedef_firma_id,
            FacebookPageID=request.form.get('facebook_page_id'),
            InstagramBusinessAccountID=request.form.get('instagram_account_id'),
            AccessToken=request.form.get('access_token'),
            WebhookSecret=request.form.get('webhook_secret'),
            Aktif=bool(request.form.get('aktif'))
        )
        
        db.session.add(instagram_ayar)
        db.session.commit()
        
        flash('Instagram ayarları başarıyla eklendi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Instagram ayarları eklenirken hata oluştu: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_instagram', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_instagram'))

@app.route('/ayarlar/instagram/guncelle/<int:ayar_id>', methods=['POST'])
@login_required
def ayarlar_instagram_guncelle(ayar_id):
    # Instagram modülü yetki kontrolü
    if not session.get('is_admin', False) and not session.get('instagram_modulu', False):
        flash('Instagram ayarlarına erişim yetkiniz yok!', 'error')
        return redirect(url_for('ayarlar'))
    
    try:
        instagram_ayar = FirmaInstagramAyar.query.get_or_404(ayar_id)
        
        # Kullanıcı yetkisi kontrolü
        if not session.get('is_admin', False) and instagram_ayar.FirmaID != session['firma_id']:
            flash('Bu ayarı düzenleme yetkiniz yok!', 'error')
            return redirect(url_for('ayarlar_instagram'))
        
        # Ayarları güncelle
        instagram_ayar.FacebookPageID = request.form.get('facebook_page_id')
        instagram_ayar.InstagramBusinessAccountID = request.form.get('instagram_account_id')
        instagram_ayar.AccessToken = request.form.get('access_token')
        instagram_ayar.WebhookSecret = request.form.get('webhook_secret')
        instagram_ayar.Aktif = bool(request.form.get('aktif'))
        instagram_ayar.GuncellemeTarihi = datetime.now()
        
        db.session.commit()
        flash('Instagram ayarları başarıyla güncellendi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Instagram ayarları güncellenirken hata oluştu: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_instagram', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_instagram'))

@app.route('/ayarlar/instagram/sil/<int:ayar_id>', methods=['POST', 'GET'])
@login_required
def ayarlar_instagram_sil(ayar_id):
    # Instagram modülü yetki kontrolü
    if not session.get('is_admin', False) and not session.get('instagram_modulu', False):
        flash('Instagram ayarlarına erişim yetkiniz yok!', 'error')
        return redirect(url_for('ayarlar'))
    
    try:
        instagram_ayar = FirmaInstagramAyar.query.get_or_404(ayar_id)
        
        # Kullanıcı yetkisi kontrolü
        if not session.get('is_admin', False) and instagram_ayar.FirmaID != session['firma_id']:
            flash('Bu ayarı silme yetkiniz yok!', 'error')
            return redirect(url_for('ayarlar_instagram'))
        
        db.session.delete(instagram_ayar)
        db.session.commit()
        flash('Instagram ayarları başarıyla silindi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Instagram ayarları silinirken hata oluştu: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False):
        hedef_firma_id = request.args.get('firma_id')
        if hedef_firma_id:
            return redirect(url_for('ayarlar_instagram', firma_id=hedef_firma_id))
    return redirect(url_for('ayarlar_instagram'))

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
    # Kullanıcı modül yetkisi kontrolü
    if not session.get('whatsapp_modulu', False):
        flash('Bu sayfaya erişim yetkiniz yok', 'error')
        return redirect(url_for('dashboard'))
    # Firma WhatsApp ayarlarını kontrol et
    whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).first()
    
    if not whatsapp_ayar:
        flash('WhatsApp ayarları bulunamadı. Lütfen önce WhatsApp ayarlarını yapılandırın.', 'warning')
        return redirect(url_for('ayarlar_whatsapp'))
    
    # Müşteri listesini getir (telefon numarası olanlar, aktif müşteriler)
    musteriler = Musteri.query.filter(
        Musteri.FirmaID == session['firma_id'],
        Musteri.Telefon.isnot(None),
        Musteri.Telefon != ''
    ).order_by(Musteri.MusteriAdi, Musteri.MusteriSoyadi).all()
    
    # Randevu defterlerini getir
    defterler = RandevuDefterAyar.query.filter_by(
        FirmaID=session['firma_id'], 
        Aktif=True
    ).order_by(RandevuDefterAyar.DefterAdi).all()
    
    return render_template('whatsapp/chat.html', 
                         whatsapp_ayar=whatsapp_ayar,
                         musteriler=musteriler,
                         defterler=defterler)

# WhatsApp Mesajları API
@app.route('/api/whatsapp/messages/<int:musteri_id>')
@login_required
def whatsapp_get_messages(musteri_id):
    """Müşteriye ait WhatsApp mesajlarını getir"""
    # Kullanıcı modül yetkisi kontrolü
    if not session.get('whatsapp_modulu', False):
        print(f"[WhatsApp Messages] WhatsApp yetkisi yok, kullanıcı: {session.get('user_id')}")
        return jsonify({'success': False, 'error': 'Bu işlem için WhatsApp yetkiniz yok'}), 403
    
    try:
        firma_id = session.get('firma_id')
        print(f"[WhatsApp Messages] Müşteri ID: {musteri_id}, Firma ID: {firma_id}")
        
        # Müşteriyi kontrol et
        musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
        if not musteri:
            print(f"[WhatsApp Messages] Müşteri bulunamadı: {musteri_id}")
            return jsonify({'success': False, 'error': 'Müşteri bulunamadı'}), 404
        
        print(f"[WhatsApp Messages] Müşteri bulundu: {musteri.MusteriAdi} {musteri.MusteriSoyadi}, Telefon: {musteri.Telefon}")
        
        # WhatsApp mesajlarını getir
        # Önce MusteriID'ye göre filtrele
        mesajlar = WhatsAppMesaj.query.filter_by(
            FirmaID=firma_id,
            MusteriID=musteri_id
        ).order_by(WhatsAppMesaj.Tarih.asc()).all()
        
        print(f"[WhatsApp Messages] MusteriID ile bulunan mesaj sayısı: {len(mesajlar)}")
        
        # Eğer MusteriID ile mesaj bulunamazsa, telefon numarasına göre dene
        if not mesajlar and musteri.Telefon:
            # Telefon numarasını temizle (sadece rakamlar)
            telefon_clean = ''.join(filter(str.isdigit, musteri.Telefon))
            print(f"[WhatsApp Messages] Telefon numarası temizlendi: {telefon_clean}")
            
            # Eğer 0 ile başlıyorsa, 90 ekle
            if telefon_clean.startswith('0'):
                telefon_clean = '90' + telefon_clean[1:]
            # Eğer 5 ile başlıyorsa ve 10 haneli ise, 90 ekle
            elif telefon_clean.startswith('5') and len(telefon_clean) == 10:
                telefon_clean = '90' + telefon_clean
            
            print(f"[WhatsApp Messages] Formatlanmış telefon: {telefon_clean}")
            
            # Telefon numarasına göre mesajları getir
            mesajlar = WhatsAppMesaj.query.filter_by(
                FirmaID=firma_id
            ).filter(
                or_(
                    WhatsAppMesaj.GonderenTelefon == telefon_clean,
                    WhatsAppMesaj.AliciTelefon == telefon_clean
                )
            ).order_by(WhatsAppMesaj.Tarih.asc()).all()
            
            print(f"[WhatsApp Messages] Telefon numarası ile bulunan mesaj sayısı: {len(mesajlar)}")
        
        # Toplam mesaj sayısını kontrol et
        toplam_mesaj = WhatsAppMesaj.query.filter_by(FirmaID=firma_id).count()
        print(f"[WhatsApp Messages] Firma için toplam mesaj sayısı: {toplam_mesaj}")
        
        # Mesajları formatla
        formatted_messages = []
        for mesaj in mesajlar:
            formatted_messages.append({
                'yonelim': 'gelen' if mesaj.Yyon == 'GELEN' else 'giden',
                'icerik': mesaj.MesajMetni or '',
                'tarih': mesaj.Tarih.strftime('%d.%m.%Y %H:%M') if mesaj.Tarih else ''
            })
        
        print(f"[WhatsApp Messages] Formatlanmış mesaj sayısı: {len(formatted_messages)}")
        
        return jsonify({
            'success': True,
            'messages': formatted_messages
        })
        
    except Exception as e:
        print(f"[WhatsApp Messages] Hata: {e}")
        import traceback
        traceback.print_exc()
        error_message = str(e)
        # Hata mesajını daha anlaşılır hale getir
        if "WhatsAppMesaj" in error_message or "does not exist" in error_message.lower():
            error_message = "WhatsApp mesajları tablosu bulunamadı. Veritabanında WhatsAppMesajlar tablosu oluşturulmamış olabilir."
        return jsonify({
            'success': False, 
            'error': error_message,
            'details': str(e) if app.debug else None
        }), 500

# WhatsApp Mesaj Gönderme API
@app.route('/api/whatsapp/send', methods=['POST'])
@login_required
def whatsapp_send_message():
    """WhatsApp mesajı gönder"""
    # Kullanıcı modül yetkisi kontrolü
    if not session.get('whatsapp_modulu', False):
        print(f"[WhatsApp] WhatsApp yetkisi yok, kullanıcı: {session.get('user_id')}")
        return jsonify({'success': False, 'error': 'Bu işlem için WhatsApp yetkiniz yok'}), 403
    try:
        data = request.get_json()
        print(f"[WhatsApp] Gelen istek: {data}")
        
        # Frontend 'telefon' ve 'mesaj' gönderiyor, backend 'phone_number' ve 'message' bekliyordu.
        # Her ikisini de destekleyelim.
        phone_number = data.get('phone_number') or data.get('telefon')
        message = data.get('message') or data.get('mesaj')
        
        print(f"[WhatsApp] phone_number: {phone_number}, message: {message[:50] if message else None}...")
        
        if not phone_number or not message:
            print(f"[WhatsApp] Eksik parametreler: phone_number={phone_number}, message={bool(message)}")
            return jsonify({'success': False, 'error': 'Telefon numarası ve mesaj gerekli'}), 400
        
        # Telefon numarasını temizle (sadece rakamlar)
        phone_clean = ''.join(filter(str.isdigit, phone_number))
        print(f"[WhatsApp] Temizlenmiş telefon: {phone_clean}, uzunluk: {len(phone_clean)}")
        
        if not phone_clean or len(phone_clean) < 7:
            print(f"[WhatsApp] Geçersiz telefon numarası: {phone_clean}")
            return jsonify({'success': False, 'error': 'Geçersiz telefon numarası (minimum 7 hane gerekli)'}), 400
        
        # WhatsApp mesajını gönder (formatlama send_whatsapp_message içinde yapılacak)
        print(f"[WhatsApp] Mesaj gönderiliyor: {phone_clean}, firma_id: {session['firma_id']}")
        success, result = send_whatsapp_message(phone_clean, message, session['firma_id'])
        
        if success:
            print(f"[WhatsApp] Mesaj başarıyla gönderildi")
            return jsonify({'success': True, 'message': 'Mesaj başarıyla gönderildi'})
        else:
            print(f"[WhatsApp] Mesaj gönderilemedi: {result}")
            return jsonify({'success': False, 'error': result}), 400
            
    except Exception as e:
        print(f"[WhatsApp] Hata: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# WhatsApp mesaj gönderme fonksiyonu
def send_whatsapp_message(phone_number, message, firma_id):
    """WhatsApp mesajı gönder"""
    try:
        whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=firma_id, Aktif=True).first()
        if not whatsapp_ayar or not whatsapp_ayar.AccessToken or not whatsapp_ayar.PhoneNumberID:
            return False, "WhatsApp ayarları bulunamadı"
        
        print(f"[WhatsApp] Ayarlar kontrol ediliyor:")
        print(f"[WhatsApp]   - Phone Number ID: {whatsapp_ayar.PhoneNumberID}")
        print(f"[WhatsApp]   - Access Token (ilk 20 karakter): {whatsapp_ayar.AccessToken[:20] if whatsapp_ayar.AccessToken else 'YOK'}...")
        print(f"[WhatsApp]   - Business Account ID: {whatsapp_ayar.BusinessAccountID}")
        
        import requests
        
        # Telefon numarasını temizle ve formatla
        # WhatsApp API + işareti olmadan bekliyor, sadece rakamlar
        # phone_number zaten sadece rakamlardan oluşuyor (whatsapp_send_message route'unda temizlendi)
        phone_clean = phone_number
        
        print(f"[WhatsApp] Gelen telefon numarası: {phone_clean}, uzunluk: {len(phone_clean)}")
        
        # Telefon numarası formatını düzelt
        # Eğer 0 ile başlıyorsa (0536...), 0'ı kaldır ve 90 ekle
        if phone_clean.startswith('0'):
            phone_clean = '90' + phone_clean[1:]
            print(f"[WhatsApp] 0 ile başlayan numara düzeltildi: {phone_clean}")
        # Eğer 5 ile başlıyorsa ve 10 haneli ise (Türkiye cep telefonu: 5XXXXXXXXX), 90 ekle
        elif phone_clean.startswith('5') and len(phone_clean) == 10:
            phone_clean = '90' + phone_clean
            print(f"[WhatsApp] 10 haneli cep telefonu düzeltildi: {phone_clean}")
        # Eğer 90 ile başlamıyorsa ve 10 haneli ise, 90 ekle
        elif not phone_clean.startswith('90') and len(phone_clean) == 10:
            phone_clean = '90' + phone_clean
            print(f"[WhatsApp] 10 haneli numara düzeltildi: {phone_clean}")
        # Eğer zaten 90 ile başlıyorsa, olduğu gibi kullan
        elif phone_clean.startswith('90'):
            print(f"[WhatsApp] Numara zaten 90 ile başlıyor: {phone_clean}")
        
        # WhatsApp API telefon numarası validasyonu: 7-15 hane arası olmalı
        if len(phone_clean) < 7 or len(phone_clean) > 15:
            return False, f"Telefon numarası geçersiz: {len(phone_clean)} hane (7-15 hane arası olmalı). Formatlanmış numara: {phone_clean}"
        
        # Mesaj içeriği kontrolü
        if not message or not message.strip():
            return False, "Mesaj içeriği boş olamaz"
        
        # Mesaj uzunluğu kontrolü (WhatsApp API maksimum 4096 karakter)
        if len(message) > 4096:
            return False, f"Mesaj çok uzun: {len(message)} karakter (maksimum 4096 karakter)"
        
        print(f"[WhatsApp] Formatlanmış telefon numarası: {phone_clean}, uzunluk: {len(phone_clean)}")
        print(f"[WhatsApp] Mesaj içeriği: {message[:100]}... (uzunluk: {len(message)})")
        
        # API versiyonu: v18.0 deprecated, v24.0 kullanılıyor
        url = f"https://graph.facebook.com/v24.0/{whatsapp_ayar.PhoneNumberID}/messages"
        headers = {
            "Authorization": f"Bearer {whatsapp_ayar.AccessToken}",
            "Content-Type": "application/json"
        }
        
        # Test numarası kontrolü - Test numaraları için özel format gerekebilir
        # WhatsApp Business API'de test numaraları genellikle sadece kayıtlı test numaralarına mesaj gönderebilir
        # veya alıcı numarasının WhatsApp Business hesabına kayıtlı olması gerekebilir
        
        # Test numarası kontrolü - Test numaraları için özel işlem
        # Test numaraları genellikle sadece belirli test numaralarına mesaj gönderebilir
        # veya alıcı numarasının WhatsApp Business hesabına kayıtlı olması gerekir
        
        # Önce Phone Number ID'nin test numarası olup olmadığını kontrol et
        test_number_info = None
        try:
            test_url = f"https://graph.facebook.com/v24.0/{whatsapp_ayar.PhoneNumberID}"
            test_headers = {"Authorization": f"Bearer {whatsapp_ayar.AccessToken}"}
            test_response = requests.get(test_url, headers=test_headers, timeout=10)
            if test_response.status_code == 200:
                test_number_info = test_response.json()
                print(f"[WhatsApp] Phone Number bilgisi: {test_number_info}")
        except:
            pass
        
        data = {
            "messaging_product": "whatsapp",
            "to": phone_clean,
            "type": "text",
            "text": {"body": message.strip()}
        }
        
        # Test numarası ise ve code_verification_status NOT_VERIFIED ise
        # Bu durumda alıcı numarasının WhatsApp Business hesabına kayıtlı olması gerekebilir
        # veya sadece belirli test numaralarına mesaj gönderebilir
        if test_number_info and test_number_info.get('code_verification_status') == 'NOT_VERIFIED':
            print(f"[WhatsApp] Test numarası tespit edildi (NOT_VERIFIED)")
            print(f"[WhatsApp] Test numaraları genellikle sadece belirli test numaralarına mesaj gönderebilir")
            print(f"[WhatsApp] Veya alıcı numarasının WhatsApp Business hesabına kayıtlı olması gerekir")
        
        print(f"[WhatsApp] Mesaj gönderme data: {json.dumps(data, indent=2)}")
        
        print(f"[WhatsApp] API isteği gönderiliyor: {url}")
        print(f"[WhatsApp] Request headers: {headers}")
        print(f"[WhatsApp] Request data: {data}")
        print(f"[WhatsApp] Request data (JSON): {json.dumps(data, indent=2)}")
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"[WhatsApp] Request exception: {e}")
            return False, f"API isteği gönderilemedi: {str(e)}"
        
        print(f"[WhatsApp] API yanıt kodu: {response.status_code}")
        print(f"[WhatsApp] API yanıt headers: {dict(response.headers)}")
        print(f"[WhatsApp] API yanıt: {response.text}")
        
        # Response'u JSON olarak parse etmeyi dene
        try:
            response_json = response.json()
            print(f"[WhatsApp] API yanıt (JSON): {json.dumps(response_json, indent=2)}")
        except:
            print(f"[WhatsApp] API yanıt JSON parse edilemedi")
        
        if response.status_code == 200:
            return True, "Mesaj başarıyla gönderildi"
        else:
            # Hata mesajını parse et
            try:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Bilinmeyen hata')
                error_code = error_data.get('error', {}).get('code', 'Bilinmeyen kod')
                error_type = error_data.get('error', {}).get('type', 'Bilinmeyen tip')
                
                # Orijinal hata mesajını al
                original_error_message = error_data.get('error', {}).get('message', 'Bilinmeyen hata')
                error_subcode = error_data.get('error', {}).get('error_subcode', None)
                
                # Türkçe hata mesajları
                if error_code == 190:
                    error_message = "Access Token geçersiz veya süresi dolmuş. Lütfen WhatsApp ayarlarından Access Token'ı yenileyin. Token'lar genellikle 60 gün sonra süresi doluyor."
                elif error_code == 133010:
                    # Test numarası kontrolü
                    is_test_number = test_number_info and test_number_info.get('code_verification_status') == 'NOT_VERIFIED'
                    if is_test_number:
                        error_message = "Test numarası ile mesaj gönderilemiyor. Test numaraları genellikle sadece belirli test numaralarına mesaj gönderebilir veya alıcı numarasının WhatsApp Business hesabına kayıtlı olması gerekir. Çözüm: 1) Alıcı numarasının WhatsApp Business hesabınıza kayıtlı olduğundan emin olun, 2) Veya gerçek bir WhatsApp Business numarası kullanın (test numarası değil), 3) Meta Business Suite'te hesabınızı doğrulayın ve gerçek numaraya geçin."
                    else:
                        error_message = "WhatsApp Business hesabı kayıtlı değil veya Access Token bu Phone Number ID ile eşleşmiyor. Lütfen şunları kontrol edin: 1) Access Token'ın bu Phone Number ID için geçerli olduğundan emin olun, 2) Meta Business Suite'te WhatsApp Business hesabınızın API'ye bağlı olduğunu kontrol edin, 3) Access Token ve Phone Number ID'nin aynı hesaba ait olduğundan emin olun. Gerekirse yeni bir Access Token oluşturun."
                elif error_code == 463:
                    error_message = "WhatsApp Business hesabınız henüz onaylanmamış. Sadece onaylanmış mesaj şablonları gönderebilirsiniz. Lütfen WhatsApp Business hesabınızı onaylatın veya mesaj şablonu kullanın."
                elif error_code == 131047:
                    error_message = "Alıcı numarası WhatsApp'a kayıtlı değil veya numara geçersiz."
                elif error_code == 131026:
                    error_message = "Mesaj gönderilemedi: Alıcı numarası WhatsApp'a kayıtlı değil."
                elif error_code == 100:
                    # 100 hatası için daha detaylı mesaj
                    print(f"[WhatsApp] Hata detayları - Code: {error_code}, Subcode: {error_subcode}, Type: {error_type}, Message: {original_error_message}")
                    
                    if "Invalid parameter" in original_error_message or "invalid" in original_error_message.lower():
                        if "phone number" in original_error_message.lower() or "to" in original_error_message.lower() or "recipient" in original_error_message.lower():
                            error_message = f"Geçersiz telefon numarası formatı. WhatsApp API telefon numarasını uluslararası formatta bekliyor (örn: 905362438446, + işareti olmadan). Gönderilen numara: {phone_clean}. Hata: {original_error_message}"
                        elif "message" in original_error_message.lower() or "body" in original_error_message.lower() or "text" in original_error_message.lower():
                            error_message = f"Geçersiz mesaj içeriği. Mesaj boş olmamalı ve maksimum 4096 karakter olmalı. Hata: {original_error_message}"
                        elif "type" in original_error_message.lower():
                            error_message = f"Geçersiz mesaj tipi. WhatsApp Business API sadece onaylanmış mesaj şablonları veya serbest metin mesajları (hesap onaylandıysa) destekler. Hata: {original_error_message}"
                        else:
                            error_message = f"Geçersiz parametreler. Hata: {original_error_message}. Gönderilen telefon: {phone_clean}, Mesaj uzunluğu: {len(message) if message else 0}"
                    else:
                        error_message = f"Geçersiz parametreler: {original_error_message}. Gönderilen telefon: {phone_clean}, Mesaj uzunluğu: {len(message) if message else 0}"
                else:
                    error_message = f"{original_error_message} (Kod: {error_code})"
                
                return False, f"Mesaj gönderilemedi (Kod: {error_code}): {error_message}"
            except:
                return False, f"Mesaj gönderilemedi: {response.text}"
            
    except Exception as e:
        print(f"[WhatsApp] Exception: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Hata: {str(e)}"

# Mesaj Sayacı API (Sidebar Badge için)
@app.route('/api/mesaj-sayaci')
@login_required
def api_mesaj_sayaci():
    """WhatsApp ve Instagram okunmamış mesaj sayılarını döndür"""
    try:
        firma_id = session.get('firma_id')
        
        # WhatsApp okunmamış mesaj sayısı
        whatsapp_count = 0
        if session.get('whatsapp_modulu', False):
            try:
                whatsapp_count = WhatsAppMesaj.query.filter_by(
                    FirmaID=firma_id, 
                    Yyon='GELEN',
                    Okundu=False
                ).count()
            except Exception:
                whatsapp_count = 0
        
        # Instagram okunmamış mesaj sayısı
        instagram_count = 0
        if session.get('instagram_modulu', False):
            try:
                instagram_count = InstagramMesaj.query.filter_by(
                    FirmaID=firma_id, 
                    Yyon='GELEN',
                    Okundu=False
                ).count()
            except Exception:
                instagram_count = 0
        
        return jsonify({
            'success': True,
            'whatsapp': whatsapp_count,
            'instagram': instagram_count
        })
        
    except Exception as e:
        return jsonify({'success': True, 'whatsapp': 0, 'instagram': 0})

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
    # Debug: AJAX isteği kontrolü
    x_requested_with = request.headers.get('X-Requested-With', '')
    is_ajax = request.is_json or x_requested_with == 'XMLHttpRequest'
    print(f"[randevu_ekle] Method: {request.method}, is_json: {request.is_json}, X-Requested-With: '{x_requested_with}', is_ajax: {is_ajax}")
    print(f"[randevu_ekle] All headers: {dict(request.headers)}")
    
    if request.method == 'POST':
        # JSON veya form verilerini al
        if request.is_json or (request.headers.get('Content-Type', '').startswith('application/json')):
            try:
                data = request.get_json() if request.is_json else request.get_json(force=True)
                print(f"[randevu_ekle] JSON data alındı: {data}")
                tarih_gun = data.get('tarih_gun')
                saat = data.get('saat') or data.get('selected_saat')
                defter_id = data.get('defter_id')
                if isinstance(defter_id, str):
                    defter_id = int(defter_id) if defter_id else None
                referans_id = data.get('referans_id')
                if isinstance(referans_id, str):
                    referans_id = int(referans_id) if referans_id else None
                islem_id = data.get('islem_id')
                if isinstance(islem_id, str):
                    islem_id = int(islem_id) if islem_id else None
                gorev_id = data.get('gorev_id')
                if isinstance(gorev_id, str):
                    gorev_id = int(gorev_id) if gorev_id else None
                musteri_adi = data.get('musteri_adi', '')
                musteri_soyadi = data.get('musteri_soyadi', '')
                telefon = data.get('telefon', '')
                email = data.get('email', '')
                aciklama = data.get('aciklama', '') or data.get('randevu_aciklamasi', '')
                randevu_suresi = int(data.get('sure', 60))
                randevu_baslik = data.get('randevu_baslik', '')
                secilen_musteri_id = data.get('secilen_musteri_id')
            except Exception as e:
                print(f"[randevu_ekle] JSON parse hatası: {e}")
                # JSON parse hatası durumunda form verilerini dene
                data = None
        else:
            data = None
        
        if not data:
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
            aciklama = request.form.get('aciklama', '') or request.form.get('randevu_aciklamasi', '')
            randevu_suresi = int(request.form.get('sure', 60))
            randevu_baslik = request.form.get('randevu_baslik', '')
            secilen_musteri_id = request.form.get('secilen_musteri_id')
        if not tarih_gun or not saat or not defter_id:
            error_msg = 'Lütfen tarih, saat ve randevu defteri seçin'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg}), 400
            flash(error_msg, 'error')
            return redirect(url_for('randevu_ekle'))
        # Referans istege bagli; yok ise "Yok" kullan
        try:
            randevu_dt = datetime.strptime(f"{tarih_gun} {saat}", '%Y-%m-%d %H:%M')
        except ValueError:
            error_msg = 'Tarih/saat formatı geçersiz'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg}), 400
            flash(error_msg, 'error')
            return redirect(url_for('randevu_ekle'))

        # Geçmiş tarih/saat için koruma
        now_local = datetime.now()
        if randevu_dt < now_local:
            error_msg = 'Geçmiş tarihe veya saate randevu verilemez'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg}), 400
            flash(error_msg, 'error')
            return redirect(url_for('randevu_ekle'))

        # Seçilen defteri kontrol et
        defter_ayar = RandevuDefterAyar.query.filter_by(
            AyarID=defter_id, 
            FirmaID=session['firma_id'], 
            Aktif=True
        ).first()
        if not defter_ayar:
            error_msg = 'Seçilen randevu defteri bulunamadı'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg}), 400
            flash(error_msg, 'error')
            return redirect(url_for('randevu_ekle'))
        
        # Süre validation - slot dakikasının katı olmalı
        if randevu_suresi % defter_ayar.SlotDakika != 0:
            error_msg = f'Randevu süresi {defter_ayar.SlotDakika} dakikanın katları olmalı'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg}), 400
            flash(error_msg, 'error')
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
                error_msg = 'Seçilen saat aralığında mevcut randevu var'
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': error_msg}), 400
                flash(error_msg, 'error')
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
            error_msg = 'Seçilen saat aralığı kapalı (bloklandı)'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg}), 400
            flash(error_msg, 'error')
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
                error_msg = 'Seçilen müşteri bulunamadı'
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': error_msg}), 400
                flash(error_msg, 'error')
                return redirect(url_for('randevu_ekle'))
            
            # Müşteri bilgilerini veritabanından al (form'dan gelenler varsa onları kullan)
            musteri_adi = request.form.get('musteri_adi', '') or musteri.MusteriAdi
            musteri_soyadi = request.form.get('musteri_soyadi', '') or musteri.MusteriSoyadi
            telefon = request.form.get('telefon', '') or musteri.Telefon or ''
            email = request.form.get('email', '') or musteri.Email or ''
            
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
        
        # Randevu başlığını belirle: önce form'dan gelen, sonra referans, sonra görev, son olarak varsayılan
        if randevu_baslik:
            randevu_baslik_final = randevu_baslik
        elif ref:
            randevu_baslik_final = ref.Ad
        elif gorev_baslik and gorev_baslik != 'Yok':
            randevu_baslik_final = gorev_baslik
        else:
            randevu_baslik_final = f"{musteri_adi} {musteri_soyadi} Randevusu" if musteri_adi else "Yok"
        
        randevu = Randevu(
            RandevuBaslik=randevu_baslik_final,
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
            print(f"Randevu oluşturma hatası: {e}")
            import traceback
            traceback.print_exc()
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
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
        
        # AJAX isteği kontrolü
        print(f"[randevu_ekle] POST sonu - is_json: {request.is_json}, X-Requested-With: {request.headers.get('X-Requested-With')}, is_ajax: {is_ajax}")
        if is_ajax:
            print("[randevu_ekle] JSON response döndürülüyor")
            return jsonify({'success': True, 'message': 'Randevu başarıyla oluşturuldu!'})
        print("[randevu_ekle] Redirect yapılıyor")
        flash('Randevu başarıyla oluşturuldu!', 'success')
        return redirect(url_for('randevular'))
    # GET isteği
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuReferans.Ad).all()
    
    # Müşterileri al
    musteriler = Musteri.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(Musteri.MusteriAdi, Musteri.MusteriSoyadi).all()
    
    # Müşteri kategorilerini al - önce tüm kategorileri kontrol et
    all_kategoriler = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id']
    ).all()
    print(f"Firma {session['firma_id']} için toplam kategori sayısı (Aktif olmayanlar dahil): {len(all_kategoriler)}")
    
    # Aktif kategorileri al
    musteri_kategoriler = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id'],
        Aktif=True
    ).order_by(MusteriKategori.KategoriAdi).all()
    print(f"Firma {session['firma_id']} için aktif kategori sayısı: {len(musteri_kategoriler)}")
    
    # Eğer kategori yoksa varsayılan kategori oluştur
    if not musteri_kategoriler:
        print(f"Firma {session['firma_id']} için kategori bulunamadı, varsayılan kategori oluşturuluyor...")
        varsayilan_kategori = MusteriKategori(
            FirmaID=session['firma_id'],
            KategoriAdi='Normal Müşteri',
            Renk='#28a745',
            Aciklama='Standart müşteri kategorisi',
            Aktif=True
        )
        db.session.add(varsayilan_kategori)
        try:
            db.session.commit()
            musteri_kategoriler = [varsayilan_kategori]
            print(f"Varsayılan kategori başarıyla oluşturuldu: KategoriID={varsayilan_kategori.KategoriID}, Ad={varsayilan_kategori.KategoriAdi}")
        except Exception as e:
            db.session.rollback()
            print(f"Varsayılan kategori oluşturulurken hata: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"Firma {session['firma_id']} için {len(musteri_kategoriler)} kategori bulundu: {[k.KategoriAdi for k in musteri_kategoriler]}")
    
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
    print(f"[randevu_ekle] get_countries() döndü: {len(countries) if countries else 0} ülke")
    if countries and len(countries) > 0:
        # countries bir dict listesi olmalı
        if isinstance(countries[0], dict):
            print(f"[randevu_ekle] İlk 5 ülke: {[c.get('name', 'N/A') for c in countries[:5]]}")
            print(f"[randevu_ekle] Son 5 ülke: {[c.get('name', 'N/A') for c in countries[-5:]]}")
        else:
            print(f"[randevu_ekle] UYARI: countries dict listesi değil, tip: {type(countries[0])}")
    else:
        print(f"[randevu_ekle] UYARI: countries boş veya None!")
    
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
        
        # Görevleri getir (sadece randevu bazlı görevler)
        query = Todo.query.filter_by(KullaniciID=user_id, Tip='Randevu')
        
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
                        db.func.date(Todo.BitisTarihi) == filter_date,
                        db.func.date(Todo.HatirlatmaTarihi) == filter_date
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

# ==================== TODO BİLDİRİM SİSTEMİ ====================



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
    # Önce veritabanından dosya yolunu kontrol et
    kullanici = Kullanici.query.get(user_id)
    if kullanici and kullanici.ProfilFotografi:
        # Veritabanından gelen dosya yolunu kullan
        avatar_path = os.path.join('static', kullanici.ProfilFotografi)
        if os.path.exists(avatar_path) and os.path.isfile(avatar_path):
            return send_file(avatar_path, mimetype='image/jpeg')
    
    # Veritabanında yol yoksa, eski yöntemle kontrol et (geriye dönük uyumluluk)
    avatar_path = os.path.join('static', 'uploads', 'users', f'user_{user_id}.jpg')
    if os.path.exists(avatar_path) and os.path.isfile(avatar_path):
        # Dosya varsa ama veritabanında yoksa, veritabanına kaydet
        if kullanici:
            relative_path = f'uploads/users/user_{user_id}.jpg'
            kullanici.ProfilFotografi = relative_path
            db.session.commit()
        return send_file(avatar_path, mimetype='image/jpeg')
    
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
        # Önce SistemAyarlar'dan veritabanı ayarlarını yükle
        # Bu, gerçek veritabanı bağlantısını kurar (MySQL/MSSQL)
        print("[INFO] SistemAyarlar'dan veritabani ayarlari yukleniyor...")
        new_engine = initialize_database_from_settings()
        print("[OK] Veritabani ayarlari yukleme islemi tamamlandi.\n")
        
        # ProfilFotografi kolonunu kontrol et ve ekle (gerekirse)
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('Kullanicilar')]
            
            if 'ProfilFotografi' not in columns:
                print("[MIGRATION] ProfilFotografi kolonu bulunamadi, ekleniyor...")
                dialect_name = db.engine.dialect.name
                
                if dialect_name == 'mysql':
                    with db.engine.connect() as conn:
                        conn.execute(text("""
                            ALTER TABLE Kullanicilar 
                            ADD COLUMN ProfilFotografi VARCHAR(500) NULL 
                            AFTER LogModulu
                        """))
                        conn.commit()
                    print("[OK] ProfilFotografi kolonu MySQL'de eklendi!")
                elif dialect_name == 'mssql':
                    with db.engine.connect() as conn:
                        conn.execute(text("""
                            ALTER TABLE Kullanicilar 
                            ADD ProfilFotografi NVARCHAR(500) NULL
                        """))
                        conn.commit()
                    print("[OK] ProfilFotografi kolonu MSSQL'de eklendi!")
                else:
                    print(f"[WARN] ProfilFotografi kolonu eklenemedi - desteklenmeyen veritabani: {dialect_name}")
            else:
                print("[OK] ProfilFotografi kolonu mevcut.")
        except Exception as e:
            error_msg = str(e).lower()
            if 'duplicate' in error_msg or 'already exists' in error_msg:
                print("[INFO] ProfilFotografi kolonu zaten mevcut.")
            else:
                print(f"[WARN] ProfilFotografi kolonu kontrol edilemedi: {e}")
                # Hata olsa bile devam et
        
        # SistemAyarlar'dan bağlantı kurulduktan sonra tabloları kontrol et/oluştur
        print("[LOAD] Veritabani tablolari kontrol ediliyor...")
        
        # Yeni engine'i kullan (eğer döndürüldüyse)
        actual_engine = new_engine if new_engine else None
        
        # Eğer new_engine yoksa, db.get_engine() ile kontrol et
        if not actual_engine:
            try:
                actual_engine = db.get_engine()
                actual_dialect = actual_engine.dialect.name if hasattr(actual_engine, 'dialect') else None
                print(f"[DEBUG] Veritabani dialect: {actual_dialect}")
            except Exception as engine_check_err:
                print(f"[WARN] Engine kontrolu yapilamadi: {engine_check_err}")
                actual_engine = None
        
        # Flask-SQLAlchemy zaten sadece eksik tabloları oluşturur, mevcut tabloları değiştirmez
        try:
            # db.create_all() çağrısı - MySQL veya MSSQL engine kullanılacak
            # Flask-SQLAlchemy'nin internal get_engine() çağrısını bypass etmek için
            # doğrudan SQLAlchemy metadata'sını kullan
            if actual_engine:
                print(f"[DEBUG] db.metadata.create_all() yeni engine ile cagriliyor (dialect: {actual_engine.dialect.name})")
                # Doğrudan SQLAlchemy metadata'sını kullan - Flask-SQLAlchemy bypass
                db.metadata.create_all(bind=actual_engine, checkfirst=True)
            else:
                print("[WARN] Engine bulunamadi, db.create_all() varsayilan engine ile cagriliyor")
                # Engine yoksa, db.get_engine() ile al
                try:
                    fallback_engine = db.get_engine()
                    print(f"[DEBUG] Fallback engine dialect: {fallback_engine.dialect.name}")
                    db.metadata.create_all(bind=fallback_engine, checkfirst=True)
                except Exception as fallback_err:
                    print(f"[WARN] Fallback engine alinamadi: {fallback_err}")
                    # Son çare: db.create_all() kullan
                    db.create_all()
            print("[OK] Tablo kontrolu tamamlandi.\n")
        except Exception as create_err:
            print(f"[WARN] Tablo olusturma sirasinda hata: {create_err}")
            import traceback
            traceback.print_exc()
            print("[INFO] Devam ediliyor...")
    
    # Hatirlatma worker'i arka planda baslat
    worker_thread = threading.Thread(target=reminder_worker, args=(app,), daemon=True)
    worker_thread.start()
    
    # Todo hatırlatma worker'ını başlat
    todo_worker_thread = threading.Thread(target=todo_reminder_worker, args=(app,), daemon=True)
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
