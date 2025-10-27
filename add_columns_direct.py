#!/usr/bin/env python3

import pyodbc

def add_columns():
    """Todo tablosuna randevu kolonlarını ekle"""
    
    server = 'localhost'
    database = 'CRM_DB'
    username = 'intermedia'
    password = 'intermedia'
    
    try:
        conn = pyodbc.connect(
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={username};'
            f'PWD={password}'
        )
        cursor = conn.cursor()
        
        print("Veritabanına bağlandı...")
        
        # Kolonları ekle
        columns = [
            "ALTER TABLE Todos ADD RandevuTarihi DATE",
            "ALTER TABLE Todos ADD RandevuSaati NVARCHAR(10)",
            "ALTER TABLE Todos ADD RandevuDefteriID INT",
            "ALTER TABLE Todos ADD AtananKullaniciID INT"
        ]
        
        for sql in columns:
            try:
                cursor.execute(sql)
                print(f"OK {sql}")
            except pyodbc.Error as e:
                if "already exists" in str(e) or "duplicate" in str(e).lower() or "already an object" in str(e):
                    print(f"WARNING {sql} - Zaten mevcut")
                else:
                    print(f"ERROR {sql} - Hata: {e}")
        
        conn.commit()
        print("Değişiklikler kaydedildi!")
        
    except Exception as e:
        print(f"Hata: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    add_columns()

