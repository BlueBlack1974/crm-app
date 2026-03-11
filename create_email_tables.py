import os
import sys

# Proje dizinini yola ekle
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models import SifreSifirlamaToken

def init_new_tables():
    print("--------------------------------------------------")
    print("Yeni Veritabani Tablolari Olusturuluyor...")
    print("--------------------------------------------------")
    
    app = create_app()
    with app.app_context():
        try:
            print(f"[INFO] Mevcut veritabani baglantisi: {db.engine.url}")
            print("[INFO] SifreSifirlamaTokenlari tablosu denetleniyor...")
            
            # Sadece yeni tabloları (varsa atlayarak) oluşturur.
            SifreSifirlamaToken.__table__.create(db.engine, checkfirst=True)
            print("[OK] SifreSifirlamaTokenlari tablosu hazir.")
            
            print("--------------------------------------------------")
            print("[BASARILI] Tum yeni sifre/SMTP tablolari veritabaniniza islendi!")
            print("--------------------------------------------------")
            
        except Exception as e:
            print(f"[HATA] Tablolar olusturulurken bir sorun olustu: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    init_new_tables()
