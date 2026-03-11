
import logging
from app import create_app
from app.extensions import db
from sqlalchemy import inspect, text

app = create_app()

with app.app_context():
    print("Inspecting database...")
    inspector = inspect(db.engine)
    columns = inspector.get_columns('Kullanicilar')
    col_names = [c['name'] for c in columns]
    print(f"Columns in Kullanicilar: {col_names}")
    
    missing = []
    if 'WhatsAppModulu' not in col_names: missing.append('WhatsAppModulu')
    if 'InstagramModulu' not in col_names: missing.append('InstagramModulu')
    
    if missing:
        print(f"MISSING COLUMNS: {missing}")
        # Try to add them
        with db.engine.connect() as conn:
            with conn.begin():
                for col in missing:
                    print(f"Adding column {col}...")
                    # MSSQL syntax
                    conn.execute(text(f"ALTER TABLE Kullanicilar ADD {col} BIT DEFAULT 0 WITH VALUES"))
        print("Columns added successfully.")
    else:
        print("All columns present.")
