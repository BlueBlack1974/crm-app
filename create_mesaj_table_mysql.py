import sys
import os
import importlib.util
from sqlalchemy import create_engine

# Force load app.py from current directory
file_path = os.path.join(os.getcwd(), "app.py")
spec = importlib.util.spec_from_file_location("app_module", file_path)
app_module = importlib.util.module_from_spec(spec)
sys.modules["app_module"] = app_module
spec.loader.exec_module(app_module)

# Get app and db from loaded module
from app.models import KullaniciMesaj

def create_table_mysql():
    print("Connecting to MySQL...")
    # Default MySQL URI found in app.py
    mysql_uri = 'mysql+pymysql://root:Sa19977991@localhost:3306/crandyx_crm_db?charset=utf8mb4'
    
    try:
        engine = create_engine(mysql_uri)
        print(f"Connected to: {mysql_uri.split('@')[1]}") # Hide password
        
        # Explicitly create the table using the model's metadata
        table = KullaniciMesaj.__table__
        print(f"Creating table: {table.name}")
        table.create(engine, checkfirst=True) # checkfirst=True prevents error if exists
        print("Table 'KullaniciMesajlari' created successfully (or already existed) in MySQL!")
        
    except Exception as e:
        print(f"Error creating table in MySQL: {e}")

if __name__ == "__main__":
    create_table_mysql()
