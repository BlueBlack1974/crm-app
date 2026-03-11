-- WhatsApp ayarları tablosuna TestNumarasi kolonu ekle
-- MySQL için
ALTER TABLE FirmaWhatsAppAyarlari 
ADD COLUMN TestNumarasi VARCHAR(20) NULL 
AFTER WebhookVerifyToken;

-- SQL Server için (eğer SQL Server kullanıyorsanız)
-- ALTER TABLE FirmaWhatsAppAyarlari 
-- ADD TestNumarasi NVARCHAR(20) NULL;

