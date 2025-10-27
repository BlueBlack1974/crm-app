#!/usr/bin/env python3

print("Script başladı...")

try:
    from app import app, db, Firma, TodoDurum
    print("Import başarılı")
    
    with app.app_context():
        print("App context içinde")
        
        # Mevcut firmayı bul
        firma = Firma.query.first()
        if not firma:
            print("Firma bulunamadı!")
            exit(1)
        
        print(f"Mevcut firma: {firma.FirmaAdi} (ID: {firma.FirmaID})")
        
        # Mevcut durumları kontrol et
        mevcut_durumlar = TodoDurum.query.filter_by(FirmaID=firma.FirmaID).all()
        print(f"Mevcut durum sayısı: {len(mevcut_durumlar)}")
        
        if len(mevcut_durumlar) == 0:
            # Durumları oluştur
            durum1 = TodoDurum(DurumAdi='Beklemede', Renk='#ffc107', Sira=1, Aktif=True, FirmaID=firma.FirmaID)
            durum2 = TodoDurum(DurumAdi='Devam Ediyor', Renk='#17a2b8', Sira=2, Aktif=True, FirmaID=firma.FirmaID)
            durum3 = TodoDurum(DurumAdi='Tamamlandı', Renk='#28a745', Sira=3, Aktif=True, FirmaID=firma.FirmaID)
            
            db.session.add(durum1)
            db.session.add(durum2)
            db.session.add(durum3)
            db.session.commit()
            print("Durumlar oluşturuldu")
        else:
            print("Durumlar zaten mevcut")
        
        # Kontrol et
        durumlar = TodoDurum.query.filter_by(FirmaID=firma.FirmaID).all()
        print(f"Toplam {len(durumlar)} durum bulundu:")
        for d in durumlar:
            print(f"  {d.DurumID}: {d.DurumAdi} (Firma: {d.FirmaID})")

except Exception as e:
    print(f"HATA: {e}")
    import traceback
    traceback.print_exc()


