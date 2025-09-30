-- CRM Veritabani Olusturma Scripti
-- MSSQL Server icin

-- Veritabani olustur
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'CRM_DB')
BEGIN
    CREATE DATABASE CRM_DB;
END
GO

USE CRM_DB;
GO

-- Ortam ayarlari
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET XACT_ABORT ON;
GO

-- Firmalar tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Firmalar' AND xtype='U')
BEGIN
    CREATE TABLE Firmalar (
        FirmaID INT IDENTITY(1,1) PRIMARY KEY,
        FirmaAdi NVARCHAR(100) NOT NULL,
        FirmaKodu NVARCHAR(20) UNIQUE NOT NULL,
        Adres NVARCHAR(200),
        Telefon NVARCHAR(20),
        Email NVARCHAR(100),
        Aktif BIT DEFAULT 1,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        GuncellemeTarihi DATETIME DEFAULT GETDATE()
    );
END
GO

-- Kullanicilar tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Kullanicilar' AND xtype='U')
BEGIN
    CREATE TABLE Kullanicilar (
        KullaniciID INT IDENTITY(1,1) PRIMARY KEY,
        KullaniciAdi NVARCHAR(50) UNIQUE NOT NULL,
        Sifre NVARCHAR(255) NOT NULL,
        Ad NVARCHAR(50) NOT NULL,
        Soyad NVARCHAR(50) NOT NULL,
        Email NVARCHAR(100) UNIQUE NOT NULL,
        Telefon NVARCHAR(20),
        FirmaID INT NOT NULL,
        Admin BIT DEFAULT 0,
        Aktif BIT DEFAULT 1,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        GuncellemeTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID)
    );
END
GO

-- Yetki tipleri tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='YetkiTipleri' AND xtype='U')
BEGIN
    CREATE TABLE YetkiTipleri (
        YetkiID INT IDENTITY(1,1) PRIMARY KEY,
        YetkiAdi NVARCHAR(50) NOT NULL,
        YetkiAciklamasi NVARCHAR(200),
        Aktif BIT DEFAULT 1
    );
END
GO

-- Kullanici yetkileri tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='KullaniciYetkileri' AND xtype='U')
BEGIN
    CREATE TABLE KullaniciYetkileri (
        KullaniciYetkiID INT IDENTITY(1,1) PRIMARY KEY,
        KullaniciID INT NOT NULL,
        YetkiID INT NOT NULL,
        Aktif BIT DEFAULT 1,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (KullaniciID) REFERENCES Kullanicilar(KullaniciID),
        FOREIGN KEY (YetkiID) REFERENCES YetkiTipleri(YetkiID),
        UNIQUE(KullaniciID, YetkiID)
    );
END
GO

-- Randevular tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Randevular' AND xtype='U')
BEGIN
    CREATE TABLE Randevular (
        RandevuID INT IDENTITY(1,1) PRIMARY KEY,
        RandevuBaslik NVARCHAR(100) NOT NULL,
        RandevuAciklamasi NVARCHAR(500),
        RandevuTarihi DATETIME NOT NULL,
        RandevuSuresi INT DEFAULT 60, -- dakika cinsinden
        MusteriAdi NVARCHAR(100),
        MusteriTelefon NVARCHAR(20),
        MusteriEmail NVARCHAR(100),
        Durum NVARCHAR(20) DEFAULT 'Beklemede', -- Beklemede, Onaylandi, Iptal, Tamamlandi
        OlusturanKullaniciID INT NOT NULL,
        FirmaID INT NOT NULL,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        GuncellemeTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (OlusturanKullaniciID) REFERENCES Kullanicilar(KullaniciID),
        FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID)
    );
END
GO

-- Randevu yetkileri tablosu (hangi kullanici hangi randevulari gorebilir)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='RandevuYetkileri' AND xtype='U')
BEGIN
    CREATE TABLE RandevuYetkileri (
        RandevuYetkiID INT IDENTITY(1,1) PRIMARY KEY,
        RandevuID INT NOT NULL,
        KullaniciID INT NOT NULL,
        GoruntulemeYetkisi BIT DEFAULT 1,
        DuzenlemeYetkisi BIT DEFAULT 0,
        SilmeYetkisi BIT DEFAULT 0,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID),
        FOREIGN KEY (KullaniciID) REFERENCES Kullanicilar(KullaniciID),
        UNIQUE(RandevuID, KullaniciID)
    );
