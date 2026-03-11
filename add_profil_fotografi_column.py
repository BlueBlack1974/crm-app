"""
ProfilFotografi kolonunu Kullanicilar tablosuna ekler.

Bu script, Kullanicilar tablosuna ProfilFotografi kolonunu ekler.
Eğer kolon zaten varsa, hata vermeden atlar.

Kullanım:
    python add_profil_fotografi_column.py
"""

import os
from app import app, db
from sqlalchemy import text, inspect

def add_profil_fotografi_column():
    """ProfilFotografi kolonunu Kullanicilar tablosuna ekle"""
    with app.app_context():
        print("=" * 60)
        print("ProfilFotografi Kolonu Ekleme Script'i")
        print("=" * 60)
        
        try:
            # Önce kolonun var olup olmadığını kontrol et
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('Kullanicilar')]
            
            if 'ProfilFotografi' in columns:
                print("[INFO] ProfilFotografi kolonu zaten mevcut!")
                return
            
            print("[INFO] ProfilFotografi kolonu ekleniyor...")
            
            # Dialect kontrolü
            dialect_name = db.engine.dialect.name
            
            if dialect_name == 'mysql':
                # MySQL için
                with db.engine.connect() as conn:
                    conn.execute(text("""
                        ALTER TABLE Kullanicilar 
                        ADD COLUMN ProfilFotografi VARCHAR(500) NULL 
                        AFTER LogModulu
                    """))
                    conn.commit()
                print("[OK] ProfilFotografi kolonu MySQL'de eklendi!")
                
            elif dialect_name == 'mssql':
                # MSSQL için
                with db.engine.connect() as conn:
                    conn.execute(text("""
                        ALTER TABLE Kullanicilar 
                        ADD ProfilFotografi NVARCHAR(500) NULL
                    """))
                    conn.commit()
                print("[OK] ProfilFotografi kolonu MSSQL'de eklendi!")
            else:
                print(f"[ERROR] Desteklenmeyen veritabani dialect: {dialect_name}")
                return
            
            # Kolonun eklendiğini doğrula
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('Kullanicilar')]
            if 'ProfilFotografi' in columns:
                print("[OK] ProfilFotografi kolonu basariyla eklendi ve dogrulandi!")
            else:
                print("[WARN] ProfilFotografi kolonu eklenmis gibi gorunuyor ama dogrulanamadi.")
                
        except Exception as e:
            # Eğer kolon zaten varsa, hata mesajında "Duplicate column" olabilir
            error_msg = str(e).lower()
            if 'duplicate' in error_msg or 'already exists' in error_msg:
                print("[INFO] ProfilFotografi kolonu zaten mevcut (hata mesajindan anlasildi).")
            else:
                print(f"[ERROR] Hata olustu: {e}")
                import traceback
                traceback.print_exc()
                raise
        
        print("=" * 60)

if __name__ == '__main__':
    try:
        add_profil_fotografi_column()
    except Exception as e:
        print(f"\n[ERROR] Script calistirilirken hata olustu: {e}")
        import traceback
        traceback.print_exc()
        exit(1)




