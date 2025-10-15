-- Kullanıcı tablosuna LogModulu sütunu ekle
ALTER TABLE Kullanicilar 
ADD LogModulu BIT DEFAULT 0;

-- Mevcut admin kullanıcılara log modülü yetkisi ver
UPDATE Kullanicilar 
SET LogModulu = 1 
WHERE Admin = 1;
