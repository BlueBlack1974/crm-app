"""
Mevcut kullanıcı fotoğraflarının dosya yollarını veritabanına aktarır.

Bu script, static/uploads/users/ klasöründeki mevcut fotoğrafları tarar ve
dosya yollarını Kullanicilar tablosundaki ProfilFotografi kolonuna kaydeder.

Kullanım:
    python migrate_user_photos.py
"""

import os
import sys
from app import app, db, Kullanici

def migrate_user_photos():
    """Mevcut kullanıcı fotoğraflarının dosya yollarını veritabanına aktar"""
    with app.app_context():
        print("=" * 60)
        print("Kullanici Fotograflari Migrasyon Script'i")
        print("=" * 60)
        
        # Uploads klasörünü kontrol et
        uploads_dir = os.path.join('static', 'uploads', 'users')
        if not os.path.exists(uploads_dir):
            print(f"[WARN] {uploads_dir} klasoru bulunamadi!")
            return
        
        print(f"[INFO] {uploads_dir} klasoru taranıyor...")
        
        # Tüm kullanıcıları al
        kullanicilar = Kullanici.query.all()
        print(f"[INFO] Toplam {len(kullanicilar)} kullanici bulundu.")
        
        migrated_count = 0
        not_found_count = 0
        already_set_count = 0
        
        for kullanici in kullanicilar:
            # Dosya yolu formatı: uploads/users/user_{KullaniciID}.jpg
            relative_path = f'uploads/users/user_{kullanici.KullaniciID}.jpg'
            full_path = os.path.join('static', relative_path)
            
            # Eğer veritabanında zaten yol varsa, atla
            if kullanici.ProfilFotografi:
                already_set_count += 1
                print(f"[SKIP] Kullanici {kullanici.KullaniciID} ({kullanici.KullaniciAdi}) - zaten veritabaninda: {kullanici.ProfilFotografi}")
                continue
            
            # Dosya var mı kontrol et
            if os.path.exists(full_path) and os.path.isfile(full_path):
                try:
                    kullanici.ProfilFotografi = relative_path
                    db.session.commit()
                    migrated_count += 1
                    print(f"[OK] Kullanici {kullanici.KullaniciID} ({kullanici.KullaniciAdi}) - dosya yolu kaydedildi: {relative_path}")
                except Exception as e:
                    print(f"[ERROR] Kullanici {kullanici.KullaniciID} ({kullanici.KullaniciAdi}) - hata: {e}")
                    db.session.rollback()
            else:
                not_found_count += 1
                print(f"[INFO] Kullanici {kullanici.KullaniciID} ({kullanici.KullaniciAdi}) - dosya bulunamadi: {full_path}")
        
        print()
        print("=" * 60)
        print("Migrasyon Tamamlandi!")
        print("=" * 60)
        print(f"[OK] {migrated_count} kullanici fotografi veritabanina aktarildi")
        print(f"[SKIP] {already_set_count} kullanici zaten veritabaninda yol vardi")
        print(f"[INFO] {not_found_count} kullanici icin dosya bulunamadi")
        print("=" * 60)

if __name__ == '__main__':
    try:
        migrate_user_photos()
    except Exception as e:
        print(f"\n[ERROR] Hata olustu: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




