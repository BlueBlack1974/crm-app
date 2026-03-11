import sys
import os
import requests
import traceback
import importlib.util

# Add current dir
sys.path.append(os.getcwd())

print("Debug Script (Direct Import) Basliyor...")

try:
    # Load app.py directly from file to avoid package conflict
    file_path = os.path.join(os.getcwd(), 'app.py')
    spec = importlib.util.spec_from_file_location("main_app", file_path)
    main_app = importlib.util.module_from_spec(spec)
    sys.modules["main_app"] = main_app
    spec.loader.exec_module(main_app)
    
    print("app.py dosyasindan import basarili.")
    
    # Get objects
    app = main_app.app
    db = main_app.db
    FirmaWhatsAppAyar = main_app.FirmaWhatsAppAyar
    
    # Try to get Firma. Usually it fits here or in models.
    # Try getting from main_app first
    if hasattr(main_app, 'Firma'):
        Firma = main_app.Firma
    else:
        # Try importing from app.models
        from app.models import Firma

except Exception as e:
    print(f"Import Hatasi: {e}")
    traceback.print_exc()
    sys.exit(1)

# Config
app.config['SQLALCHEMY_DATABASE_URI'] = 'mssql+pyodbc://sa:19977991@localhost:1433/CRM_DB?driver=ODBC+Driver+17+for+SQL+Server'

with app.app_context():
    print("DB Baglandisi Test Ediliyor...")
    try:
        firma = Firma.query.first()
        if not firma:
            print("HATA: Firma yok.")
        else:
            print(f"Firma: {firma.FirmaAdi}")
            whatsapp = FirmaWhatsAppAyar.query.filter_by(FirmaID=firma.FirmaID).first()
            if whatsapp:
                print(f"WhatsApp Ayar ID: {whatsapp.WhatsAppAyarID}")
                print(f"Token: {whatsapp.AccessToken[:10]}...")
                print(f"PhoneID: {whatsapp.PhoneNumberID}")
                
                # API Test
                url = f"https://graph.facebook.com/v18.0/{whatsapp.PhoneNumberID}"
                headers = {"Authorization": f"Bearer {whatsapp.AccessToken}"}
                print(f"API GET {url}...")
                r = requests.get(url, headers=headers)
                print(f"STATUS: {r.status_code}")
                if r.status_code != 200:
                    print(f"RESPONSE: {r.text}")
                else:
                    print("API TOKEN GECERLI.")
            else:
                print("WhatsApp ayari yok.")
    except Exception as e:
        print(f"Sorgu Hatasi: {e}")
        traceback.print_exc()
