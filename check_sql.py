#!/usr/bin/env python3

import pyodbc

# SQL Server bağlantısı
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CRM;"
    "Trusted_Connection=yes;"
)

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    print("=== DURUMLAR ===")
    cursor.execute("SELECT DurumID, DurumAdi, FirmaID FROM TodoDurumlar")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row[0]}, Ad: '{row[1]}', Firma: {row[2]}")
    
    print("\n=== BEKLEMEDE DURUMLARI ===")
    cursor.execute("SELECT DurumID, DurumAdi, FirmaID FROM TodoDurumlar WHERE DurumAdi = 'Beklemede'")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row[0]}, Ad: '{row[1]}', Firma: {row[2]}")
    
    print("\n=== FIRMALAR ===")
    cursor.execute("SELECT FirmaID, FirmaAdi FROM Firmalar")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row[0]}, Ad: '{row[1]}'")
    
    conn.close()
    
except Exception as e:
    print(f"Hata: {e}")
    import traceback
    traceback.print_exc()


