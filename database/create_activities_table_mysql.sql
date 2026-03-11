-- =====================================================
-- Activity / İletişim Geçmişi Tablosu - MySQL
-- =====================================================
-- Bu script MySQL veritabanı için Activity tablosunu oluşturur
-- Hem MySQL 5.7+ hem MySQL 8.0+ ile uyumludur

USE crandyx_crm_db; -- Veritabanı adınızı buraya yazın

CREATE TABLE IF NOT EXISTS Aktiviteler (
    AktiviteID INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Müşteri ilişkisi (zorunlu)
    MusteriID INT NOT NULL,
    FOREIGN KEY (MusteriID) REFERENCES Musteriler(MusteriID) ON DELETE CASCADE,
    
    -- Firma ilişkisi (filtreleme için)
    FirmaID INT NOT NULL,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    
    -- Aktivite tipi: 'call', 'email', 'note', 'appointment', 'task', 'meeting', 'proposal', vb.
    AktiviteTipi VARCHAR(50) NOT NULL,
    
    -- Başlık ve açıklama
    Baslik VARCHAR(200) NOT NULL,
    Aciklama TEXT,
    
    -- İlişkili nesne (opsiyonel - genişletilebilirlik için)
    -- Örn: 'appointment', 'task', 'proposal', 'invoice' vb.
    IlgiliNesneTipi VARCHAR(50) NULL,
    IlgiliNesneID INT NULL,
    
    -- Aktivite tarihi/saati (kronolojik sıralama için)
    AktiviteTarihi DATETIME NOT NULL,
    
    -- Ek bilgiler (JSON formatında saklanabilir - opsiyonel)
    -- Örn: telefon numarası, email konusu, görüşme süresi vb.
    EkBilgiler JSON NULL,
    
    -- Oluşturan kullanıcı
    OlusturanKullaniciID INT NULL,
    FOREIGN KEY (OlusturanKullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE SET NULL,
    
    -- Tarih alanları
    OlusturmaTarihi DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    GuncellemeTarihi DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Index'ler (performans için)
    INDEX idx_musteri (MusteriID),
    INDEX idx_firma (FirmaID),
    INDEX idx_aktivite_tarihi (AktiviteTarihi),
    INDEX idx_aktivite_tipi (AktiviteTipi),
    INDEX idx_ilgili_nesne (IlgiliNesneTipi, IlgiliNesneID),
    INDEX idx_olusturan (OlusturanKullaniciID),
    
    -- Aktivite tarihi ve müşteri kombinasyonu için composite index
    INDEX idx_musteri_tarih (MusteriID, AktiviteTarihi DESC)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Müşteri iletişim geçmişi ve aktivite kayıtları';

-- Aktivite tipleri için kontrol (opsiyonel - uygulama tarafında da kontrol edilebilir)
-- MySQL 8.0+ için CHECK constraint desteği var
-- ALTER TABLE Aktiviteler ADD CONSTRAINT chk_aktivite_tipi 
-- CHECK (AktiviteTipi IN ('call', 'email', 'note', 'appointment', 'task', 'meeting', 'proposal', 'other'));





