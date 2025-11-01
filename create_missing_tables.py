#!/usr/bin/env python3
"""
Eksik MySQL Tablolarını Oluşturma
"""

from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'Sa19977991'
MYSQL_DATABASE = 'Crandyx_CRM_DB'

# Eksik tablolar için SQL
MISSING_TABLES_SQL = [
    # Randevular tablosu
    """CREATE TABLE IF NOT EXISTS Randevular (
    RandevuID INT AUTO_INCREMENT PRIMARY KEY,
    RandevuBaslik VARCHAR(100) NOT NULL,
    RandevuAciklamasi TEXT,
    RandevuTarihi DATETIME NOT NULL,
    RandevuSuresi INT DEFAULT 60,
    MusteriID INT NULL,
    MusteriAdi VARCHAR(100),
    MusteriSoyadi VARCHAR(100),
    MusteriTelefon VARCHAR(20),
    MusteriEmail VARCHAR(100),
    Durum VARCHAR(20) DEFAULT 'Beklemede',
    IslemID INT NULL,
    OlusturanKullaniciID INT NOT NULL,
    FirmaID INT NOT NULL,
    DefterID INT NULL,
    GorevID INT NULL,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    GuncellemeTarihi DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (MusteriID) REFERENCES Musteriler(MusteriID) ON DELETE SET NULL,
    FOREIGN KEY (IslemID) REFERENCES RandevuIslemler(IslemID) ON DELETE SET NULL,
    FOREIGN KEY (OlusturanKullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE RESTRICT,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    FOREIGN KEY (DefterID) REFERENCES RandevuDefterAyarlar(AyarID) ON DELETE SET NULL,
    FOREIGN KEY (GorevID) REFERENCES Todos(TodoID) ON DELETE SET NULL,
    INDEX idx_FirmaID (FirmaID),
    INDEX idx_RandevuTarihi (RandevuTarihi),
    INDEX idx_OlusturanKullaniciID (OlusturanKullaniciID),
    INDEX idx_MusteriID (MusteriID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    
    # RandevuYetkileri tablosu
    """CREATE TABLE IF NOT EXISTS RandevuYetkileri (
    RandevuYetkiID INT AUTO_INCREMENT PRIMARY KEY,
    RandevuID INT NOT NULL,
    KullaniciID INT NOT NULL,
    GoruntulemeYetkisi TINYINT(1) DEFAULT 1,
    DuzenlemeYetkisi TINYINT(1) DEFAULT 0,
    SilmeYetkisi TINYINT(1) DEFAULT 0,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID) ON DELETE CASCADE,
    FOREIGN KEY (KullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE CASCADE,
    UNIQUE KEY unique_randevu_kullanici (RandevuID, KullaniciID),
    INDEX idx_RandevuID (RandevuID),
    INDEX idx_KullaniciID (KullaniciID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    
    # Bildirimler tablosu
    """CREATE TABLE IF NOT EXISTS Bildirimler (
    BildirimID INT AUTO_INCREMENT PRIMARY KEY,
    KullaniciID INT NOT NULL,
    FirmaID INT NOT NULL,
    Metin VARCHAR(300) NOT NULL,
    Okundu TINYINT(1) DEFAULT 0,
    Tip VARCHAR(30) DEFAULT 'genel',
    IlgiliRandevuID INT NULL,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (KullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE CASCADE,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    FOREIGN KEY (IlgiliRandevuID) REFERENCES Randevular(RandevuID) ON DELETE SET NULL,
    INDEX idx_KullaniciID (KullaniciID),
    INDEX idx_Okundu (Okundu)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    
    # RandevuHatirlatmalar tablosu
    """CREATE TABLE IF NOT EXISTS RandevuHatirlatmalar (
    HatirlatmaID INT AUTO_INCREMENT PRIMARY KEY,
    RandevuID INT NOT NULL,
    FirmaID INT NOT NULL,
    RecipientEmail VARCHAR(200),
    MinutesBefore INT DEFAULT 60,
    Gonderildi TINYINT(1) DEFAULT 0,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    GonderimTarihi DATETIME NULL,
    FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID) ON DELETE CASCADE,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    INDEX idx_RandevuID (RandevuID),
    INDEX idx_HatirlatmaTarihi (OlusturmaTarihi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    
    # RandevuSMSHatirlatmalar tablosu
    """CREATE TABLE IF NOT EXISTS RandevuSMSHatirlatmalar (
    HatirlatmaID INT AUTO_INCREMENT PRIMARY KEY,
    RandevuID INT NOT NULL,
    FirmaID INT NOT NULL,
    RecipientPhone VARCHAR(20),
    MinutesBefore INT DEFAULT 1440,
    Gonderildi TINYINT(1) DEFAULT 0,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    GonderimTarihi DATETIME NULL,
    FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID) ON DELETE CASCADE,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    INDEX idx_RandevuID (RandevuID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    
    # Todos tablosu - NOT: Randevular tablosundan önce oluşturulmalı (foreign key yok)
    """CREATE TABLE IF NOT EXISTS Todos (
    TodoID INT AUTO_INCREMENT PRIMARY KEY,
    KullaniciID INT NOT NULL,
    Baslik VARCHAR(200) NOT NULL,
    Aciklama TEXT,
    Oncelik ENUM('Düşük', 'Orta', 'Yüksek') DEFAULT 'Orta',
    DurumID INT,
    Tip ENUM('Kisisel', 'Randevu') DEFAULT 'Kisisel',
    BitisTarihi DATETIME,
    HatirlatmaTarihi DATETIME,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    GuncellemeTarihi DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    TamamlanmaTarihi DATETIME,
    MusteriAdi VARCHAR(100),
    MusteriSoyadi VARCHAR(100),
    MusteriTelefon VARCHAR(20),
    MusteriEmail VARCHAR(100),
    RandevuTarihi DATE,
    RandevuSaati VARCHAR(10),
    RandevuDefteriID INT,
    RandevuID INT,
    AtananKullaniciID INT,
    FOREIGN KEY (KullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE CASCADE,
    FOREIGN KEY (DurumID) REFERENCES TodoDurumlar(DurumID) ON DELETE SET NULL,
    FOREIGN KEY (RandevuDefteriID) REFERENCES RandevuDefterAyarlar(AyarID) ON DELETE SET NULL,
    FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID) ON DELETE SET NULL,
    FOREIGN KEY (AtananKullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE SET NULL,
    INDEX idx_KullaniciID (KullaniciID),
    INDEX idx_DurumID (DurumID),
    INDEX idx_Tip (Tip),
    INDEX idx_BitisTarihi (BitisTarihi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
]

def create_missing_tables():
    """Eksik tabloları oluştur"""
    
    print("=" * 60)
    print("Eksik Tabloları Oluşturma")
    print("=" * 60)
    
    try:
        password_encoded = quote_plus(MYSQL_PASSWORD)
        username_encoded = quote_plus(MYSQL_USER)
        
        connection_string = f"mysql+pymysql://{username_encoded}:{password_encoded}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
        
        engine = create_engine(connection_string, pool_pre_ping=True)
        
        # Önce Todos'u oluştur (Randevular'dan önce)
        print("\n[1/6] Todos tablosu oluşturuluyor...")
        with engine.connect() as conn:
            with conn.begin():
                # Todos'tan GorevID foreign key'ini kaldır (henüz Randevular yok)
                todos_sql = MISSING_TABLES_SQL[5].replace(
                    "FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID) ON DELETE SET NULL,",
                    "-- FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID) ON DELETE SET NULL, -- Randevular oluşturulduktan sonra eklenecek"
                )
                conn.execute(text(todos_sql))
            print("[OK] Todos tablosu oluşturuldu")
        
        # Sonra Randevular'ı oluştur
        print("\n[2/6] Randevular tablosu oluşturuluyor...")
        with engine.connect() as conn:
            with conn.begin():
                # Randevular'dan GorevID foreign key'ini kaldır (henüz Todos yok veya zaten oluşturuldu)
                randevular_sql = MISSING_TABLES_SQL[0]
                conn.execute(text(randevular_sql))
            print("[OK] Randevular tablosu oluşturuldu")
        
        # Sonra GorevID foreign key'ini ekle (Randevular oluşturulduktan sonra)
        print("\n[3/6] Todos tablosuna RandevuID foreign key ekleniyor...")
        try:
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("""
                        ALTER TABLE Todos 
                        ADD CONSTRAINT FK_Todos_Randevular 
                        FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID) ON DELETE SET NULL
                    """))
                print("[OK] Foreign key eklendi")
        except Exception as e:
            if "Duplicate" in str(e) or "already exists" in str(e).lower():
                print("[INFO] Foreign key zaten mevcut")
            else:
                print(f"[UYARI] Foreign key eklenemedi: {e}")
        
        # Diğer tabloları oluştur
        table_names = ["RandevuYetkileri", "Bildirimler", "RandevuHatirlatmalar", "RandevuSMSHatirlatmalar"]
        sql_statements = MISSING_TABLES_SQL[1:5]
        
        for i, (table_name, sql_stmt) in enumerate(zip(table_names, sql_statements), 4):
            print(f"\n[{i}/6] {table_name} tablosu oluşturuluyor...")
            try:
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text(sql_stmt))
                print(f"[OK] {table_name} tablosu oluşturuldu")
            except Exception as e:
                if "already exists" in str(e).lower() or "Duplicate" in str(e):
                    print(f"[INFO] {table_name} tablosu zaten mevcut")
                else:
                    print(f"[HATA] {table_name} oluşturulamadı: {e}")
        
        # Son kontrol
        print("\n[KONTROL] Tablolar kontrol ediliyor...")
        with engine.connect() as conn:
            result = conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            print(f"[OK] Toplam {len(tables)} tablo mevcut")
            
            # Eksik tabloları kontrol et
            required_lower = ['randevular', 'randevuyetkileri', 'bildirimler', 
                            'randevuhatirlatmalar', 'randevusmshatirlatmalar', 'todos']
            existing_lower = [t.lower() for t in tables]
            
            missing = [t for t in required_lower if t not in existing_lower]
            
            if missing:
                print(f"[UYARI] Hala eksik tablolar var: {missing}")
            else:
                print("[OK] Tum tablolar mevcut!")
        
        print("\n" + "=" * 60)
        print("[BASARILI] Eksik tablolar olusturuldu!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n[HATA] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    create_missing_tables()

