-- CRM Veritabanı Oluşturma Scripti
-- MySQL için

-- Veritabanı oluştur
CREATE DATABASE IF NOT EXISTS Crandyx_CRM_DB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE Crandyx_CRM_DB;

-- Firmalar tablosu
CREATE TABLE IF NOT EXISTS Firmalar (
    FirmaID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaAdi VARCHAR(100) NOT NULL,
    FirmaKodu VARCHAR(20) UNIQUE NOT NULL,
    Adres VARCHAR(200),
    Telefon VARCHAR(20),
    Email VARCHAR(100),
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    GuncellemeTarihi DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_FirmaKodu (FirmaKodu)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Kullanicilar tablosu
CREATE TABLE IF NOT EXISTS Kullanicilar (
    KullaniciID INT AUTO_INCREMENT PRIMARY KEY,
    KullaniciAdi VARCHAR(50) UNIQUE NOT NULL,
    Sifre VARCHAR(255) NOT NULL,
    Ad VARCHAR(50) NOT NULL,
    Soyad VARCHAR(50) NOT NULL,
    Email VARCHAR(100) UNIQUE NOT NULL,
    Telefon VARCHAR(20),
    FirmaID INT NOT NULL,
    Admin TINYINT(1) DEFAULT 0,
    Aktif TINYINT(1) DEFAULT 1,
    RaporlarModulu TINYINT(1) DEFAULT 1,
    AyarlarModulu TINYINT(1) DEFAULT 0,
    LogModulu TINYINT(1) DEFAULT 0,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    GuncellemeTarihi DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    INDEX idx_KullaniciAdi (KullaniciAdi),
    INDEX idx_Email (Email),
    INDEX idx_FirmaID (FirmaID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- AktifOturumlar tablosu
-- MSSQL ile uyumlu kolon isimleri kullanılıyor
CREATE TABLE IF NOT EXISTS AktifOturumlar (
    AktifOturumID INT AUTO_INCREMENT PRIMARY KEY,
    KullaniciID INT NOT NULL,
    SessionToken VARCHAR(255) UNIQUE NOT NULL,
    ClientIP VARCHAR(50),
    UserAgent TEXT,
    GirisZamani DATETIME DEFAULT CURRENT_TIMESTAMP,
    SonGorulmeZamani DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (KullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE CASCADE,
    INDEX idx_KullaniciID (KullaniciID),
    INDEX idx_SessionToken (SessionToken)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- KullaniciLoglari tablosu
-- MSSQL ile uyumlu kolon isimleri kullanılıyor
CREATE TABLE IF NOT EXISTS KullaniciLoglari (
    LogID INT AUTO_INCREMENT PRIMARY KEY,
    KullaniciID INT NOT NULL,
    IslemTipi VARCHAR(30) NOT NULL,
    TabloAdi VARCHAR(30) NOT NULL,
    KayitID INT,
    EskiVeri TEXT,
    YeniVeri TEXT,
    IslemDetayi VARCHAR(500),
    IPAdresi VARCHAR(45),
    UserAgent VARCHAR(500),
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (KullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE CASCADE,
    INDEX idx_KullaniciID (KullaniciID),
    INDEX idx_OlusturmaTarihi (OlusturmaTarihi),
    INDEX idx_TabloAdi (TabloAdi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Yetki tipleri tablosu
CREATE TABLE IF NOT EXISTS YetkiTipleri (
    YetkiID INT AUTO_INCREMENT PRIMARY KEY,
    YetkiAdi VARCHAR(50) NOT NULL,
    YetkiAciklamasi VARCHAR(200),
    Aktif TINYINT(1) DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Kullanici yetkileri tablosu
CREATE TABLE IF NOT EXISTS KullaniciYetkileri (
    KullaniciYetkiID INT AUTO_INCREMENT PRIMARY KEY,
    KullaniciID INT NOT NULL,
    YetkiID INT NOT NULL,
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (KullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE CASCADE,
    FOREIGN KEY (YetkiID) REFERENCES YetkiTipleri(YetkiID) ON DELETE CASCADE,
    UNIQUE KEY unique_kullanici_yetki (KullaniciID, YetkiID),
    INDEX idx_KullaniciID (KullaniciID),
    INDEX idx_YetkiID (YetkiID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Randevular tablosu
CREATE TABLE IF NOT EXISTS Randevular (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Randevu yetkileri tablosu
CREATE TABLE IF NOT EXISTS RandevuYetkileri (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Randevu defteri ayarları tablosu
CREATE TABLE IF NOT EXISTS RandevuDefterAyarlar (
    AyarID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaID INT NOT NULL,
    DefterAdi VARCHAR(100) NOT NULL DEFAULT 'Varsayilan Defter',
    CalismaGunleri VARCHAR(50) DEFAULT '1,2,3,4,5',
    BaslangicSaati VARCHAR(5) DEFAULT '09:00',
    BitisSaati VARCHAR(5) DEFAULT '18:00',
    SlotDakika INT DEFAULT 30,
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    GuncellemeTarihi DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    INDEX idx_FirmaID (FirmaID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Randevu defteri bloklar tablosu
CREATE TABLE IF NOT EXISTS RandevuDefterBloklar (
    BlokID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaID INT NOT NULL,
    DefterID INT NULL,
    BaslangicTarih DATE NOT NULL,
    BitisTarih DATE NULL,
    SaatBaslangic VARCHAR(5),
    SaatBitis VARCHAR(5),
    Aciklama VARCHAR(200),
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    FOREIGN KEY (DefterID) REFERENCES RandevuDefterAyarlar(AyarID) ON DELETE CASCADE,
    INDEX idx_FirmaID (FirmaID),
    INDEX idx_DefterID (DefterID),
    INDEX idx_BaslangicTarih (BaslangicTarih)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Randevu referansları tablosu
CREATE TABLE IF NOT EXISTS RandevuReferanslari (
    ReferansID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaID INT NOT NULL,
    Ad VARCHAR(100) NOT NULL,
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    INDEX idx_FirmaID (FirmaID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Randevu işlemler tablosu
CREATE TABLE IF NOT EXISTS RandevuIslemler (
    IslemID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaID INT NOT NULL,
    DefterID INT NULL,
    IslemAdi VARCHAR(100) NOT NULL,
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    FOREIGN KEY (DefterID) REFERENCES RandevuDefterAyarlar(AyarID) ON DELETE SET NULL,
    INDEX idx_FirmaID (FirmaID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bildirimler tablosu
CREATE TABLE IF NOT EXISTS Bildirimler (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Randevu hatırlatmaları tablosu
CREATE TABLE IF NOT EXISTS RandevuHatirlatmalar (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Randevu SMS hatırlatmaları tablosu
CREATE TABLE IF NOT EXISTS RandevuSMSHatirlatmalar (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- E-posta ayarları tablosu
CREATE TABLE IF NOT EXISTS FirmaEmailAyarlari (
    EmailAyarID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaID INT NOT NULL,
    SMTP_Sunucu VARCHAR(200) NOT NULL,
    SMTP_Port INT NOT NULL,
    KullaniciAdi VARCHAR(200) NOT NULL,
    Sifre VARCHAR(200) NOT NULL,
    SSL_Kullan TINYINT(1) DEFAULT 1,
    VarsayilanGonderenAdi VARCHAR(200),
    VarsayilanGonderenEmail VARCHAR(200),
    VarsayilanEmailKonu VARCHAR(200),
    VarsayilanEmailMetni TEXT,
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    INDEX idx_FirmaID (FirmaID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- SMS ayarları tablosu
CREATE TABLE IF NOT EXISTS FirmaSMSAyarlari (
    SMSAyarID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaID INT NOT NULL,
    SMSFirmasi VARCHAR(50) NOT NULL,
    API_Key VARCHAR(500),
    API_Secret VARCHAR(500),
    KullaniciAdi VARCHAR(200),
    Sifre VARCHAR(200),
    GondericiAdi VARCHAR(20),
    API_URL VARCHAR(500),
    VarsayilanSMSMetni VARCHAR(1000),
    SMSGonderOnCreate TINYINT(1) DEFAULT 0,
    SMSGonder24SaatOnce TINYINT(1) DEFAULT 0,
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    INDEX idx_FirmaID (FirmaID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- WhatsApp ayarları tablosu
CREATE TABLE IF NOT EXISTS FirmaWhatsAppAyarlari (
    WhatsAppAyarID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaID INT NOT NULL,
    AccessToken TEXT,
    PhoneNumberID VARCHAR(50),
    BusinessAccountID VARCHAR(50),
    WebhookVerifyToken VARCHAR(100),
    RandevuOlusturmaMesaji TEXT,
    RandevuHatirlatmaMesaji TEXT,
    RandevuIptalMesaji TEXT,
    MesajGonderOnCreate TINYINT(1) DEFAULT 0,
    MesajGonder24SaatOnce TINYINT(1) DEFAULT 0,
    MesajGonder1SaatOnce TINYINT(1) DEFAULT 0,
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    GuncellemeTarihi DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    INDEX idx_FirmaID (FirmaID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Sistem ayarları tablosu
CREATE TABLE IF NOT EXISTS SistemAyarlar (
    AyarID INT AUTO_INCREMENT PRIMARY KEY,
    AyarAdi VARCHAR(100) UNIQUE NOT NULL,
    AyarDegeri TEXT,
    Aciklama VARCHAR(500),
    GuncellemeTarihi DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_AyarAdi (AyarAdi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Müşteri kategorileri tablosu
CREATE TABLE IF NOT EXISTS MusteriKategorileri (
    KategoriID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaID INT NOT NULL,
    KategoriAdi VARCHAR(100) NOT NULL,
    Renk VARCHAR(20) DEFAULT '#007bff',
    Aciklama TEXT,
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    INDEX idx_FirmaID (FirmaID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Müşteriler tablosu
CREATE TABLE IF NOT EXISTS Musteriler (
    MusteriID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaID INT NOT NULL,
    MusteriAdi VARCHAR(100) NOT NULL,
    MusteriSoyadi VARCHAR(100) NOT NULL,
    Telefon VARCHAR(20),
    Email VARCHAR(200),
    Ulke VARCHAR(100) DEFAULT 'Türkiye',
    Sehir VARCHAR(100),
    Ilce VARCHAR(100),
    Adres TEXT,
    DogumTarihi DATE,
    Yas INT,
    Cinsiyet VARCHAR(10),
    KategoriID INT,
    Notlar TEXT,
    ProfilFotografi VARCHAR(500),
    Aktif TINYINT(1) DEFAULT 1,
    OlusturanKullaniciID INT,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    GuncellemeTarihi DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    FOREIGN KEY (KategoriID) REFERENCES MusteriKategorileri(KategoriID) ON DELETE SET NULL,
    FOREIGN KEY (OlusturanKullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE SET NULL,
    INDEX idx_FirmaID (FirmaID),
    INDEX idx_KategoriID (KategoriID),
    INDEX idx_Telefon (Telefon),
    INDEX idx_Email (Email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Todo durumlar tablosu
CREATE TABLE IF NOT EXISTS TodoDurumlar (
    DurumID INT AUTO_INCREMENT PRIMARY KEY,
    FirmaID INT NOT NULL,
    DurumAdi VARCHAR(50) NOT NULL,
    DurumAciklamasi VARCHAR(200),
    Renk VARCHAR(7) DEFAULT '#007bff',
    Sira INT DEFAULT 0,
    Aktif TINYINT(1) DEFAULT 1,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    INDEX idx_FirmaID (FirmaID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Todos (Görevler) tablosu
CREATE TABLE IF NOT EXISTS Todos (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Not: Randevular tablosunda MusteriID zaten tanımlı (yukarıda)

-- Varsayılan veriler
-- Yetki tipleri
INSERT IGNORE INTO YetkiTipleri (YetkiAdi, YetkiAciklamasi) VALUES
('RandevuGoruntuleme', 'Randevuları görüntüleme yetkisi'),
('RandevuOlusturma', 'Yeni randevu oluşturma yetkisi'),
('RandevuDuzenleme', 'Mevcut randevuları düzenleme yetkisi'),
('RandevuSilme', 'Randevu silme yetkisi'),
('KullaniciYonetimi', 'Kullanıcı yönetim yetkisi'),
('FirmaYonetimi', 'Firma yönetim yetkisi'),
('Admin', 'Tam yetki');

-- Varsayılan firma
INSERT IGNORE INTO Firmalar (FirmaAdi, FirmaKodu, Adres, Telefon, Email)
VALUES ('Ana Firma', 'ANA001', 'Merkez Adres', '0212 000 00 00', 'info@anafirma.com');

-- Admin kullanıcı (şifre: admin123 - hash'lenmiş olarak)
-- Not: Bu hash'i werkzeug ile oluşturmanız gerekiyor: generate_password_hash('admin123')
INSERT IGNORE INTO Kullanicilar (KullaniciAdi, Sifre, Ad, Soyad, Email, FirmaID, Admin)
VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/8Kz8Kz2', 'Admin', 'Kullanici', 'admin@anafirma.com', 1, 1);

-- Admin kullanıcıya tüm yetkileri ver
INSERT IGNORE INTO KullaniciYetkileri (KullaniciID, YetkiID)
SELECT 1, yt.YetkiID
FROM YetkiTipleri yt;

-- Varsayılan müşteri kategorileri ekle
INSERT IGNORE INTO MusteriKategorileri (FirmaID, KategoriAdi, Renk, Aciklama)
SELECT f.FirmaID, 'Normal Müşteri', '#28a745', 'Standart müşteri kategorisi' 
FROM Firmalar f
WHERE NOT EXISTS (
    SELECT 1 FROM MusteriKategorileri mk 
    WHERE mk.FirmaID = f.FirmaID AND mk.KategoriAdi = 'Normal Müşteri'
);

INSERT IGNORE INTO MusteriKategorileri (FirmaID, KategoriAdi, Renk, Aciklama)
SELECT f.FirmaID, 'VIP Müşteri', '#dc3545', 'Özel müşteri kategorisi' 
FROM Firmalar f
WHERE NOT EXISTS (
    SELECT 1 FROM MusteriKategorileri mk 
    WHERE mk.FirmaID = f.FirmaID AND mk.KategoriAdi = 'VIP Müşteri'
);

INSERT IGNORE INTO MusteriKategorileri (FirmaID, KategoriAdi, Renk, Aciklama)
SELECT f.FirmaID, 'Yeni Müşteri', '#17a2b8', 'Yeni kayıt olan müşteriler' 
FROM Firmalar f
WHERE NOT EXISTS (
    SELECT 1 FROM MusteriKategorileri mk 
    WHERE mk.FirmaID = f.FirmaID AND mk.KategoriAdi = 'Yeni Müşteri'
);

INSERT IGNORE INTO MusteriKategorileri (FirmaID, KategoriAdi, Renk, Aciklama)
SELECT f.FirmaID, 'Sadık Müşteri', '#ffc107', 'Düzenli gelen müşteriler' 
FROM Firmalar f
WHERE NOT EXISTS (
    SELECT 1 FROM MusteriKategorileri mk 
    WHERE mk.FirmaID = f.FirmaID AND mk.KategoriAdi = 'Sadık Müşteri'
);

SELECT 'CRM veritabanı başarıyla oluşturuldu!' AS Mesaj;
SELECT 'Admin kullanıcı: admin' AS Mesaj;
SELECT 'Admin şifre: admin123' AS Mesaj;

-- Dosya güncellendi: 2025

