#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Kullanıcılar tablosunu kontrol et"""

from sqlalchemy import create_engine, text, inspect
from urllib.parse import quote_plus

# MySQL bağlantı bilgileri
MYSQL_CONFIG = {
    'server': 'localhost',
    'port': 3306,
    'database': 'crandyx_crm_db',
    'username': 'root',
    'password': 'Sa19977991',
    'charset': 'utf8mb4'
}

def build_mysql_uri(server, database, username, password, port=3306, charset='utf8mb4'):
    username_encoded = quote_plus(username) if username else ''
    password_encoded = quote_plus(password) if password else ''
    return f"mysql+pymysql://{username_encoded}:{password_encoded}@{server}:{port}/{database}?charset={charset}"

def check_users():
    print("=" * 60)
    print("Kullanicilar Tablosu Kontrol Ediliyor...")
    print("=" * 60)
    
    mysql_uri = build_mysql_uri(
        MYSQL_CONFIG['server'],
        MYSQL_CONFIG['database'],
        MYSQL_CONFIG['username'],
        MYSQL_CONFIG['password'],
        MYSQL_CONFIG['port'],
        MYSQL_CONFIG['charset']
    )
    
    print(f"Sunucu: {MYSQL_CONFIG['server']}:{MYSQL_CONFIG['port']}")
    print(f"Veritabani: {MYSQL_CONFIG['database']}")
    print(f"Kullanici: {MYSQL_CONFIG['username']}")
    print()
    
    try:
        # MySQL'e bağlan
        engine = create_engine(mysql_uri)
        
        # Bağlantıyı test et
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        print("[OK] MySQL baglantisi basarili!")
        print()
        
        # Tabloları kontrol et
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"[INFO] Veritabanindaki tablolar ({len(tables)} adet):")
        for table in sorted(tables):
            print(f"  - {table}")
        print()
        
        # Kullanicilar tablosunu kontrol et
        if 'Kullanicilar' in tables:
            print("[OK] Kullanicilar tablosu mevcut")
            
            with engine.connect() as conn:
                # Kayıt sayısı
                count = conn.execute(text("SELECT COUNT(*) FROM Kullanicilar")).scalar()
                print(f"[INFO] Kullanicilar tablosundaki kayit sayisi: {count}")
                
                if count > 0:
                    # Tüm kullanıcıları listele
                    users = conn.execute(text("""
                        SELECT KullaniciID, KullaniciAdi, Ad, Soyad, Email, Admin, Aktif 
                        FROM Kullanicilar
                        ORDER BY KullaniciID
                    """)).fetchall()
                    
                    print()
                    print("[INFO] Kullanicilar:")
                    print("-" * 80)
                    print(f"{'ID':<5} {'KullaniciAdi':<20} {'Ad Soyad':<25} {'Email':<30} {'Admin':<6} {'Aktif':<6}")
                    print("-" * 80)
                    for user in users:
                        admin_str = "Evet" if user[5] else "Hayir"
                        aktif_str = "Evet" if user[6] else "Hayir"
                        print(f"{user[0]:<5} {user[1]:<20} {user[2]} {user[3]:<20} {user[4]:<30} {admin_str:<6} {aktif_str:<6}")
                    
                    # Admin kullanıcısı var mı?
                    admin_exists = conn.execute(text("SELECT COUNT(*) FROM Kullanicilar WHERE KullaniciAdi = 'admin'")).scalar()
                    print()
                    if admin_exists > 0:
                        admin_user = conn.execute(text("""
                            SELECT KullaniciAdi, Sifre, Aktif 
                            FROM Kullanicilar 
                            WHERE KullaniciAdi = 'admin'
                        """)).fetchone()
                        print(f"[OK] Admin kullanici mevcut")
                        print(f"  - KullaniciAdi: {admin_user[0]}")
                        print(f"  - Sifre hash: {admin_user[1][:50]}...")
                        print(f"  - Aktif: {'Evet' if admin_user[2] else 'Hayir'}")
                    else:
                        print("[WARN] Admin kullanici bulunamadi!")
                else:
                    print("[WARN] Kullanicilar tablosu bos!")
                    
                # Firmalar tablosunu da kontrol et
                if 'Firmalar' in tables:
                    firma_count = conn.execute(text("SELECT COUNT(*) FROM Firmalar")).scalar()
                    print()
                    print(f"[INFO] Firmalar tablosundaki kayit sayisi: {firma_count}")
                    if firma_count > 0:
                        firmalar = conn.execute(text("SELECT FirmaID, FirmaAdi, FirmaKodu FROM Firmalar")).fetchall()
                        print("[INFO] Firmalar:")
                        for firma in firmalar:
                            print(f"  - ID: {firma[0]}, Ad: {firma[1]}, Kod: {firma[2]}")
                    else:
                        print("[WARN] Firmalar tablosu bos!")
        else:
            print("[ERROR] Kullanicilar tablosu bulunamadi!")
        
        print()
        print("=" * 60)
        print("[TAMAMLANDI] Kontrol islemi bitti.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] Hata olustu: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_users()




