#!/usr/bin/env python3

print("Script başladı...")

try:
    from app import app, db, Firma, TodoDurum
    print("Import başarılı")
    
    with app.app_context():
        print("App context içinde")
        
        # Tabloları oluştur
        db.create_all()
        print("Tablolar oluşturuldu")
        
        # Firma oluştur
        firma = Firma(FirmaAdi='Test Firma', FirmaKodu='TEST')
        db.session.add(firma)
        db.session.commit()
        print(f"Firma oluşturuldu: {firma.FirmaID}")
        
        # Durumları oluştur
        durum1 = TodoDurum(DurumAdi='Beklemede', Renk='#ffc107', Sira=1, Aktif=True, FirmaID=firma.FirmaID)
        durum2 = TodoDurum(DurumAdi='Devam Ediyor', Renk='#17a2b8', Sira=2, Aktif=True, FirmaID=firma.FirmaID)
        durum3 = TodoDurum(DurumAdi='Tamamlandı', Renk='#28a745', Sira=3, Aktif=True, FirmaID=firma.FirmaID)
        
        db.session.add(durum1)
        db.session.add(durum2)
        db.session.add(durum3)
        db.session.commit()
        print("Durumlar oluşturuldu")
        
        # Kontrol et
        durumlar = TodoDurum.query.all()
        print(f"Toplam {len(durumlar)} durum bulundu:")
        for d in durumlar:
            print(f"  {d.DurumID}: {d.DurumAdi} (Firma: {d.FirmaID})")

except Exception as e:
    print(f"HATA: {e}")
    import traceback
    traceback.print_exc()


