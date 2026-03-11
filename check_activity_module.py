"""
Aktivite Modülü Hızlı Kontrol Scripti
Bu script modülün çalışıp çalışmadığını kontrol eder.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("AKTİVİTE MODÜLÜ KONTROL")
print("=" * 60)

# 1. Dosya kontrolü
print("\n1. Dosya Kontrolü...")
files_to_check = [
    'app/models.py',
    'app/routes/aktivite.py',
    'app/templates/musteri_detay_modal.html',
    'database/create_activities_table_mysql.sql',
    'database/create_activities_table_mssql.sql'
]

for file in files_to_check:
    if os.path.exists(file):
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} BULUNAMADI!")

# 2. Model import kontrolü
print("\n2. Model Import Kontrolü...")
try:
    from app.models import Aktivite
    print("   ✅ Aktivite modeli import edilebildi")
except Exception as e:
    print(f"   ❌ Aktivite modeli import edilemedi: {e}")

# 3. Blueprint kontrolü
print("\n3. Blueprint Kontrolü...")
try:
    from app.routes.aktivite import aktivite_bp
    print("   ✅ aktivite_bp blueprint'i import edilebildi")
    print(f"   ✅ Blueprint name: {aktivite_bp.name}")
except Exception as e:
    print(f"   ❌ Blueprint import edilemedi: {e}")

# 4. __init__.py kontrolü
print("\n4. Blueprint Kayıt Kontrolü...")
try:
    with open('app/__init__.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'aktivite_bp' in content and 'app.register_blueprint(aktivite_bp)' in content:
            print("   ✅ Blueprint app/__init__.py'de kayıtlı")
        else:
            print("   ❌ Blueprint app/__init__.py'de kayıtlı DEĞİL!")
except Exception as e:
    print(f"   ❌ __init__.py okunamadı: {e}")

# 5. Route kontrolü
print("\n5. Route Kontrolü...")
try:
    with open('app/routes/aktivite.py', 'r', encoding='utf-8') as f:
        content = f.read()
        routes = [
            '@aktivite_bp.route(\'/api/aktiviteler\'',
            'def api_aktiviteler_liste',
            'def api_aktivite_olustur',
            'def get_customer_activities'
        ]
        for route in routes:
            if route in content:
                print(f"   ✅ {route} bulundu")
            else:
                print(f"   ❌ {route} bulunamadı!")
except Exception as e:
    print(f"   ❌ Route kontrolü yapılamadı: {e}")

# 6. Template kontrolü
print("\n6. Template Kontrolü...")
try:
    with open('app/templates/musteri_detay_modal.html', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'Activity Timeline' in content or 'aktivite' in content.lower():
            print("   ✅ Template'de aktivite bölümü var")
        else:
            print("   ❌ Template'de aktivite bölümü bulunamadı!")
except Exception as e:
    print(f"   ❌ Template okunamadı: {e}")

print("\n" + "=" * 60)
print("KONTROL TAMAMLANDI")
print("=" * 60)
print("\n⚠️  ÖNEMLİ: Veritabanı tablosu kontrolü için uygulamayı çalıştırıp")
print("   test_activity_module.py script'ini çalıştırın.")
print("\n📋 YAPILACAKLAR:")
print("   1. Migration script'ini çalıştırın:")
print("      mysql -u root -p crandyx_crm_db < database/create_activities_table_mysql.sql")
print("   2. Uygulamayı yeniden başlatın: python run.py")
print("   3. Müşteri detay sayfasına gidin ve timeline'ı kontrol edin")





