import sqlite3

conn = sqlite3.connect('crm.db')
cursor = conn.cursor()

# Tabloları listele
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tablolar:')
for table in tables:
    print(table[0])

# TodoDurumlar tablosunu kontrol et
try:
    cursor.execute("SELECT * FROM TodoDurumlar")
    rows = cursor.fetchall()
    print('\nTodoDurumlar tablosu:')
    for row in rows:
        print(row)
except Exception as e:
    print(f'\nTodoDurumlar tablosu hatası: {e}')

# Firma tablosunu kontrol et
try:
    cursor.execute("SELECT * FROM Firma")
    rows = cursor.fetchall()
    print('\nFirma tablosu:')
    for row in rows:
        print(row)
except Exception as e:
    print(f'\nFirma tablosu hatası: {e}')

conn.close()

