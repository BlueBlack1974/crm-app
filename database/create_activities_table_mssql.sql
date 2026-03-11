-- =====================================================
-- Activity / İletişim Geçmişi Tablosu - MSSQL (SQL Server)
-- =====================================================
-- Bu script SQL Server veritabanı için Activity tablosunu oluşturur
-- SQL Server 2012+ ile uyumludur

-- Veritabanını seç
USE CRM_DB;
GO

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Aktiviteler]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[Aktiviteler] (
        -- Primary key (IDENTITY = auto increment)
        AktiviteID INT IDENTITY(1,1) PRIMARY KEY,
        
        -- Müşteri ilişkisi (zorunlu)
        MusteriID INT NOT NULL,
        FOREIGN KEY (MusteriID) REFERENCES Musteriler(MusteriID) ON DELETE CASCADE,
        
        -- Firma ilişkisi (filtreleme için)
        FirmaID INT NOT NULL,
        FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
        
        -- Aktivite tipi: 'call', 'email', 'note', 'appointment', 'task', 'meeting', 'proposal', vb.
        AktiviteTipi NVARCHAR(50) NOT NULL,
        
        -- Başlık ve açıklama
        Baslik NVARCHAR(200) NOT NULL,
        Aciklama NVARCHAR(MAX) NULL,
        
        -- İlişkili nesne (opsiyonel - genişletilebilirlik için)
        -- Örn: 'appointment', 'task', 'proposal', 'invoice' vb.
        IlgiliNesneTipi NVARCHAR(50) NULL,
        IlgiliNesneID INT NULL,
        
        -- Aktivite tarihi/saati (kronolojik sıralama için)
        AktiviteTarihi DATETIME2 NOT NULL,
        
        -- Ek bilgiler (JSON formatında saklanabilir - SQL Server 2016+)
        -- Örn: telefon numarası, email konusu, görüşme süresi vb.
        EkBilgiler NVARCHAR(MAX) NULL, -- JSON string olarak saklanır
        
        -- Oluşturan kullanıcı
        OlusturanKullaniciID INT NULL,
        FOREIGN KEY (OlusturanKullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE SET NULL,
        
        -- Tarih alanları
        OlusturmaTarihi DATETIME2 NOT NULL DEFAULT GETDATE(),
        GuncellemeTarihi DATETIME2 NOT NULL DEFAULT GETDATE()
    );
    
    -- Index'ler (performans için)
    CREATE INDEX idx_musteri ON Aktiviteler(MusteriID);
    CREATE INDEX idx_firma ON Aktiviteler(FirmaID);
    CREATE INDEX idx_aktivite_tarihi ON Aktiviteler(AktiviteTarihi);
    CREATE INDEX idx_aktivite_tipi ON Aktiviteler(AktiviteTipi);
    CREATE INDEX idx_ilgili_nesne ON Aktiviteler(IlgiliNesneTipi, IlgiliNesneID);
    CREATE INDEX idx_olusturan ON Aktiviteler(OlusturanKullaniciID);
    
    -- Aktivite tarihi ve müşteri kombinasyonu için composite index
    CREATE INDEX idx_musteri_tarih ON Aktiviteler(MusteriID, AktiviteTarihi DESC);
    
    -- Tablo açıklaması
    EXEC sys.sp_addextendedproperty 
        @name = N'MS_Description', 
        @value = N'Müşteri iletişim geçmişi ve aktivite kayıtları', 
        @level0type = N'SCHEMA', @level0name = N'dbo', 
        @level1type = N'TABLE', @level1name = N'Aktiviteler';
    
    PRINT 'Aktiviteler tablosu başarıyla oluşturuldu.';
END
ELSE
BEGIN
    PRINT 'Aktiviteler tablosu zaten mevcut.';
END

-- Aktivite tipleri için kontrol (opsiyonel)
-- ALTER TABLE Aktiviteler ADD CONSTRAINT chk_aktivite_tipi 
-- CHECK (AktiviteTipi IN ('call', 'email', 'note', 'appointment', 'task', 'meeting', 'proposal', 'other'));

-- Güncelleme trigger'ı (GuncellemeTarihi için)
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

