from app import app, db

try:
    with app.app_context():
        # Tüm tabloları oluştur
        db.create_all()
        print("Tablolar oluşturuldu!")
    
    # Firma oluştur
    from app import Firma
    firma = Firma(FirmaAdi='Test Firma', FirmaKodu='TEST')
    db.session.add(firma)
    db.session.commit()
    print(f"Firma oluşturuldu: ID {firma.FirmaID}")
    
    # Varsayılan durumları oluştur
    from app import TodoDurum
    default_durumlar = [
        {'DurumAdi': 'Beklemede', 'Renk': '#ffc107', 'Sira': 1, 'Aktif': True, 'FirmaID': firma.FirmaID},
        {'DurumAdi': 'Devam Ediyor', 'Renk': '#17a2b8', 'Sira': 2, 'Aktif': True, 'FirmaID': firma.FirmaID},
        {'DurumAdi': 'Tamamlandı', 'Renk': '#28a745', 'Sira': 3, 'Aktif': True, 'FirmaID': firma.FirmaID}
    ]
    
    for durum_data in default_durumlar:
        durum = TodoDurum(**durum_data)
        db.session.add(durum)
    
        db.session.commit()
        print("Varsayılan durumlar oluşturuldu!")
        
        # Kontrol et
        durumlar = TodoDurum.query.all()
        print("Oluşturulan durumlar:")
        for durum in durumlar:
            print(f"ID: {durum.DurumID}, Ad: {durum.DurumAdi}, Firma: {durum.FirmaID}")

except Exception as e:
    print(f"Hata: {e}")
    import traceback
    traceback.print_exc()
