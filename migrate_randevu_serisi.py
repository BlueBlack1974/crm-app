import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Proje dizinini yola ekle
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# .env dosyasındaki değişkenleri yükle
load_dotenv()

from app import create_app
from app.extensions import db
from app.models import RandevuSeri, SistemAyar

def init_randevu_serisi():
    print("--------------------------------------------------")
    print("Randevu Serisi Veritabani Guncellemesi Basladi...")
    print("--------------------------------------------------")
    
    app = create_app()

    with app.app_context():
        print("--- 1. Settings Uzerinden URI Aliniyor ---")
        
        # Bypass the manual fallback we had, and let the app figure out the URI properly 
        # based on the environment and the DB settings
        import importlib.util
        spec = importlib.util.spec_from_file_location("app_module", os.path.join(os.path.dirname(__file__), "app.py"))
        app_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app_module)
        
        uri = app_module.get_database_uri_from_settings(debug=True)
        
        if not uri:
            print("Settings üzerinden URI alınamadı. İşlem iptal ediliyor.")
            sys.exit(1)
            
        print(f"Alınan Dinamik URI: {uri[:50]}...")
        
        print("--- 2. Yeni Engine Olusturuluyor ---")
        engine = create_engine(uri)
        dialect = engine.dialect.name
        print(f"[INFO] Mevcut veritabani tipi: {dialect}")
        
        print("--- 3. RandevuSerileri Tablosu Denetleniyor ---")
        try:
            RandevuSeri.__table__.create(engine, checkfirst=True)
            print("[OK] RandevuSerileri tablosu hazir.")
        except Exception as e:
            print(f"[HATA] Tablo olusturma hatasi: {e}")

        print("--- 4. Randevular Tablosuna Kolonlar Ekleniyor ---")
        with engine.begin() as conn:
            try:
                if dialect == 'mssql':
                    # Check if columns exist first for MSSQL
                    check_sql = text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Randevular' AND COLUMN_NAME = 'SeriID'")
                    result = conn.execute(check_sql).fetchone()
                    
                    if result:
                        print("[INFO] SeriID ve SeriNo kolonlari zaten mevcut. Geciliyor.")
                    else:
                        conn.execute(text("ALTER TABLE Randevular ADD SeriID INT NULL, SeriNo INT NULL"))
                        print("[OK] Kolonlar eklendi.")
                else:
                     conn.execute(text("ALTER TABLE Randevular ADD COLUMN SeriID INT NULL, ADD COLUMN SeriNo INT NULL"))
                     print("[OK] Kolonlar eklendi.")
            except Exception as e:
                print(f"[HATA] Kolon ekleme hatasi: {e}")
        
        print("--------------------------------------------------")
        print("[BASARILI] Randevu serisi veritabani guncellemesi tamamlandi!")
        print("--------------------------------------------------")

if __name__ == '__main__':
    init_randevu_serisi()
