# Aktivite Modülü Görünmüyor - Hızlı Çözüm

## Sorun: Aktivite timeline müşteri detay sayfasında görünmüyor

## Çözüm Adımları:

### 1. Veritabanı Tablosunu Oluştur (EN ÖNEMLİ!)

**MySQL için:**
```bash
# Terminal'de (veya MySQL Workbench'te)
mysql -u root -p crandyx_crm_db < database/create_activities_table_mysql.sql
```

**Veya MySQL Workbench'te:**
1. MySQL Workbench'i aç
2. `database/create_activities_table_mysql.sql` dosyasını aç
3. Tüm script'i seç (Ctrl+A)
4. Çalıştır (F9 veya Execute butonu)

**Kontrol:**
```sql
-- MySQL'de tablo var mı kontrol et
SHOW TABLES LIKE 'Aktiviteler';

-- Sütunları kontrol et
DESCRIBE Aktiviteler;
```

### 2. Uygulamayı Yeniden Başlat

```bash
# Eğer uygulama çalışıyorsa durdur (Ctrl+C)
# Sonra tekrar başlat:
python run.py
```

### 3. Tarayıcıda Test Et

1. Tarayıcıda `http://localhost:5000` adresine git
2. Giriş yap
3. **Müşteriler** menüsüne git
4. Bir müşteri seç ve **Detay** butonuna tıkla
5. Modal açılacak, en altta **"Activity Timeline / Communication History"** bölümü görünmeli

### 4. Hala Görünmüyorsa - Browser Console Kontrolü

1. Tarayıcıda **F12** tuşuna bas (Developer Tools)
2. **Console** sekmesine git
3. Müşteri detay sayfasını aç
4. Kırmızı hata mesajları var mı kontrol et

**Olası hatalar:**
- `Aktiviteler table doesn't exist` → Migration çalıştırılmamış
- `Cannot read property 'aktiviteler'` → Template hatası
- `404 Not Found` → Route çalışmıyor

### 5. Server Log Kontrolü

Terminal'de (uygulama çalışırken) hata mesajları var mı kontrol et:
- `Aktivite yükleme hatası: ...`
- `Table 'Aktiviteler' doesn't exist`
- `ImportError: cannot import name 'Aktivite'`

## Hızlı Test

```bash
# Terminal'de
python test_activity_module.py
```

Bu script tablo var mı kontrol eder.

## Manuel Tablo Oluşturma (Alternatif)

Eğer migration script'i çalışmıyorsa, MySQL'de manuel olarak:

```sql
USE crandyx_crm_db;

CREATE TABLE IF NOT EXISTS Aktiviteler (
    AktiviteID INT AUTO_INCREMENT PRIMARY KEY,
    MusteriID INT NOT NULL,
    FirmaID INT NOT NULL,
    AktiviteTipi VARCHAR(50) NOT NULL,
    Baslik VARCHAR(200) NOT NULL,
    Aciklama TEXT,
    IlgiliNesneTipi VARCHAR(50) NULL,
    IlgiliNesneID INT NULL,
    AktiviteTarihi DATETIME NOT NULL,
    EkBilgiler TEXT NULL,
    OlusturanKullaniciID INT NULL,
    OlusturmaTarihi DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    GuncellemeTarihi DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (MusteriID) REFERENCES Musteriler(MusteriID) ON DELETE CASCADE,
    FOREIGN KEY (FirmaID) REFERENCES Firmalar(FirmaID) ON DELETE CASCADE,
    FOREIGN KEY (OlusturanKullaniciID) REFERENCES Kullanicilar(KullaniciID) ON DELETE SET NULL,
    INDEX idx_musteri (MusteriID),
    INDEX idx_firma (FirmaID),
    INDEX idx_aktivite_tarihi (AktiviteTarihi),
    INDEX idx_musteri_tarih (MusteriID, AktiviteTarihi DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## Sorun Devam Ediyorsa

1. **Browser Console'u kontrol et** (F12 → Console)
2. **Server log'larını kontrol et** (terminal çıktısı)
3. **Veritabanı bağlantısını kontrol et**
4. Hata mesajlarını paylaş, birlikte çözelim!





