"""
Crandyx CRM - Konfigurasyon Dosyasi
"""

import os
from dotenv import load_dotenv

# .env dosyasini yukle
load_dotenv()

class Config:
    """Ana konfigurasyon sinifi"""
    
    # Flask ayarlari
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Veritabani ayarlari
    # MSSQL Server baglantisi icin
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mssql+pyodbc://sa:YourPassword@localhost/Crandyx_CRM_DB?driver=ODBC+Driver+17+for+SQL+Server'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 60,
    }
    
    # Uygulama ayarlari
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', 5000))
    
    # Guvenlik ayarlari
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Sayfalama ayarlari
    RANDEVULAR_PER_PAGE = 20
    KULLANICILAR_PER_PAGE = 20
    
    import os
    # Babel (Çeviri) ayarlari
    LANGUAGES = ['tr', 'en', 'fr', 'de']
    BABEL_DEFAULT_LOCALE = 'tr'
    BABEL_DEFAULT_TIMEZONE = 'Europe/Istanbul'
    BABEL_TRANSLATION_DIRECTORIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'translations')

class DevelopmentConfig(Config):
    """Gelistirme ortami konfigurasyonu"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'mssql+pyodbc://sa:YourPassword@localhost/Crandyx_CRM_DB?driver=ODBC+Driver+17+for+SQL+Server'

class ProductionConfig(Config):
    """Uretim ortami konfigurasyonu"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

class TestingConfig(Config):
    """Test ortami konfigurasyonu"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Konfigurasyon sozlugu
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}




