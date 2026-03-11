
import os
import sys
import importlib.util
from werkzeug.security import generate_password_hash, check_password_hash

# Import app.py as a module
spec = importlib.util.spec_from_file_location("main_app", "app.py")
main_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_app)

# Get app instance and initialize
app = main_app.app
main_app.initialize_app()

from app.models import Kullanici
from app.extensions import db

def set_password():
    with app.app_context():
        print(f"Connected to: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
        
        try:
            admin = Kullanici.query.filter_by(KullaniciAdi='admin').first()
            if admin:
                print(f"Admin user found (ID: {admin.KullaniciID}).")
                # Set password to 'admin123'
                admin.Sifre = generate_password_hash('admin123')
                db.session.commit()
                print("[OK] Admin password updated to 'admin123'.")
            else:
                print("[ERROR] Admin user not found!")
        except Exception as e:
            print(f"[ERROR] Password update failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    set_password()
