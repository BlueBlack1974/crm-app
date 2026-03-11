import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models import SifreSifirlamaToken, FirmaEmailAyar
from app import initialize_database_from_settings

def sync_new_tables():
    print("MySQL ve MSSQL için veritabanı ayarlanıyor...")
    app = create_app()
    with app.app_context():
        try:
            # En son MySQL/MSSQL bağlantı ayarlarını okur.
            initialize_database_from_settings()
            
            print(f"[INFO] Engine URI: {db.engine.url}")
            
            # SifreSifirlamaTokenlari ve FirmaEmailAyar tablolarını engine üzerinden tarar ve eksikse oluşturur.
            SifreSifirlamaToken.__table__.create(db.engine, checkfirst=True)
            print("[OK] SifreSifirlamaTokenlari tablosu başarıyla oluşturuldu veya zaten var.")
            
            FirmaEmailAyar.__table__.create(db.engine, checkfirst=True)
            print("[OK] FirmaEmailAyar tablosu başarıyla oluşturuldu veya zaten var.")
            
        except Exception as e:
            print("[HATA]", e)

if __name__ == '__main__':
    sync_new_tables()
