"""
CRM Uygulamasi - Kurulum Scripti
"""

import os
import sys
import subprocess

def install_requirements():
    """Gerekli Python paketlerini yukle"""
    print("Gerekli Python paketleri yukleniyor...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Paketler basariyla yuklendi!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Paket yukleme hatasi: {e}")
        return False

def create_env_file():
    """Ornek .env dosyasi olustur"""
    if not os.path.exists('.env'):
        print(".env dosyasi olusturuluyor...")
        try:
            with open('env_example.txt', 'r', encoding='utf-8') as f:
                content = f.read()
            
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✓ .env dosyasi olusturuldu!")
            print("⚠️  Lutfen .env dosyasini duzenleyerek veritabani baglanti bilgilerini girin!")
            return True
        except Exception as e:
            print(f"✗ .env dosyasi olusturma hatasi: {e}")
            return False
    else:
        print("✓ .env dosyasi zaten mevcut!")
        return True

def check_database_script():
    """Veritabani script dosyasini kontrol et"""
    if os.path.exists('database/create_database.sql'):
        print("✓ Veritabani script dosyasi mevcut!")
        print("⚠️  Lutfen MSSQL Server'da database/create_database.sql dosyasini calistirin!")
        return True
    else:
        print("✗ Veritabani script dosyasi bulunamadi!")
        return False

def main():
    """Ana kurulum fonksiyonu"""
    print("=" * 50)
    print("CRM Uygulamasi - Kurulum Scripti")
    print("=" * 50)
    
    success = True
    
    # 1. Python paketlerini yukle
    if not install_requirements():
        success = False
    
    print()
    
    # 2. .env dosyasi olustur
    if not create_env_file():
        success = False
    
    print()
    
    # 3. Veritabani script kontrolu
    if not check_database_script():
        success = False
    
    print()
    print("=" * 50)
    
    if success:
        print("✓ Kurulum tamamlandi!")
        print()
        print("Sonraki adimlar:")
        print("1. .env dosyasini duzenleyin")
        print("2. MSSQL Server'da veritabani scriptini calistirin")
        print("3. python app.py ile uygulamayi baslatin")
        print()
        print("Varsayilan giris bilgileri:")
        print("Kullanici Adi: admin")
        print("Sifre: admin123")
    else:
        print("✗ Kurulum sirasinda hatalar olustu!")
        print("Lutfen hatalari duzelttikten sonra tekrar deneyin.")
    
    print("=" * 50)

if __name__ == "__main__":
    main()