END
GO

-- Indexler (idempotent)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Kullanicilar_FirmaID' AND object_id = OBJECT_ID('dbo.Kullanicilar'))
    CREATE INDEX IX_Kullanicilar_FirmaID ON dbo.Kullanicilar(FirmaID);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Kullanicilar_KullaniciAdi' AND object_id = OBJECT_ID('dbo.Kullanicilar'))
    CREATE INDEX IX_Kullanicilar_KullaniciAdi ON dbo.Kullanicilar(KullaniciAdi);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Randevular_FirmaID' AND object_id = OBJECT_ID('dbo.Randevular'))
    CREATE INDEX IX_Randevular_FirmaID ON dbo.Randevular(FirmaID);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Randevular_RandevuTarihi' AND object_id = OBJECT_ID('dbo.Randevular'))
    CREATE INDEX IX_Randevular_RandevuTarihi ON dbo.Randevular(RandevuTarihi);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_RandevuYetkileri_KullaniciID' AND object_id = OBJECT_ID('dbo.RandevuYetkileri'))
    CREATE INDEX IX_RandevuYetkileri_KullaniciID ON dbo.RandevuYetkileri(KullaniciID);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_RandevuYetkileri_RandevuID' AND object_id = OBJECT_ID('dbo.RandevuYetkileri'))
    CREATE INDEX IX_RandevuYetkileri_RandevuID ON dbo.RandevuYetkileri(RandevuID);

-- Varsayilan veriler (idempotent)
-- Yetki tipleri
IF NOT EXISTS (SELECT 1 FROM dbo.YetkiTipleri WHERE YetkiAdi = 'RandevuGoruntuleme')
    INSERT INTO dbo.YetkiTipleri (YetkiAdi, YetkiAciklamasi) VALUES ('RandevuGoruntuleme', 'Randevulari goruntuleme yetkisi');
IF NOT EXISTS (SELECT 1 FROM dbo.YetkiTipleri WHERE YetkiAdi = 'RandevuOlusturma')
    INSERT INTO dbo.YetkiTipleri (YetkiAdi, YetkiAciklamasi) VALUES ('RandevuOlusturma', 'Yeni randevu olusturma yetkisi');
IF NOT EXISTS (SELECT 1 FROM dbo.YetkiTipleri WHERE YetkiAdi = 'RandevuDuzenleme')
    INSERT INTO dbo.YetkiTipleri (YetkiAdi, YetkiAciklamasi) VALUES ('RandevuDuzenleme', 'Mevcut randevulari duzenleme yetkisi');
IF NOT EXISTS (SELECT 1 FROM dbo.YetkiTipleri WHERE YetkiAdi = 'RandevuSilme')
    INSERT INTO dbo.YetkiTipleri (YetkiAdi, YetkiAciklamasi) VALUES ('RandevuSilme', 'Randevu silme yetkisi');
IF NOT EXISTS (SELECT 1 FROM dbo.YetkiTipleri WHERE YetkiAdi = 'KullaniciYonetimi')
    INSERT INTO dbo.YetkiTipleri (YetkiAdi, YetkiAciklamasi) VALUES ('KullaniciYonetimi', 'Kullanici yonetim yetkisi');
IF NOT EXISTS (SELECT 1 FROM dbo.YetkiTipleri WHERE YetkiAdi = 'FirmaYonetimi')
    INSERT INTO dbo.YetkiTipleri (YetkiAdi, YetkiAciklamasi) VALUES ('FirmaYonetimi', 'Firma yonetim yetkisi');
IF NOT EXISTS (SELECT 1 FROM dbo.YetkiTipleri WHERE YetkiAdi = 'Admin')
    INSERT INTO dbo.YetkiTipleri (YetkiAdi, YetkiAciklamasi) VALUES ('Admin', 'Tam yetki');

-- Varsayilan firma
IF NOT EXISTS (SELECT 1 FROM dbo.Firmalar WHERE FirmaKodu = 'ANA001')
    INSERT INTO dbo.Firmalar (FirmaAdi, FirmaKodu, Adres, Telefon, Email)
    VALUES ('Ana Firma', 'ANA001', 'Merkez Adres', '0212 000 00 00', 'info@anafirma.com');

