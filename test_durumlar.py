#!/usr/bin/env python3

from app import app, db, TodoDurum, Firma

with app.app_context():
    print("=== TÜM DURUMLAR ===")
    durumlar = TodoDurum.query.all()
    for d in durumlar:
        print(f"ID: {d.DurumID}, Ad: '{d.DurumAdi}', Firma: {d.FirmaID}")
    
    print("\n=== BEKLEMEDE DURUMLARI ===")
    beklemede = TodoDurum.query.filter_by(DurumAdi='Beklemede').all()
    print(f"Beklemede durum sayısı: {len(beklemede)}")
    for d in beklemede:
        print(f"ID: {d.DurumID}, Ad: '{d.DurumAdi}', Firma: {d.FirmaID}")
    
    print("\n=== FIRMALAR ===")
    firmalar = Firma.query.all()
    for f in firmalar:
        print(f"ID: {f.FirmaID}, Ad: '{f.FirmaAdi}'")
    
    print("\n=== FIRMA 1'İN DURUMLARI ===")
    firma1_durumlar = TodoDurum.query.filter_by(FirmaID=1).all()
    for d in firma1_durumlar:
        print(f"ID: {d.DurumID}, Ad: '{d.DurumAdi}', Firma: {d.FirmaID}")


