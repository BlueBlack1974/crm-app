#!/usr/bin/env python3

from app import app, db, TodoDurum

with app.app_context():
    print("=== TÜM DURUMLAR ===")
    durumlar = TodoDurum.query.all()
    for d in durumlar:
        print(f"ID: {d.DurumID}, Ad: '{d.DurumAdi}', Firma: {d.FirmaID}")
    
    print("\n=== BEKLEMEDE ARAMA ===")
    beklemede = TodoDurum.query.filter(TodoDurum.DurumAdi.like('%Beklemede%')).all()
    print(f"Beklemede içeren durumlar: {len(beklemede)}")
    for d in beklemede:
        print(f"  ID: {d.DurumID}, Ad: '{d.DurumAdi}', Firma: {d.FirmaID}")
    
    print("\n=== DEVAM ARAMA ===")
    devam = TodoDurum.query.filter(TodoDurum.DurumAdi.like('%Devam%')).all()
    print(f"Devam içeren durumlar: {len(devam)}")
    for d in devam:
        print(f"  ID: {d.DurumID}, Ad: '{d.DurumAdi}', Firma: {d.FirmaID}")
    
    print("\n=== TAMAMLANDI ARAMA ===")
    tamamlandi = TodoDurum.query.filter(TodoDurum.DurumAdi.like('%Tamamlandı%')).all()
    print(f"Tamamlandı içeren durumlar: {len(tamamlandi)}")
    for d in tamamlandi:
        print(f"  ID: {d.DurumID}, Ad: '{d.DurumAdi}', Firma: {d.FirmaID}")
    
    print("\n=== TAMAM ARAMA ===")
    tamam = TodoDurum.query.filter(TodoDurum.DurumAdi.like('%Tamam%')).all()
    print(f"Tamam içeren durumlar: {len(tamam)}")
    for d in tamam:
        print(f"  ID: {d.DurumID}, Ad: '{d.DurumAdi}', Firma: {d.FirmaID}")


