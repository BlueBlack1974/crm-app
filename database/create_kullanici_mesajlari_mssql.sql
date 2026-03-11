-- Kullanıcılar Arası Mesajlaşma Tablosu
-- MSSQL Server için

USE CRM_DB;
GO

-- KullaniciMesajlari tablosu
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[KullaniciMesajlari]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[KullaniciMesajlari] (
        MesajID INT IDENTITY(1,1) PRIMARY KEY,
        GonderenID INT NOT NULL,
        AliciID INT NOT NULL,
        Mesaj NVARCHAR(MAX) NOT NULL,
        Okundu BIT DEFAULT 0,
        GonderenSilindi BIT DEFAULT 0,
        AliciSilindi BIT DEFAULT 0,
        OlusturmaTarihi DATETIME DEFAULT GETDATE(),
        OkunmaTarihi DATETIME NULL,
        FOREIGN KEY (GonderenID) REFERENCES Kullanicilar(KullaniciID) ON DELETE CASCADE,
        FOREIGN KEY (AliciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE CASCADE
    );
    
    -- Index'ler
    CREATE INDEX idx_GonderenID ON KullaniciMesajlari(GonderenID);
    CREATE INDEX idx_AliciID ON KullaniciMesajlari(AliciID);
    CREATE INDEX idx_Okundu ON KullaniciMesajlari(Okundu);
    CREATE INDEX idx_OlusturmaTarihi ON KullaniciMesajlari(OlusturmaTarihi);
    
    PRINT 'KullaniciMesajlari tablosu oluşturuldu.';
END
ELSE
BEGIN
    PRINT 'KullaniciMesajlari tablosu zaten mevcut.';
END
GO
