# MySQL Veritabanı Kurulum Rehberi

Bu rehber, CRM uygulamasını MySQL veritabanı ile kullanmak için gerekli adımları açıklar.

## Gereksinimler

- MySQL 5.7+ veya MariaDB 10.3+
- MySQL kullanıcı hesabı ve yetkileri
- Python 3.8+
- PyMySQL paketi (`pip install PyMySQL`)

## Kurulum Adımları

### 1. MySQL Veritabanını Oluşturma

#### Yöntem A: MySQL Command Line Kullanarak

```bash
# MySQL'e bağlan
mysql -u root -p

# Script'i çalıştır
source database/create_database_mysql.sql

# veya direkt
mysql -u root -p < database/create_database_mysql.sql
```

#### Yöntem B: MySQL Workbench veya phpMyAdmin Kullanarak

1. MySQL Workbench veya phpMyAdmin'i açın
2. `database/create_database_mysql.sql` dosyasını açın
3. Script'in tamamını seçip çalıştırın

### 2. Veritabanı Bağlantı Ayarları

#### .env Dosyasını Düzenleme

`.env` dosyanızı açın ve MySQL bağlantı bilgilerini girin:

```env
DATABASE_URL=mysql+pymysql://kullanici_adi:sifre@localhost:3306/Crandyx_CRM_DB?charset=utf8mb4
```

**Örnek:**
```env
DATABASE_URL=mysql+pymysql://root:yourpassword@localhost:3306/Crandyx_CRM_DB?charset=utf8mb4
```

#### SistemAyarlar Üzerinden (Web Arayüzü)

1. Uygulamaya giriş yapın (admin/admin123)
2. Ayarlar > Veritabanı Ayarları sayfasına gidin
3. Veritabanı tipini **MySQL** seçin
4. MySQL bağlantı bilgilerini girin:
   - **Sunucu:** localhost (veya MySQL sunucu adresi)
   - **Port:** 3306
   - **Veritabanı:** Crandyx_CRM_DB
   - **Kullanıcı Adı:** MySQL kullanıcı adınız
   - **Şifre:** MySQL şifreniz (şifrelenmiş olarak saklanacak)
   - **Charset:** utf8mb4
5. Kaydet butonuna tıklayın
6. Uygulamayı yeniden başlatın

### 3. Veritabanı Kullanıcısı Oluşturma (Opsiyonel)

Güvenlik için özel bir MySQL kullanıcısı oluşturmanız önerilir:

```sql
-- MySQL'de root olarak giriş yapın
mysql -u root -p

-- Yeni kullanıcı oluştur
CREATE USER 'crm_user'@'localhost' IDENTIFIED BY 'güvenli_şifre';

-- Yetkileri ver
GRANT ALL PRIVILEGES ON Crandyx_CRM_DB.* TO 'crm_user'@'localhost';

-- Değişiklikleri uygula
FLUSH PRIVILEGES;
```

### 4. Uygulamayı Başlatma

```bash
python app.py
```

## Varsayılan Kullanıcı Bilgileri

- **Kullanıcı Adı:** admin
- **Şifre:** admin123

**ÖNEMLİ:** İlk girişten sonra şifrenizi değiştirin!

## Tablolar

Script aşağıdaki tabloları oluşturur:

- Firmalar
- Kullanicilar
- AktifOturumlar
- KullaniciLoglari
- YetkiTipleri
- KullaniciYetkileri
- Randevular
- RandevuYetkileri
- RandevuDefterAyarlar
- RandevuDefterBloklar
- RandevuReferanslari
- RandevuIslemler
- Bildirimler
- RandevuHatirlatmalar
- RandevuSMSHatirlatmalar
- FirmaEmailAyarlari
- FirmaSMSAyarlari
- FirmaWhatsAppAyarlari
- SistemAyarlar
- MusteriKategorileri
- Musteriler
- TodoDurumlar
- Todos

## Varsayılan Veriler

Script aşağıdaki varsayılan verileri ekler:

- **Yetki Tipleri:** RandevuGoruntuleme, RandevuOlusturma, RandevuDuzenleme, RandevuSilme, KullaniciYonetimi, FirmaYonetimi, Admin
- **Varsayılan Firma:** Ana Firma (ANA001)
- **Admin Kullanıcı:** admin/admin123
- **Müşteri Kategorileri:** Normal Müşteri, VIP Müşteri, Yeni Müşteri, Sadık Müşteri

## Karakter Seti

Veritabanı `utf8mb4` karakter seti ile oluşturulur, bu sayede Türkçe karakterler ve emojiler sorunsuz çalışır.

## Sorun Giderme

### Bağlantı Hatası

1. MySQL servisinin çalıştığından emin olun:
   ```bash
   # Windows
   net start MySQL80
   
   # Linux/Mac
   sudo systemctl status mysql
   ```

2. Kullanıcı adı ve şifrenin doğru olduğunu kontrol edin

3. Firewall ayarlarını kontrol edin (port 3306)

### Şifreleme Hatası

Eğer şifre şifreleme sistemi hata veriyorsa, `.env` dosyanızda `SECRET_KEY` tanımlı olduğundan emin olun.

## Notlar

- MySQL'de `BIT` yerine `TINYINT(1)` kullanılır
- MySQL'de `IDENTITY(1,1)` yerine `AUTO_INCREMENT` kullanılır
- MySQL'de `GETDATE()` yerine `CURRENT_TIMESTAMP` kullanılır
- MySQL'de `NVARCHAR` yerine `VARCHAR` kullanılır (utf8mb4 charset ile)
- Foreign key constraint'ler MySQL'de otomatik olarak index oluşturur

