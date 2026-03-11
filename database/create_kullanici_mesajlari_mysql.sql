-- Kullanıcılar Arası Mesajlaşma Tablosu
-- MySQL için

USE httpdtjs_Crandyx_CRM_DB;

CREATE TABLE IF NOT EXISTS KullaniciMesajlari (
    MesajID INT AUTO_INCREMENT PRIMARY KEY,
    GonderenID INT NOT NULL,
    AliciID INT NOT NULL,
    Mesaj TEXT NOT NULL,
    Okundu TINYINT(1) DEFAULT 0,
    GonderenSilindi TINYINT(1) DEFAULT 0,
    AliciSilindi TINYINT(1) DEFAULT 0,
    OlusturmaTarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    OkunmaTarihi DATETIME NULL,
    INDEX idx_GonderenID (GonderenID),
    INDEX idx_AliciID (AliciID),
    INDEX idx_Okundu (Okundu),
    INDEX idx_OlusturmaTarihi (OlusturmaTarihi),
    FOREIGN KEY (GonderenID) REFERENCES Kullanicilar(KullaniciID) ON DELETE CASCADE,
    FOREIGN KEY (AliciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
