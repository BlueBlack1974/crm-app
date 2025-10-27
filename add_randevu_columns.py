#!/usr/bin/env python3

import pyodbc
from app import app

def add_randevu_columns():
    """Todo tablosuna randevu alanlarını ekle"""
    
    # Veritabanı bağlantı bilgileri
    server = 'localhost'
    database = 'CRM'
    username = 'sa'
    password = '123456'
    
    try:
        # Veritabanına bağlan
        conn = pyodbc.connect(
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={username};'
            f'PWD={password}'
        )
        cursor = conn.cursor()
        
        print("Veritabanına bağlandı...")
        
        # RandevuTarihi alanını ekle
        try:
            cursor.execute("ALTER TABLE Todos ADD RandevuTarihi DATE")
            print("RandevuTarihi alanı eklendi...")
        except pyodbc.Error as e:
            if "already exists" in str(e) or "duplicate" in str(e).lower():
                print("RandevuTarihi alanı zaten mevcut...")
            else:
                print(f"RandevuTarihi alanı eklenirken hata: {e}")
        
        # RandevuSaati alanını ekle
        try:
            cursor.execute("ALTER TABLE Todos ADD RandevuSaati NVARCHAR(10)")
            print("RandevuSaati alanı eklendi...")
        except pyodbc.Error as e:
            if "already exists" in str(e) or "duplicate" in str(e).lower():
                print("RandevuSaati alanı zaten mevcut...")
            else:
                print(f"RandevuSaati alanı eklenirken hata: {e}")
        
        # RandevuDefterID alanını ekle
        try:
            cursor.execute("ALTER TABLE Todos ADD RandevuDefterID INT")
            print("RandevuDefterID alanı eklendi...")
        except pyodbc.Error as e:
            if "already exists" in str(e) or "duplicate" in str(e).lower():
                print("RandevuDefterID alanı zaten mevcut...")
            else:
                print(f"RandevuDefterID alanı eklenirken hata: {e}")
        
        # Foreign key constraint ekle
        try:
            cursor.execute("""
                ALTER TABLE Todos 
                ADD CONSTRAINT FK_Todos_RandevuDefterID 
                FOREIGN KEY (RandevuDefterID) REFERENCES Ayarlar(AyarID)
            """)
            print("Foreign key constraint eklendi...")
        except pyodbc.Error as e:
            if "already exists" in str(e) or "duplicate" in str(e).lower():
                print("Foreign key constraint zaten mevcut...")
            else:
                print(f"Foreign key constraint eklenirken hata: {e}")
        
        conn.commit()
        print("Tüm değişiklikler kaydedildi!")
        
    except Exception as e:
        print(f"Genel hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'conn' in locals():
            conn.close()
            print("Veritabanı bağlantısı kapatıldı...")

if __name__ == "__main__":
    add_randevu_columns()


