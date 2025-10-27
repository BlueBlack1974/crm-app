#!/usr/bin/env python3

from app import app, db, TodoDurum

with app.app_context():
    print("=== EKSİK DURUMLARI EKLEME ===")
    
    # Firma 2 için eksik durumları ekle
    firma2_durumlar = [
        {'DurumAdi': 'Devam Ediyor', 'Renk': '#17a2b8', 'Sira': 2, 'Aktif': True, 'FirmaID': 2},
        {'DurumAdi': 'Tamamlandı', 'Renk': '#28a745', 'Sira': 3, 'Aktif': True, 'FirmaID': 2}
    ]
    
    for durum_data in firma2_durumlar:
        # Durum zaten var mı kontrol et
        existing = TodoDurum.query.filter_by(
            DurumAdi=durum_data['DurumAdi'], 
            FirmaID=durum_data['FirmaID']
        ).first()
        
        if not existing:
            yeni_durum = TodoDurum(**durum_data)
            db.session.add(yeni_durum)
            print(f"Eklendi: {durum_data['DurumAdi']} (Firma: {durum_data['FirmaID']})")
        else:
            print(f"Zaten mevcut: {durum_data['DurumAdi']} (Firma: {durum_data['FirmaID']})")
    
    db.session.commit()
    print("Durumlar kaydedildi!")
    
    # Kontrol et
    print("\n=== FIRMA 2 DURUMLARI ===")
    firma2_durumlar = TodoDurum.query.filter_by(FirmaID=2).all()
    for d in firma2_durumlar:
        print(f"ID: {d.DurumID}, Ad: '{d.DurumAdi}', Firma: {d.FirmaID}")


