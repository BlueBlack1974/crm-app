#!/usr/bin/env python3
"""
MySQL Veritabanı Oluşturma Script'i
"""

import sys
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# MySQL bağlantı bilgileri
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'Sa19977991'
MYSQL_DATABASE = 'Crandyx_CRM_DB'

def create_mysql_database():
    """MySQL veritabanını ve tablolarını oluştur"""
    
    print("=" * 60)
    print("MySQL Veritabani Olusturma")
    print("=" * 60)
    
    try:
        # Önce MySQL'e bağlan (veritabanı olmadan)
        print(f"\n[1/3] MySQL sunucusuna baglaniliyor...")
        password_encoded = quote_plus(MYSQL_PASSWORD)
        username_encoded = quote_plus(MYSQL_USER)
        
        # Veritabanı olmadan bağlan
        connection_string = f"mysql+pymysql://{username_encoded}:{password_encoded}@{MYSQL_HOST}:{MYSQL_PORT}/?charset=utf8mb4"
        
        engine = create_engine(connection_string, pool_pre_ping=True)
        
        with engine.connect() as conn:
            # Veritabanının var olup olmadığını kontrol et
            print(f"[2/3] Veritabani kontrol ediliyor: {MYSQL_DATABASE}")
            result = conn.execute(text(f"SHOW DATABASES LIKE '{MYSQL_DATABASE}'"))
            db_exists = result.fetchone()
            
            if db_exists:
                print(f"[INFO] Veritabani zaten mevcut: {MYSQL_DATABASE}")
                try:
                    response = input("Veritabanini silip yeniden olusturmak ister misiniz? (E/h): ").strip().lower()
                except:
                    response = 'h'
                if response == 'e':
                    print(f"[INFO] Veritabani siliniyor...")
                    with conn.begin():
                        conn.execute(text(f"DROP DATABASE IF EXISTS `{MYSQL_DATABASE}`"))
                    print(f"[OK] Veritabani silindi")
                else:
                    print("[INFO] Mevcut veritabani korunuyor, sadece tablolar kontrol edilecek")
            else:
                print(f"[INFO] Veritabani bulunamadi, olusturuluyor...")
            
            # Veritabanını oluştur
            print(f"[3/3] Veritabani olusturuluyor...")
            with conn.begin():
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            print(f"[OK] Veritabani olusturuldu: {MYSQL_DATABASE}")
        
        # Şimdi veritabanına bağlan ve script'i çalıştır
        print(f"\n[4/4] Tablolar olusturuluyor...")
        db_connection_string = f"mysql+pymysql://{username_encoded}:{password_encoded}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
        db_engine = create_engine(db_connection_string, pool_pre_ping=True)
        
        # SQL script'ini oku ve çalıştır
        sql_file = 'database/create_database_mysql.sql'
        
        try:
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # SQL script'ini statement'lara ayır (; ile ayrılmış)
            # MySQL'de USE komutu ve bazı özel durumları handle et
            statements = []
            current_statement = ""
            
            for line in sql_script.split('\n'):
                line = line.strip()
                # Yorumları ve boş satırları atla
                if line.startswith('--') or not line:
                    continue
                # USE komutunu atla (zaten bağlıyız)
                if line.upper().startswith('USE '):
                    continue
                # SELECT 'Mesaj' gibi son mesajları atla
                if line.upper().startswith("SELECT '"):
                    continue
                
                current_statement += line + " "
                
                # Eğer satır ; ile bitiyorsa statement'ı ekle
                if line.endswith(';'):
                    stmt = current_statement.strip()
                    if stmt and not stmt.startswith('--'):
                        statements.append(stmt)
                    current_statement = ""
            
            # Statement'ları çalıştır
            with db_engine.connect() as conn:
                executed = 0
                errors = 0
                with conn.begin():  # Transaction başlat
                    for stmt in statements:
                        try:
                            if stmt.strip():
                                conn.execute(text(stmt))
                                executed += 1
                        except Exception as e:
                            errors += 1
                            # Bazı hatalar normal (örneğin tablo zaten varsa)
                            error_msg = str(e).lower()
                            if "already exists" not in error_msg and "duplicate" not in error_msg and "exists" not in error_msg:
                                print(f"[UYARI] Statement hatasi: {e}")
                                print(f"   Statement: {stmt[:100]}...")
                
                print(f"[OK] {executed} SQL statement calistirildi")
                if errors > 0:
                    print(f"[INFO] {errors} statement atlandi (zaten mevcut)")
            
            # Son kontrol - tabloları listele
            print(f"\n[KONTROL] Olusturulan tablolar:")
            with db_engine.connect() as conn:
                result = conn.execute(text("SHOW TABLES"))
                tables = [row[0] for row in result.fetchall()]
                
                if tables:
                    print(f"   {len(tables)} tablo bulundu:")
                    for table in tables:
                        print(f"   [OK] {table}")
                else:
                    print("   [UYARI] Henuz tablo yok!")
            
            print("\n" + "=" * 60)
            print("[BASARILI] MySQL veritabani basariyla olusturuldu!")
            print("=" * 60)
            print(f"\nBaglanti bilgileri:")
            print(f"   Host: {MYSQL_HOST}")
            print(f"   Port: {MYSQL_PORT}")
            print(f"   Database: {MYSQL_DATABASE}")
            print(f"   Username: {MYSQL_USER}")
            print(f"\n.env dosyasi icin:")
            print(f"   DATABASE_URL=mysql+pymysql://{username_encoded}:{password_encoded}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4")
            
            return True
            
        except FileNotFoundError:
            print(f"[HATA] SQL dosyasi bulunamadi: {sql_file}")
            return False
        except Exception as e:
            print(f"[HATA] SQL script calistirma hatasi: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except ImportError:
        print("\n[HATA] PyMySQL paketi bulunamadi!")
        print("[COZUM] Su komutu calistirin: pip install PyMySQL")
        return False
        
    except Exception as e:
        print(f"\n[HATA] MySQL baglanti hatasi:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = create_mysql_database()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[IPTAL] Islem kullanici tarafindan iptal edildi.")
        sys.exit(1)

