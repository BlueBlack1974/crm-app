-- Veritabanını seç (kendi veritabanı adınıza göre değiştirin)
USE crandyx_crm_db;

-- Kullanıcı tablosuna WhatsAppModulu sütunu ekle
ALTER TABLE Kullanicilar 
ADD WhatsAppModulu TINYINT(1) DEFAULT 0;

-- Mevcut admin kullanıcılara WhatsApp modülü yetkisi ver
-- Safe update mode için PRIMARY KEY kullanıyoruz
UPDATE Kullanicilar 
SET WhatsAppModulu = 1 
WHERE Admin = 1 AND KullaniciID > 0;


