
import os
import sys
import importlib.util
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

# Import app.py as a module
spec = importlib.util.spec_from_file_location("main_app", "app.py")
main_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_app)

# Get app instance and initialize
app = main_app.app
main_app.initialize_app()

from app.models import Kullanici, SistemAyar, Firma
from app.extensions import db

def migrate():
    with app.app_context():
        print(f"Connected to: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
        
        dialect = db.engine.dialect.name
        print(f"Database Dialect: {dialect}")

        # 1. Check and Add Columns
        try:
            # Use begin() for auto-commit transaction
            with db.engine.begin() as conn:
                # Check for WhatsAppModulu
                try:
                    conn.execute(text("SELECT WhatsAppModulu FROM Kullanicilar WHERE 1=0"))
                    print("[OK] WhatsAppModulu column exists.")
                except Exception:
                    print("[INFO] WhatsAppModulu column missing. Adding...")
                    if dialect == 'mssql':
                        conn.execute(text("ALTER TABLE Kullanicilar ADD WhatsAppModulu BIT DEFAULT 0"))
                    else: # mysql
                        conn.execute(text("ALTER TABLE Kullanicilar ADD COLUMN WhatsAppModulu BOOLEAN DEFAULT FALSE"))
                    print("[OK] WhatsAppModulu column added.")

                # Check for ProfilFotografi
                try:
                    conn.execute(text("SELECT ProfilFotografi FROM Kullanicilar WHERE 1=0"))
                    print("[OK] ProfilFotografi column exists.")
                except Exception:
                    print("[INFO] ProfilFotografi column missing. Adding...")
                    if dialect == 'mssql':
                        conn.execute(text("ALTER TABLE Kullanicilar ADD ProfilFotografi NVARCHAR(500) NULL"))
                    else: # mysql
                        conn.execute(text("ALTER TABLE Kullanicilar ADD COLUMN ProfilFotografi VARCHAR(500) NULL"))
                    print("[OK] ProfilFotografi column added.")
                    
        except Exception as e:
            print(f"[ERROR] Column migration failed: {e}")
            # Don't return, try to fix user anyway if possible (though likely to fail if cols missing)
        
        # 2. Check/Fix Admin User
        try:
            # Re-query to ensure schema update is recognized (might need session refresh)
            db.session.expire_all()
            
            admin = Kullanici.query.filter_by(KullaniciAdi='admin').first()
            if not admin:
                print("[INFO] Admin user not found. Creating...")
                
                firma = Firma.query.first()
                if not firma:
                    print("[INFO] No company found. Creating default company...")
                    firma = Firma(FirmaAdi='Merkez', FirmaKodu='MRKZ', Aktif=True)
                    db.session.add(firma)
                    db.session.commit()
                
                admin = Kullanici(
                    KullaniciAdi='admin',
                    Sifre=generate_password_hash('123'),
                    Ad='System',
                    Soyad='Admin',
                    Email='admin@localhost',
                    FirmaID=firma.FirmaID,
                    Admin=True,
                    Aktif=True,
                    RaporlarModulu=True,
                    AyarlarModulu=True,
                    LogModulu=True,
                    WhatsAppModulu=True
                )
                db.session.add(admin)
                db.session.commit()
                print("[OK] Admin user created with password '123'.")
            else:
                print(f"[INFO] Admin user found (ID: {admin.KullaniciID}).")
                
                # Check if password is valid hash (simple check)
                is_hashed = admin.Sifre and (admin.Sifre.startswith('scrypt:') or admin.Sifre.startswith('pbkdf2:'))
                
                if not is_hashed:
                     print(f"[WARN] Admin password seems to be plain text: '{admin.Sifre}'")
                     # Update to hash
                     admin.Sifre = generate_password_hash(admin.Sifre if admin.Sifre else '123')
                     db.session.commit()
                     print("[OK] Admin password hashed.")
                
                # Verify known passwords (just for info)
                if check_password_hash(admin.Sifre, '123'):
                    print("[INFO] Admin password is '123'.")
                elif check_password_hash(admin.Sifre, 'admin'):
                    print("[INFO] Admin password is 'admin'.")
                else:
                    print("[INFO] Admin password is set (unknown hash). Keeping as is.")


        except Exception as e:
            print(f"[ERROR] User check/fix failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    migrate()
