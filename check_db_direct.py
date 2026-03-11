from app.extensions import db
from app.models import Kullanici, FirmaEmailAyar

def check_settings():
    try:
        kullanicilar = Kullanici.query.all()
        print("--- KULLANICILAR ---")
        for k in kullanicilar:
            print(f"User: {k.KullaniciAdi}, FirmaID: {k.FirmaID}")
            
        ayarlar = FirmaEmailAyar.query.all()
        print("--- EMAIL AYARLARI ---")
        if not ayarlar:
            print("Hic ayar bulunamadi!")
        for a in ayarlar:
            print(f"AyarID: {a.AyarID}, FirmaID: {a.FirmaID}, SMTP: {a.SMTP_Sunucu}, Kullanici: {a.KullaniciAdi}")
            
    except Exception as e:
        print("HATA:", e)

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        # Eger initialize lazimsa... ama flask shell ortaminda normalde calisir.
        try:
            from app import initialize_database_from_settings
            initialize_database_from_settings()
        except:
            pass
        check_settings()
