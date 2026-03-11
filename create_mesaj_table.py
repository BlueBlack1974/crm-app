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
from app.models import KullaniciMesaj

def create_table():
    print("Creating tables...")
    with app.app_context():
        # Create tables
        try:
            # Explicitly create the table for KullaniciMesaj
            table = KullaniciMesaj.__table__
            print(f"Creating table: {table.name}")
            table.create(db.engine)
            print("Table created successfully!")
        except Exception as e:
            print(f"Error creating table: {e}")

if __name__ == "__main__":
    create_table()
