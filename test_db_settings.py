#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Veritabanı ayarlarını SistemAyarlar tablosundan kontrol et"""

from app import app, db, get_database_uri_from_settings, SistemAyar
from sqlalchemy import create_engine, text, inspect
from urllib.parse import quote_plus

def test_database_settings():
    print("=" * 60)
    print("Veritabani Ayarlari Kontrol Ediliyor...")
    print("=" * 60)
    
    with app.app_context():
        try:
            # SistemAyarlar tablosunu kontrol et
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'SistemAyarlar' not in tables and 'sistemayarlar' not in [t.lower() for t in tables]:
                print("[ERROR] SistemAyarlar tablosu bulunamadi!")
                return
            
            # SistemAyarlar tablosundaki tüm ayarları listele
            print("\n[INFO] SistemAyarlar tablosundaki ayarlar:")
            print("-" * 60)
            
            settings = SistemAyar.query.all()
            if not settings:
                print("[WARN] SistemAyarlar tablosu bos!")
            else:
                for setting in settings:
                    # Şifre alanlarını maskele
                    value = setting.AyarDegeri
                    if 'password' in setting.AyarAdi.lower() and value:
                        value = value[:10] + "..." if len(value) > 10 else "***"
                    print(f"  {setting.AyarAdi}: {value}")
            
            # Veritabanı ayarlarını oku
            print("\n[INFO] Veritabani ayarlari okunuyor...")
            print("-" * 60)
            
            db_uri = get_database_uri_from_settings(debug=True)
            
            if db_uri:
                # URI'yi maskele
                if '@' in db_uri:
                    parts = db_uri.split('@')
                    if '://' in parts[0]:
                        protocol_user = parts[0].split('://')
                        if ':' in protocol_user[1]:
                            user_pass = protocol_user[1].split(':')
                            masked_uri = f"{protocol_user[0]}://{user_pass[0]}:***@{parts[1]}"
                        else:
                            masked_uri = f"{protocol_user[0]}://***@{parts[1]}"
                    else:
                        masked_uri = f"***@{parts[1]}"
                else:
                    masked_uri = db_uri
                
                print(f"[OK] Veritabani URI okundu: {masked_uri}")
                
                # Bağlantıyı test et
                print("\n[INFO] Veritabani baglantisi test ediliyor...")
                print("-" * 60)
                
                try:
                    test_engine = create_engine(db_uri, pool_pre_ping=True)
                    with test_engine.connect() as conn:
                        # Veritabanı bilgisini al
                        try:
                            current_db = conn.execute(text("SELECT DATABASE()")).scalar()
                            print(f"[OK] Aktif veritabani: {current_db}")
                        except:
                            pass
                        
                        # Tabloları listele
                        inspector = inspect(test_engine)
                        tables = inspector.get_table_names()
                        print(f"[OK] Veritabanindaki tablo sayisi: {len(tables)}")
                        print(f"[INFO] Ilk 10 tablo: {sorted(tables)[:10]}")
                        
                        # Kullanicilar tablosunu kontrol et
                        kullanicilar_table = None
                        for table in tables:
                            if table.lower() == 'kullanicilar':
                                kullanicilar_table = table
                                break
                        
                        if kullanicilar_table:
                            count = conn.execute(text(f"SELECT COUNT(*) FROM `{kullanicilar_table}`")).scalar()
                            print(f"[OK] Kullanicilar tablosu mevcut: {kullanicilar_table} ({count} kayit)")
                        else:
                            print(f"[WARN] Kullanicilar tablosu bulunamadi!")
                        
                        print("\n[OK] Veritabani baglantisi basarili!")
                        
                except Exception as test_err:
                    print(f"[ERROR] Veritabani baglanti testi basarisiz: {test_err}")
                    import traceback
                    traceback.print_exc()
            else:
                print("[WARN] Veritabani URI okunamadi!")
                print("[INFO] SistemAyarlar tablosunda veritabani ayarlari eksik olabilir.")
            
            # Mevcut Flask-SQLAlchemy engine'i kontrol et
            print("\n[INFO] Flask-SQLAlchemy engine kontrolu:")
            print("-" * 60)
            try:
                current_engine = db.get_engine()
                current_uri = str(current_engine.url)
                
                # URI'yi maskele
                if '@' in current_uri:
                    parts = current_uri.split('@')
                    if '://' in parts[0]:
                        protocol_user = parts[0].split('://')
                        if ':' in protocol_user[1]:
                            user_pass = protocol_user[1].split(':')
                            masked_current_uri = f"{protocol_user[0]}://{user_pass[0]}:***@{parts[1]}"
                        else:
                            masked_current_uri = f"{protocol_user[0]}://***@{parts[1]}"
                    else:
                        masked_current_uri = f"***@{parts[1]}"
                else:
                    masked_current_uri = current_uri
                
                print(f"[INFO] Mevcut engine URI: {masked_current_uri}")
                print(f"[INFO] Engine dialect: {current_engine.dialect.name}")
                
                # URI'lerin eşleşip eşleşmediğini kontrol et
                if db_uri:
                    # Sadece host, port, database karşılaştırması yap
                    def extract_db_info(uri):
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(uri)
                            return {
                                'host': parsed.hostname,
                                'port': parsed.port,
                                'database': parsed.path.lstrip('/').split('?')[0]
                            }
                        except:
                            return None
                    
                    settings_info = extract_db_info(db_uri)
                    current_info = extract_db_info(current_uri)
                    
                    if settings_info and current_info:
                        if (settings_info['host'] == current_info['host'] and
                            settings_info['port'] == current_info['port'] and
                            settings_info['database'] == current_info['database']):
                            print("[OK] Flask-SQLAlchemy engine, SistemAyarlar'daki ayarlarla eslesiyor!")
                        else:
                            print("[WARN] Flask-SQLAlchemy engine, SistemAyarlar'daki ayarlarla eslesmiyor!")
                            print(f"  SistemAyarlar: {settings_info['host']}:{settings_info['port']}/{settings_info['database']}")
                            print(f"  Mevcut engine: {current_info['host']}:{current_info['port']}/{current_info['database']}")
                
            except Exception as engine_err:
                print(f"[ERROR] Engine kontrolu basarisiz: {engine_err}")
                import traceback
                traceback.print_exc()
            
        except Exception as e:
            print(f"\n[ERROR] Hata olustu: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("[TAMAMLANDI] Kontrol islemi bitti.")
    print("=" * 60)

if __name__ == '__main__':
    test_database_settings()




