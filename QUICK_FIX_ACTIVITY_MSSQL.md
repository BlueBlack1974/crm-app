# Aktivite Modülü - MSSQL Kurulum Rehberi

## MSSQL için Migration

### 1. SQL Server Management Studio (SSMS) ile:

1. **SSMS'i açın**
2. Veritabanınıza bağlanın
3. **File → Open → File** ile `database/create_activities_table_mssql.sql` dosyasını açın
4. Script'i seçin ve **Execute** (F5) tuşuna basın

### 2. sqlcmd ile (Terminal):

```bash
sqlcmd -S localhost -d crandyx_crm_db -U sa -P your_password -i database/create_activities_table_mssql.sql
```

### 3. Manuel Olarak (SSMS Query Window):

SSMS'te yeni bir query penceresi açın ve şu komutu çalıştırın:

```sql
-- Veritabanını seç
USE crandyx_crm_db;
GO

-- Tablo oluştur
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Aktiviteler]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[Aktiviteler] (
        AktiviteID INT IDENTITY(1,1) PRIMARY KEY,
        MusteriID INT NOT NULL,
        FirmaID INT NOT NULL,
        AktiviteTipi NVARCHAR(50) NOT NULL,
        Baslik NVARCHAR(200) NOT NULL,
        Aciklama NVARCHAR(MAX) NULL,
        IlgiliNesneTipi NVARCHAR(50) NULL,
        IlgiliNesneID INT NULL,
        AktiviteTarihi DATETIME2 NOT NULL,
        EkBilgiler NVARCHAR(MAX) NULL,
        OlusturanKullaniciID INT NULL,
        OlusturmaTarihi DATETIME2 NOT NULL DEFAULT GETDATE(),
        GuncellemeTarihi DATETIME2 NOT NULL DEFAULT GETDATE(),
        FOREIGN KEY (MusteriID) REFERENCES Musteriler(MusteriID) ON DELETE CASCADE,
        FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
        FOREIGN KEY (OlusturanKullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE SET NULL
    );
    
    -- Index'ler
    CREATE INDEX idx_musteri ON Aktiviteler(MusteriID);
    CREATE INDEX idx_firma ON Aktiviteler(FirmaID);
    CREATE INDEX idx_aktivite_tarihi ON Aktiviteler(AktiviteTarihi);
    CREATE INDEX idx_aktivite_tipi ON Aktiviteler(AktiviteTipi);
    CREATE INDEX idx_ilgili_nesne ON Aktiviteler(IlgiliNesneTipi, IlgiliNesneID);
    CREATE INDEX idx_olusturan ON Aktiviteler(OlusturanKullaniciID);
    CREATE INDEX idx_musteri_tarih ON Aktiviteler(MusteriID, AktiviteTarihi DESC);
    
    PRINT 'Aktiviteler tablosu başarıyla oluşturuldu.';
END
ELSE
BEGIN
    PRINT 'Aktiviteler tablosu zaten mevcut.';
END
GO

-- Güncelleme trigger'ı
IF NOT EXISTS (SELECT * FROM sys.triggers WHERE name = 'trg_Aktiviteler_Update')
BEGIN
    EXEC('
    CREATE TRIGGER trg_Aktiviteler_Update
    ON Aktiviteler
    AFTER UPDATE
    AS
    BEGIN
        SET NOCOUNT ON;
        UPDATE Aktiviteler
        SET GuncellemeTarihi = GETDATE()
        FROM Aktiviteler a
        INNER JOIN inserted i ON a.AktiviteID = i.AktiviteID;
    END
    ');
    PRINT 'Güncelleme trigger''ı oluşturuldu.';
END
GO
```

## Tablo Kontrolü

Migration'dan sonra tabloyu kontrol edin:

```sql
-- Tablo var mı?
SELECT * FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_NAME = 'Aktiviteler';

-- Sütunları kontrol et
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'Aktiviteler'
ORDER BY ORDINAL_POSITION;

-- Index'leri kontrol et
SELECT 
    i.name AS IndexName,
    i.type_desc AS IndexType,
    COL_NAME(ic.object_id, ic.column_id) AS ColumnName
FROM sys.indexes i
INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
WHERE i.object_id = OBJECT_ID('Aktiviteler')
ORDER BY i.name, ic.key_ordinal;
```

## Uygulamayı Başlat

```bash
python run.py
```

## Test

1. Tarayıcıda `http://localhost:5000` → Giriş yap
2. Müşteriler → Bir müşteri seç → Detay
3. Modal'da en altta "Activity Timeline" görünmeli

## Sorun Giderme

### Hata: "Invalid object name 'Aktiviteler'"
- **Çözüm:** Migration script'ini çalıştırın

### Hata: "Foreign key constraint"
- **Çözüm:** Önce Musteriler, Firmalar ve Kullanicilar tablolarının var olduğundan emin olun

### Hata: "IDENTITY_INSERT is set to OFF"
- **Çözüm:** Bu normal, IDENTITY otomatik artacak

### Tablo oluşturuldu ama görünmüyor
- **Çözüm:** Uygulamayı yeniden başlatın (python run.py)





