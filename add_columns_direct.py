#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RandevuID ve GorevID sutunlarini dogrudan SQL ile ekleme scripti
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# .env dosyasini yukle
load_dotenv()

def add_columns():
    """Gerekli sutunlari ekle"""
    try:
        # Veritabani URI'sini al
        db_uri = os.environ.get('DATABASE_URL')
        if not db_uri:
            print("HATA - DATABASE_URL environment variable bulunamadi")
            return
        
        print(f"Veritabani URI: {db_uri}")
        
        # Engine olustur
        engine = create_engine(db_uri)
        
        with engine.connect() as conn:
            print("Baglanti basarili!")
            
            # 1. Todos tablosuna RandevuID sutunu ekle
            print("\n1. Todos tablosuna RandevuID sutunu ekleniyor...")
            try:
                conn.execute(text("""
                    ALTER TABLE Todos 
                    ADD RandevuID INT NULL
                """))
                conn.commit()
                print("OK - RandevuID sutunu eklendi")
            except Exception as e:
                if "already exists" in str(e) or "already an object" in str(e):
                    print("INFO - RandevuID sutunu zaten mevcut")
                else:
                    print(f"HATA - RandevuID sutunu eklenirken hata: {e}")
            
            # 2. Randevular tablosuna GorevID sutunu ekle
            print("\n2. Randevular tablosuna GorevID sutunu ekleniyor...")
            try:
                conn.execute(text("""
                    ALTER TABLE Randevular 
                    ADD GorevID INT NULL
                """))
                conn.commit()
                print("OK - GorevID sutunu eklendi")
            except Exception as e:
                if "already exists" in str(e) or "already an object" in str(e):
                    print("INFO - GorevID sutunu zaten mevcut")
                else:
                    print(f"HATA - GorevID sutunu eklenirken hata: {e}")
            
            # 3. Foreign key constraint'leri ekle
            print("\n3. Foreign key constraint'leri ekleniyor...")
            
            # Todos.RandevuID -> Randevular.RandevuID
            try:
                conn.execute(text("""
                    ALTER TABLE Todos 
                    ADD CONSTRAINT FK_Todos_RandevuID 
                    FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID)
                """))
                conn.commit()
                print("OK - Todos.RandevuID foreign key eklendi")
            except Exception as e:
                if "already exists" in str(e) or "already an object" in str(e):
                    print("INFO - Todos.RandevuID foreign key zaten mevcut")
                else:
                    print(f"HATA - Todos.RandevuID foreign key eklenirken hata: {e}")
            
            # Randevular.GorevID -> Todos.TodoID
            try:
                conn.execute(text("""
                    ALTER TABLE Randevular 
                    ADD CONSTRAINT FK_Randevular_GorevID 
                    FOREIGN KEY (GorevID) REFERENCES Todos(TodoID)
                """))
                conn.commit()
                print("OK - Randevular.GorevID foreign key eklendi")
            except Exception as e:
                if "already exists" in str(e) or "already an object" in str(e):
                    print("INFO - Randevular.GorevID foreign key zaten mevcut")
                else:
                    print(f"HATA - Randevular.GorevID foreign key eklenirken hata: {e}")
            
            # Sutunlari kontrol et
            print("\n4. Sutunlar kontrol ediliyor...")
            
            # Todos tablosundaki sutunlari listele
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'Todos' 
                AND COLUMN_NAME IN ('RandevuID', 'AtananKullaniciID')
                ORDER BY COLUMN_NAME
            """))
            todos_columns = [row[0] for row in result.fetchall()]
            print(f"Todos tablosundaki sutunlar: {todos_columns}")
            
            # Randevular tablosundaki sutunlari listele
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'Randevular' 
                AND COLUMN_NAME = 'GorevID'
                ORDER BY COLUMN_NAME
            """))
            randevu_columns = [row[0] for row in result.fetchall()]
            print(f"Randevular tablosundaki sutunlar: {randevu_columns}")
            
            print("\nOK - Tum degisiklikler basariyla kaydedildi!")
        
    except Exception as e:
        print(f"HATA - Genel hata: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("RandevuID ve GorevID sutunlari ekleniyor...")
    add_columns()
    print("\nIslem tamamlandi!")