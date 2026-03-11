
import os
import sys
import importlib.util
from werkzeug.security import check_password_hash

# Import app.py as a module
spec = importlib.util.spec_from_file_location("main_app", "app.py")
main_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_app)

# Get app instance and initialize
app = main_app.app
main_app.initialize_app()

from app.models import Kullanici, SistemAyar

def check_state():
    with app.app_context():
        print(f"Current DB URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
        
        # Check SistemAyar
        try:
            db_type = SistemAyar.query.filter_by(AyarAdi='database_type').first()
            print(f"SistemAyar database_type: {db_type.AyarDegeri if db_type else 'None'}")
        except Exception as e:
            print(f"Error reading SistemAyar: {e}")

        # Check Admin User
        try:
            admin = Kullanici.query.filter_by(KullaniciAdi='admin').first()
            if admin:
                print(f"Admin user found: {admin.KullaniciAdi}")
                print(f"Admin password hash: {admin.Sifre}")
                
                # Check if password is '123'
                if check_password_hash(admin.Sifre, '123'):
                    print("Password is '123'")
                
                # Check if password is 'admin'
                elif check_password_hash(admin.Sifre, 'admin'):
                    print("Password is 'admin'")
                    
                # Check if password is 'admin123'
                elif check_password_hash(admin.Sifre, 'admin123'):
                    print("Password is 'admin123'")
                else:
                    print("Password is NOT '123', 'admin', or 'admin123'")
            else:
                print("Admin user NOT found!")
                
                # List all users
                users = Kullanici.query.all()
                print(f"Total users: {len(users)}")
                for u in users:
                    print(f"User: {u.KullaniciAdi}, ID: {u.KullaniciID}")
                    
        except Exception as e:
            print(f"Error checking users: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    check_state()
