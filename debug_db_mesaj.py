import sys
import os
import importlib.util

# Force load app.py from current directory
file_path = os.path.join(os.getcwd(), "app.py")
spec = importlib.util.spec_from_file_location("app_module", file_path)
app_module = importlib.util.module_from_spec(spec)
sys.modules["app_module"] = app_module
spec.loader.exec_module(app_module)

# Get app and db from loaded module
app = app_module.app
db = app_module.db

from sqlalchemy import inspect, text


def check_mesaj_table():
    print("Checking Database Schema for 'KullaniciMesajlari'...")
    with app.app_context():
        # Get engine
        engine = db.engine
        print(f"Engine: {engine}")
        
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        
        if 'KullaniciMesajlari' not in table_names:
            print("ERROR: Table 'KullaniciMesajlari' DOES NOT EXIST!")
            return
            
        print("Table 'KullaniciMesajlari' exists.")
        columns = inspector.get_columns('KullaniciMesajlari')
        print(f"Found {len(columns)} columns:")
        for col in columns:
            print(f" - {col['name']} ({col['type']})")
            
        # Try a simple select
        print("\nTrying simple SELECT query...")
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT TOP 1 * FROM KullaniciMesajlari"))
                print("SELECT successful.")
                row = result.fetchone()
                if row:
                    print(f"Sample row: {row}")
                else:
                    print("Table is empty.")
        except Exception as e:
            print(f"SELECT failed: {e}")

if __name__ == "__main__":
    check_mesaj_table()
