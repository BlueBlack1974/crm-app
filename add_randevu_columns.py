#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RandevuID ve GorevID sutunlarini veritabanina ekleme scripti
"""

import pyodbc
import os
from dotenv import load_dotenv

# .env dosyasini yukle
load_dotenv()

def get_connection_string():
    """Veritabani baglanti stringini al"""
    server = os.getenv('DB_SERVER', 'localhost')
    database = os.getenv('DB_NAME', 'CRM')
    username = os.getenv('DB_USERNAME', 'sa')
    password = os.getenv('DB_PASSWORD', '')
    
    return f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"

def add_columns():
    """Gerekli sutunlari ekle"""
    try:
        # Baglantiyi kur
        conn_str = get_connection_string()
        print(f"Veritabanina baglaniliyor: {conn_str}")
        
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        print("Baglanti basarili!")
        
        # 1. Todos tablosuna RandevuID sutunu ekle
        print("\n1. Todos tablosuna RandevuID sutunu ekleniyor...")
        try:
            cursor.execute("""
                ALTER TABLE Todos 
                ADD RandevuID INT NULL
            """)
            print("OK - RandevuID sutunu eklendi")
        except pyodbc.Error as e:
            if "already exists" in str(e) or "already an object" in str(e):
                print("INFO - RandevuID sutunu zaten mevcut")
            else:
                print(f"HATA - RandevuID sutunu eklenirken hata: {e}")
        
        # 2. Randevular tablosuna GorevID sutunu ekle
        print("\n2. Randevular tablosuna GorevID sutunu ekleniyor...")
        try:
            cursor.execute("""
                ALTER TABLE Randevular 
                ADD GorevID INT NULL
            """)
            print("OK - GorevID sutunu eklendi")
        except pyodbc.Error as e:
            if "already exists" in str(e) or "already an object" in str(e):
                print("INFO - GorevID sutunu zaten mevcut")
            else:
                print(f"HATA - GorevID sutunu eklenirken hata: {e}")
        
        # 3. Foreign key constraint'leri ekle
        print("\n3. Foreign key constraint'leri ekleniyor...")
        
        # Todos.RandevuID -> Randevular.RandevuID
        try:
            cursor.execute("""
                ALTER TABLE Todos 
                ADD CONSTRAINT FK_Todos_RandevuID 
                FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID)
            """)
            print("OK - Todos.RandevuID foreign key eklendi")
        except pyodbc.Error as e:
            if "already exists" in str(e) or "already an object" in str(e):
                print("INFO - Todos.RandevuID foreign key zaten mevcut")
            else:
                print(f"HATA - Todos.RandevuID foreign key eklenirken hata: {e}")
        
        # Randevular.GorevID -> Todos.TodoID
        try:
            cursor.execute("""
                ALTER TABLE Randevular 
                ADD CONSTRAINT FK_Randevular_GorevID 
                FOREIGN KEY (GorevID) REFERENCES Todos(TodoID)
            """)
            print("OK - Randevular.GorevID foreign key eklendi")
        except pyodbc.Error as e:
            if "already exists" in str(e) or "already an object" in str(e):
                print("INFO - Randevular.GorevID foreign key zaten mevcut")
            else:
                print(f"HATA - Randevular.GorevID foreign key eklenirken hata: {e}")
        
        # Degisiklikleri kaydet
        conn.commit()
        print("\nOK - Tum degisiklikler basariyla kaydedildi!")
        
        # Sutunlari kontrol et
        print("\n4. Sutunlar kontrol ediliyor...")
        
        # Todos tablosundaki sutunlari listele
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'Todos' 
            AND COLUMN_NAME IN ('RandevuID', 'AtananKullaniciID')
            ORDER BY COLUMN_NAME
        """)
        todos_columns = [row[0] for row in cursor.fetchall()]
        print(f"Todos tablosundaki sutunlar: {todos_columns}")
        
        # Randevular tablosundaki sutunlari listele
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'Randevular' 
            AND COLUMN_NAME = 'GorevID'
            ORDER BY COLUMN_NAME
        """)
        randevu_columns = [row[0] for row in cursor.fetchall()]
        print(f"Randevular tablosundaki sutunlar: {randevu_columns}")
        
    except Exception as e:
        print(f"HATA - Genel hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'conn' in locals():
            conn.close()
            print("\nVeritabani baglantisi kapatildi")

if __name__ == "__main__":
    print("RandevuID ve GorevID sutunlari ekleniyor...")
    add_columns()
    print("\nIslem tamamlandi!")