-- Admin kullanici (sifre: admin123 - hash'lenmis olarak)
IF NOT EXISTS (SELECT 1 FROM dbo.Kullanicilar WHERE KullaniciAdi = 'admin')
    INSERT INTO dbo.Kullanicilar (KullaniciAdi, Sifre, Ad, Soyad, Email, FirmaID, Admin)
    VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/8Kz8Kz2', 'Admin', 'Kullanici', 'admin@anafirma.com', 1, 1);

-- Admin kullaniciya tum yetkileri ver
INSERT INTO dbo.KullaniciYetkileri (KullaniciID, YetkiID)
SELECT 1, yt.YetkiID
FROM dbo.YetkiTipleri yt
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.KullaniciYetkileri ky
    WHERE ky.KullaniciID = 1 AND ky.YetkiID = yt.YetkiID
);

-- Randevu defteri ayarları tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='RandevuDefterAyarlar' AND xtype='U')
BEGIN
    CREATE TABLE RandevuDefterAyarlar (
        AyarID INT IDENTITY(1,1) PRIMARY KEY,
        FirmaID INT NOT NULL,
        Pazartesi BIT DEFAULT 1,
        Sali BIT DEFAULT 1,
        Carsamba BIT DEFAULT 1,
        Persembe BIT DEFAULT 1,
        Cuma BIT DEFAULT 1,
        Cumartesi BIT DEFAULT 0,
        Pazar BIT DEFAULT 0,
        BaslangicSaati TIME DEFAULT '09:00',
        BitisSaati TIME DEFAULT '18:00',
        SlotSuresi INT DEFAULT 30, -- dakika cinsinden
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        GuncellemeTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID)
    );
END
GO

-- Randevu referansları tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='RandevuReferanslari' AND xtype='U')
BEGIN
    CREATE TABLE RandevuReferanslari (
        ReferansID INT IDENTITY(1,1) PRIMARY KEY,
        FirmaID INT NOT NULL,
        ReferansAdi NVARCHAR(100) NOT NULL,
        Aktif BIT DEFAULT 1,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID)
    );
END
GO

-- Bildirimler tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Bildirimler' AND xtype='U')
BEGIN
    CREATE TABLE Bildirimler (
        BildirimID INT IDENTITY(1,1) PRIMARY KEY,
        KullaniciID INT NOT NULL,
        Baslik NVARCHAR(200) NOT NULL,
        Mesaj NVARCHAR(1000) NOT NULL,
        Okundu BIT DEFAULT 0,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (KullaniciID) REFERENCES Kullanicilar(KullaniciID)
    );
END
GO

-- Randevu hatırlatmaları tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='RandevuHatirlatmalari' AND xtype='U')
BEGIN
    CREATE TABLE RandevuHatirlatmalari (
        HatirlatmaID INT IDENTITY(1,1) PRIMARY KEY,
        RandevuID INT NOT NULL,
        HatirlatmaTarihi DATETIME NOT NULL,
        Gonderildi BIT DEFAULT 0,
        GonderimTarihi DATETIME NULL,
        FOREIGN KEY (RandevuID) REFERENCES Randevular(RandevuID)
    );
END
GO

-- E-posta ayarları tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='FirmaEmailAyarlari' AND xtype='U')
BEGIN
    CREATE TABLE FirmaEmailAyarlari (
        EmailAyarID INT IDENTITY(1,1) PRIMARY KEY,
        FirmaID INT NOT NULL,
        SMTP_Sunucu NVARCHAR(200) NOT NULL,
        SMTP_Port INT NOT NULL,
        KullaniciAdi NVARCHAR(200) NOT NULL,
        Sifre NVARCHAR(200) NOT NULL,
        SSL_Kullan BIT DEFAULT 1,
        VarsayilanGonderenAdi NVARCHAR(200) NULL,
        VarsayilanGonderenEmail NVARCHAR(200) NULL,
        Aktif BIT DEFAULT 1,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID)
    );
END
GO

