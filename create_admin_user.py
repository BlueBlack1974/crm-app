#!/usr/bin/env python3
"""
Admin kullanıcısını oluştur veya şifresini güncelle
"""

from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from werkzeug.security import generate_password_hash, check_password_hash

MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'Sa19977991'
MYSQL_DATABASE = 'Crandyx_CRM_DB'

# Admin kullanıcı bilgileri
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
ADMIN_EMAIL = 'admin@anafirma.com'
ADMIN_AD = 'Admin'
ADMIN_SOYAD = 'Kullanici'

connection_string = f"mysql+pymysql://{quote_plus(MYSQL_USER)}:{quote_plus(MYSQL_PASSWORD)}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"

try:
    engine = create_engine(connection_string, pool_pre_ping=True)
    
    with engine.connect() as conn:
        print("=" * 60)
        print("Admin Kullanici Olusturma/Guncelleme")
        print("=" * 60)
        
        # Şifre hash'i oluştur
        print(f"\n[1/4] Sifre hash'i olusturuluyor...")
        password_hash = generate_password_hash(ADMIN_PASSWORD)
        print(f"[OK] Hash olusturuldu (uzunluk: {len(password_hash)})")
        
        # Mevcut kullanıcıyı kontrol et
        print(f"\n[2/4] Mevcut kullanici kontrol ediliyor...")
        result = conn.execute(
            text("SELECT KullaniciID, KullaniciAdi, Sifre FROM Kullanicilar WHERE KullaniciAdi = :username"),
            {'username': ADMIN_USERNAME}
        )
        existing_user = result.fetchone()
        
        with conn.begin():
            if existing_user:
                kullanici_id, kullanici_adi, mevcut_hash = existing_user
                print(f"[INFO] Kullanici mevcut: {kullanici_adi} (ID: {kullanici_id})")
                
                # Şifreyi güncelle
                print(f"\n[3/4] Sifre guncelleniyor...")
                conn.execute(
                    text("""
                        UPDATE Kullanicilar 
                        SET Sifre = :sifre, 
                            Email = :email,
                            Ad = :ad,
                            Soyad = :soyad,
                            Admin = 1,
                            Aktif = 1
                        WHERE KullaniciID = :kullanici_id
                    """),
                    {
                        'sifre': password_hash,
                        'email': ADMIN_EMAIL,
                        'ad': ADMIN_AD,
                        'soyad': ADMIN_SOYAD,
                        'kullanici_id': kullanici_id
                    }
                )
                print(f"[OK] Kullanici sifresi guncellendi")
                
                # FirmaID kontrolü ve güncelleme
                print(f"\n[4/4] Firma ayari kontrol ediliyor...")
                firma_result = conn.execute(text("SELECT FirmaID FROM Firmalar LIMIT 1"))
                firma = firma_result.fetchone()
                
                if firma:
                    firma_id = firma[0]
                    conn.execute(
                        text("UPDATE Kullanicilar SET FirmaID = :firma_id WHERE KullaniciID = :kullanici_id"),
                        {'firma_id': firma_id, 'kullanici_id': kullanici_id}
                    )
                    print(f"[OK] FirmaID guncellendi: {firma_id}")
            else:
                # Yeni kullanıcı oluştur
                print(f"[INFO] Yeni kullanici olusturuluyor...")
                
                # FirmaID al
                firma_result = conn.execute(text("SELECT FirmaID FROM Firmalar LIMIT 1"))
                firma = firma_result.fetchone()
                firma_id = firma[0] if firma else 1
                
                conn.execute(
                    text("""
                        INSERT INTO Kullanicilar 
                        (KullaniciAdi, Sifre, Ad, Soyad, Email, FirmaID, Admin, Aktif)
                        VALUES (:username, :sifre, :ad, :soyad, :email, :firma_id, 1, 1)
                    """),
                    {
                        'username': ADMIN_USERNAME,
                        'sifre': password_hash,
                        'ad': ADMIN_AD,
                        'soyad': ADMIN_SOYAD,
                        'email': ADMIN_EMAIL,
                        'firma_id': firma_id
                    }
                )
                print(f"[OK] Yeni kullanici olusturuldu")
                
                # Kullanıcı ID'yi al
                result = conn.execute(
                    text("SELECT KullaniciID FROM Kullanicilar WHERE KullaniciAdi = :username"),
                    {'username': ADMIN_USERNAME}
                )
                kullanici_id = result.fetchone()[0]
            
            # Yetkileri kontrol et ve ver
            print(f"\n[5/5] Yetkiler kontrol ediliyor...")
            yetki_result = conn.execute(
                text("""
                    SELECT COUNT(*) FROM KullaniciYetkileri 
                    WHERE KullaniciID = :kullanici_id
                """),
                {'kullanici_id': kullanici_id}
            )
            yetki_count = yetki_result.fetchone()[0]
            
            if yetki_count == 0:
                # Tüm yetkileri ver
                conn.execute(
                    text("""
                        INSERT INTO KullaniciYetkileri (KullaniciID, YetkiID)
                        SELECT :kullanici_id, YetkiID
                        FROM YetkiTipleri
                    """),
                    {'kullanici_id': kullanici_id}
                )
                print(f"[OK] Tum yetkiler verildi")
            else:
                print(f"[INFO] Zaten {yetki_count} yetki mevcut")
        
        # Son kontrol - kullanıcıyı doğrula
        print(f"\n[KONTROL] Kullanici bilgileri:")
        result = conn.execute(
            text("""
                SELECT KullaniciID, KullaniciAdi, Ad, Soyad, Email, Admin, Aktif, FirmaID
                FROM Kullanicilar 
                WHERE KullaniciAdi = :username
            """),
            {'username': ADMIN_USERNAME}
        )
        user = result.fetchone()
        
        if user:
            kullanici_id, username, ad, soyad, email, admin, aktif, firma_id = user
            print(f"  Kullanici ID: {kullanici_id}")
            print(f"  Kullanici Adi: {username}")
            print(f"  Ad Soyad: {ad} {soyad}")
            print(f"  Email: {email}")
            print(f"  Admin: {'Evet' if admin else 'Hayir'}")
            print(f"  Aktif: {'Evet' if aktif else 'Hayir'}")
            print(f"  Firma ID: {firma_id}")
            
            # Şifre testi
            result = conn.execute(
                text("SELECT Sifre FROM Kullanicilar WHERE KullaniciAdi = :username"),
                {'username': ADMIN_USERNAME}
            )
            saved_hash = result.fetchone()[0]
            if check_password_hash(saved_hash, ADMIN_PASSWORD):
                print(f"  [OK] Sifre dogrulandi!")
            else:
                print(f"  [UYARI] Sifre dogrulamasi basarisiz!")
        
        print("\n" + "=" * 60)
        print("[BASARILI] Admin kullanici hazir!")
        print("=" * 60)
        print(f"\nGiris bilgileri:")
        print(f"  Kullanici Adi: {ADMIN_USERNAME}")
        print(f"  Sifre: {ADMIN_PASSWORD}")
        print(f"\nhttp://localhost:5000 adresinden giris yapabilirsiniz.")
        
except Exception as e:
    print(f"\n[HATA] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

