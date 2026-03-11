import sys
from app import create_app, initialize_database_from_settings
from app.models import Kullanici, FirmaEmailAyar
from app.utils.helpers import send_password_reset_email

app = create_app()
with app.app_context():
    initialize_database_from_settings()

    user = Kullanici.query.first()
    if not user:
        print('Kullanici bulunamadi!')
        sys.exit(1)
        
    print(f'Test Edilen Kullanici: {user.KullaniciAdi}, FirmaID: {user.FirmaID}, Email: {user.Email}')
    
    settings = FirmaEmailAyar.query.filter_by(FirmaID=user.FirmaID).first()
    if not settings:
        print(f'HATA: FirmaID={user.FirmaID} icin E-Posta ayarlari DB\'de bulunamadi!')
    else:
        print(f'Ayarlar Bulundu -> Sunucu: {settings.SMTP_Sunucu}, Port: {settings.SMTP_Port}, Kullanici: {settings.KullaniciAdi}')
        print('E-Posta gonderme deneniyor...')
        success = send_password_reset_email(user.Email, 'http://test.com/reset', user.FirmaID)
        print(f'Sonuc: {success}')
