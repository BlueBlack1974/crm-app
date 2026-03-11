
import logging
from sqlalchemy import create_engine, text, inspect

# URI from logs
uri = "mssql+pyodbc://sa:19977991@localhost:1433/CRM_DB?driver=ODBC+Driver+17+for+SQL+Server"

print("Connecting with explicit URI...")
engine = create_engine(uri)

print("Inspecting properties...")
inspector = inspect(engine)
columns = inspector.get_columns('Kullanicilar')
col_names = [c['name'] for c in columns]
print(f"Columns: {col_names}")

missing = []
if 'WhatsAppModulu' not in col_names: missing.append('WhatsAppModulu')
if 'InstagramModulu' not in col_names: missing.append('InstagramModulu')

if missing:
    print(f"MISSING: {missing}")
    with engine.connect() as conn:
        with conn.begin():
            for col in missing:
                print(f"Adding {col}...")
                conn.execute(text(f"ALTER TABLE Kullanicilar ADD {col} BIT DEFAULT 0 WITH VALUES"))
                # Also set to 1 for 'fatih'
                conn.execute(text(f"UPDATE Kullanicilar SET {col} = 1 WHERE KullaniciAdi = 'fatih'"))
    print("Fixed.")
else:
    print("Columns exist.")
    # Ensure fatih has them
    with engine.connect() as conn:
        with conn.begin():
            print("Ensuring fatih has permissions...")
            conn.execute(text("UPDATE Kullanicilar SET WhatsAppModulu = 1, InstagramModulu = 1 WHERE KullaniciAdi = 'fatih'"))
    print("Permissions updated for fatih.")
