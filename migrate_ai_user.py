import os
import sys
import importlib.util
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("main_app", "app.py")
main_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_app)

app = main_app.initialize_app()
with app.app_context():
    from app.extensions import db
    dialect = db.engine.dialect.name
    print(f'Dialect is: {dialect}')
    
    if dialect == 'mssql':
        try:
            db.session.execute(text("""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME='Kullanicilar' AND COLUMN_NAME='AIModulu'
                )
                ALTER TABLE Kullanicilar ADD AIModulu BIT NOT NULL DEFAULT 0
            """))
            db.session.commit()
            print('Successfully added/verified AIModulu in MSSQL')
        except Exception as e:
            db.session.rollback()
            print(f'Error adding AIModulu: {str(e)[:200]}')
        
    elif dialect == 'mysql':
        try:
            db.session.execute(text("""
                ALTER TABLE Kullanicilar ADD COLUMN AIModulu TINYINT(1) NOT NULL DEFAULT 0
            """))
            db.session.commit()
            print('Successfully added AIModulu in MySQL')
        except Exception as e:
            db.session.rollback()
            if '1060' in str(e) or 'duplicate' in str(e).lower():
                print('AIModulu already exists in MySQL')
            else:
                print(f'Error adding AIModulu: {str(e)[:200]}')
    
    print("Finished applying columns.")
