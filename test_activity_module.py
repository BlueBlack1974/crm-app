"""
Aktivite Modülü Hızlı Test Scripti
Bu script modülün temel fonksiyonlarını test eder.
"""
import sys
import os

# Proje root'unu path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import Aktivite, Musteri, Kullanici, Firma
from datetime import datetime, timedelta

def test_activity_module():
    """Aktivite modülünü test et"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("AKTİVİTE MODÜLÜ TEST SÜRECİ")
        print("=" * 60)
        
        # 1. Tablo kontrolü
        print("\n1. Tablo Kontrolü...")
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'Aktiviteler' in tables or 'aktiviteler' in [t.lower() for t in tables]:
                print("✅ Aktiviteler tablosu mevcut")
            else:
                print("❌ Aktiviteler tablosu bulunamadı!")
                print("   Lütfen migration script'ini çalıştırın:")
                print("   mysql -u root -p crandyx_crm_db < database/create_activities_table_mysql.sql")
                return False
        except Exception as e:
            print(f"❌ Tablo kontrolü hatası: {e}")
            return False
        
        # 2. Model kontrolü
        print("\n2. Model Kontrolü...")
        try:
            aktivite_count = Aktivite.query.count()
            print(f"✅ Aktivite modeli çalışıyor (Toplam aktivite: {aktivite_count})")
        except Exception as e:
            print(f"❌ Model hatası: {e}")
            return False
        
        # 3. Müşteri kontrolü
        print("\n3. Müşteri Kontrolü...")
        try:
            musteri = Musteri.query.first()
            if musteri:
                print(f"✅ Test müşterisi bulundu: {musteri.MusteriAdi} {musteri.MusteriSoyadi} (ID: {musteri.MusteriID})")
            else:
                print("⚠️  Müşteri bulunamadı. Önce müşteri eklemeniz gerekiyor.")
                return False
        except Exception as e:
            print(f"❌ Müşteri kontrolü hatası: {e}")
            return False
        
        # 4. Aktivite oluşturma testi
        print("\n4. Aktivite Oluşturma Testi...")
        try:
            test_aktivite = Aktivite(
                MusteriID=musteri.MusteriID,
                FirmaID=musteri.FirmaID,
                AktiviteTipi='note',
                Baslik='Test Aktivitesi',
                Aciklama='Bu bir test aktivitesidir',
                AktiviteTarihi=datetime.now(),
                OlusturmaTarihi=datetime.now(),
                GuncellemeTarihi=datetime.now()
            )
            db.session.add(test_aktivite)
            db.session.commit()
            print(f"✅ Test aktivitesi oluşturuldu (ID: {test_aktivite.AktiviteID})")
            
            # Oluşturulan aktiviteyi sil
            db.session.delete(test_aktivite)
            db.session.commit()
            print("✅ Test aktivitesi temizlendi")
        except Exception as e:
            print(f"❌ Aktivite oluşturma hatası: {e}")
            db.session.rollback()
            return False
        
        # 5. Yardımcı fonksiyon testi
        print("\n5. Yardımcı Fonksiyon Testi...")
        try:
            from app.routes.aktivite import get_customer_activities
            aktiviteler = get_customer_activities(musteri.MusteriID, limit=5)
            print(f"✅ get_customer_activities() çalışıyor (Bulunan: {len(aktiviteler)} aktivite)")
        except Exception as e:
            print(f"❌ Yardımcı fonksiyon hatası: {e}")
            return False
        
        # 6. İlişki kontrolü
        print("\n6. İlişki Kontrolü...")
        try:
            musteri_aktiviteler = musteri.aktiviteler
            print(f"✅ Müşteri-aktivite ilişkisi çalışıyor (Müşterinin aktivite sayısı: {len(musteri_aktiviteler)})")
        except Exception as e:
            print(f"❌ İlişki hatası: {e}")
            return False
        
        # 7. Sorgu performans testi
        print("\n7. Sorgu Performans Testi...")
        try:
            import time
            start = time.time()
            aktiviteler = Aktivite.query.filter_by(MusteriID=musteri.MusteriID).order_by(Aktivite.AktiviteTarihi.desc()).limit(10).all()
            elapsed = time.time() - start
            print(f"✅ Sorgu performansı: {len(aktiviteler)} aktivite {elapsed*1000:.2f}ms'de getirildi")
        except Exception as e:
            print(f"❌ Performans testi hatası: {e}")
            return False
        
        print("\n" + "=" * 60)
        print("✅ TÜM TESTLER BAŞARILI!")
        print("=" * 60)
        print("\nSonraki adımlar:")
        print("1. Web arayüzünde müşteri detay sayfasına gidin")
        print("2. Timeline'ın göründüğünü kontrol edin")
        print("3. Yeni aktivite eklemeyi deneyin")
        print("4. Randevu/görev oluşturup otomatik aktivite oluşumunu kontrol edin")
        print("\nDetaylı test rehberi için: ACTIVITY_MODULE_TEST_GUIDE.md dosyasına bakın")
        
        return True

if __name__ == '__main__':
    success = test_activity_module()
    sys.exit(0 if success else 1)





