from app import create_app, db
from app.models import FirmaWhatsAppAyar, Firma

app = create_app()

with app.app_context():
    print("WhatsApp Ayarlari Kontrol Ediliyor...")
    firma = Firma.query.first()
    if not firma:
        print("Hata: Sistemde firma bulunamadi!")
    else:
        print(f"Firma: {firma.FirmaAdi} (ID: {firma.FirmaID})")
        whatsapp = FirmaWhatsAppAyar.query.filter_by(FirmaID=firma.FirmaID).first()
        if whatsapp:
            print("WhatsApp Ayari Bulundu:")
            print(f"- ID: {whatsapp.WhatsAppAyarID}")
            print(f"- Aktif: {whatsapp.Aktif}")
            print(f"- Phone ID: {whatsapp.PhoneNumberID}")
            print(f"- Access Token: {'***' + whatsapp.AccessToken[-5:] if whatsapp.AccessToken else 'YOK'}")
        else:
            print("Hata: Bu firma icin WhatsApp ayari bulunamadi!")

    # Request kutuphanesini kontrol et
    try:
        import requests
        print("Requests kutuphanesi yuklu.")
    except ImportError:
        print("Hata: requests kutuphanesi yuklu degil!")
