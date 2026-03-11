-- ProfilFotografi kolonunu Kullanicilar tablosuna ekle
-- MySQL için

ALTER TABLE Kullanicilar 
ADD COLUMN ProfilFotografi VARCHAR(500) NULL 
AFTER LogModulu;

-- Kolonun eklendiğini kontrol et
-- SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH 
-- FROM INFORMATION_SCHEMA.COLUMNS 
-- WHERE TABLE_SCHEMA = DATABASE() 
--   AND TABLE_NAME = 'Kullanicilar' 
--   AND COLUMN_NAME = 'ProfilFotografi';




