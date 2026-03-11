
import os
import sys
import importlib.util
from sqlalchemy import text

# Import app.py as a module
spec = importlib.util.spec_from_file_location("main_app", "app.py")
main_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_app)

# Get app instance and initialize
app = main_app.app
main_app.initialize_app()

from app.extensions import db

def migrate_instagram():
    with app.app_context():
        print(f"Connected to: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
        
        dialect = db.engine.dialect.name
        print(f"Database Dialect: {dialect}")

        # 1. Create New Tables (FirmaInstagramAyarlari, InstagramMesajlar)
        print("[INFO] Creating new tables if they don't exist...")
        db.create_all()
        print("[OK] db.create_all() executed.")

        # 2. Add Columns to Existing Tables
        try:
            with db.engine.begin() as conn:
                # ---------------------------------------------------------
                # Check/Add InstagramModulu to Kullanicilar
                # ---------------------------------------------------------
                try:
                    conn.execute(text("SELECT InstagramModulu FROM Kullanicilar WHERE 1=0"))
                    print("[OK] InstagramModulu column exists in Kullanicilar.")
                except Exception:
                    print("[INFO] InstagramModulu column missing in Kullanicilar. Adding...")
                    if dialect == 'mssql':
                        conn.execute(text("ALTER TABLE Kullanicilar ADD InstagramModulu BIT DEFAULT 0"))
                    else: # mysql/sqlite
                        conn.execute(text("ALTER TABLE Kullanicilar ADD COLUMN InstagramModulu BOOLEAN DEFAULT FALSE"))
                    print("[OK] InstagramModulu column added.")

                # ---------------------------------------------------------
                # Check/Add InstagramKullaniciAdi to Musteriler
                # ---------------------------------------------------------
                try:
                    conn.execute(text("SELECT InstagramKullaniciAdi FROM Musteriler WHERE 1=0"))
                    print("[OK] InstagramKullaniciAdi column exists in Musteriler.")
                except Exception:
                    print("[INFO] InstagramKullaniciAdi column missing in Musteriler. Adding...")
                    if dialect == 'mssql':
                        conn.execute(text("ALTER TABLE Musteriler ADD InstagramKullaniciAdi NVARCHAR(100) NULL"))
                    else: # mysql/sqlite
                        conn.execute(text("ALTER TABLE Musteriler ADD COLUMN InstagramKullaniciAdi VARCHAR(100) NULL"))
                    print("[OK] InstagramKullaniciAdi column added.")

        except Exception as e:
            print(f"[ERROR] Column migration failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    migrate_instagram()