-- SMS ayarları tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='FirmaSMSAyarlari' AND xtype='U')
BEGIN
    CREATE TABLE FirmaSMSAyarlari (
        SMSAyarID INT IDENTITY(1,1) PRIMARY KEY,
        FirmaID INT NOT NULL,
        SMSFirmasi NVARCHAR(50) NOT NULL, -- 'netgsm', 'iletimerkezi', 'mesajnet', 'custom'
        API_Key NVARCHAR(500) NULL,
        API_Secret NVARCHAR(500) NULL,
        KullaniciAdi NVARCHAR(200) NULL,
        Sifre NVARCHAR(200) NULL,
        GondericiAdi NVARCHAR(20) NULL,
        API_URL NVARCHAR(500) NULL,
        Aktif BIT DEFAULT 1,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID)
    );
END
GO

-- Müşteri kategorileri tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='MusteriKategorileri' AND xtype='U')
BEGIN
    CREATE TABLE MusteriKategorileri (
        KategoriID INT IDENTITY(1,1) PRIMARY KEY,
        FirmaID INT NOT NULL,
        KategoriAdi NVARCHAR(100) NOT NULL,
        Renk NVARCHAR(20) DEFAULT '#007bff',
        Aciklama NVARCHAR(500) NULL,
        Aktif BIT DEFAULT 1,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID)
    );
END
GO

-- Müşteriler tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Musteriler' AND xtype='U')
BEGIN
    CREATE TABLE Musteriler (
        MusteriID INT IDENTITY(1,1) PRIMARY KEY,
        FirmaID INT NOT NULL,
        MusteriAdi NVARCHAR(100) NOT NULL,
        MusteriSoyadi NVARCHAR(100) NOT NULL,
        Telefon NVARCHAR(20) NULL,
        Email NVARCHAR(200) NULL,
        Adres NVARCHAR(500) NULL,
        DogumTarihi DATE NULL,
        Cinsiyet NVARCHAR(10) NULL, -- 'Erkek', 'Kadın'
        KategoriID INT NULL,
        Notlar NVARCHAR(1000) NULL,
        ProfilFotografi NVARCHAR(500) NULL,
        Aktif BIT DEFAULT 1,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        GuncellemeTarihi DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID),
        FOREIGN KEY (KategoriID) REFERENCES MusteriKategorileri(KategoriID)
    );
END
GO

-- Varsayılan müşteri kategorileri ekle (tüm firmalar için - sadece yoksa)
INSERT INTO MusteriKategorileri (FirmaID, KategoriAdi, Renk, Aciklama)
SELECT f.FirmaID, 'Normal Müşteri', '#28a745', 'Standart müşteri kategorisi' 
FROM Firmalar f
WHERE NOT EXISTS (
    SELECT 1 FROM MusteriKategorileri mk 
    WHERE mk.FirmaID = f.FirmaID AND mk.KategoriAdi = 'Normal Müşteri'
)
UNION ALL
SELECT f.FirmaID, 'VIP Müşteri', '#dc3545', 'Özel müşteri kategorisi' 
FROM Firmalar f
WHERE NOT EXISTS (
    SELECT 1 FROM MusteriKategorileri mk 
    WHERE mk.FirmaID = f.FirmaID AND mk.KategoriAdi = 'VIP Müşteri'
)
UNION ALL
SELECT f.FirmaID, 'Yeni Müşteri', '#17a2b8', 'Yeni kayıt olan müşteriler' 
FROM Firmalar f
WHERE NOT EXISTS (
    SELECT 1 FROM MusteriKategorileri mk 
    WHERE mk.FirmaID = f.FirmaID AND mk.KategoriAdi = 'Yeni Müşteri'
)
UNION ALL
SELECT f.FirmaID, 'Sadık Müşteri', '#ffc107', 'Düzenli gelen müşteriler' 
FROM Firmalar f
WHERE NOT EXISTS (
    SELECT 1 FROM MusteriKategorileri mk 
    WHERE mk.FirmaID = f.FirmaID AND mk.KategoriAdi = 'Sadık Müşteri'
);

GO

-- Randevular tablosuna MusteriID alanı ekle (eğer yoksa)
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('Randevular') AND name = 'MusteriID')
BEGIN
    ALTER TABLE Randevular ADD MusteriID INT NULL;
    ALTER TABLE Randevular ADD CONSTRAINT FK_Randevular_Musteriler FOREIGN KEY (MusteriID) REFERENCES Musteriler(MusteriID);
END
GO

PRINT 'CRM veritabani basariyla olusturuldu!';
PRINT 'Admin kullanici: admin';
PRINT 'Admin sifre: admin123';
