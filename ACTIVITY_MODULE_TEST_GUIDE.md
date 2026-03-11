# Aktivite Modülü Test Rehberi

## 1. Veritabanı Migration (İlk Kurulum)

### MySQL için:
```bash
# MySQL'e bağlan
mysql -u root -p

# Veritabanını seç
USE crandyx_crm_db;

# Migration script'ini çalıştır
SOURCE database/create_activities_table_mysql.sql;

# Veya direkt:
mysql -u root -p crandyx_crm_db < database/create_activities_table_mysql.sql
```

### MSSQL için:
```bash
# SQL Server Management Studio'da veya sqlcmd ile:
sqlcmd -S localhost -d crandyx_crm_db -i database/create_activities_table_mssql.sql
```

**Kontrol:**
```sql
-- Tablo oluştu mu kontrol et
SHOW TABLES LIKE 'Aktiviteler';  -- MySQL
-- veya
SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'Aktiviteler';  -- MSSQL

-- Sütunları kontrol et
DESCRIBE Aktiviteler;  -- MySQL
-- veya
SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Aktiviteler';  -- MSSQL
```

## 2. Uygulamayı Başlat

```bash
# Terminal'de proje dizinine git
cd D:\Yazılım_Projeler\Python\CRM

# Uygulamayı başlat
python run.py
```

Uygulama `http://localhost:5000` adresinde çalışacak.

## 3. Web Arayüzünde Test

### Adım 1: Giriş Yap
- Tarayıcıda `http://localhost:5000/login` adresine git
- Kullanıcı adı ve şifre ile giriş yap

### Adım 2: Müşteri Detay Sayfasına Git
1. **Müşteriler** menüsüne tıkla
2. Herhangi bir müşterinin **detay** butonuna tıkla (veya müşteri listesinden bir müşteri seç)
3. Müşteri detay modal'ı açılacak

### Adım 3: Aktivite Timeline'ını Kontrol Et
- Modal'ın alt kısmında **"Activity Timeline / Communication History"** bölümü görünmeli
- Eğer aktivite yoksa "No activities found" mesajı görünecek

### Adım 4: Manuel Aktivite Ekle
1. **"Add Activity"** butonuna tıkla
2. Modal açılacak:
   - **Activity Type**: call, email, note, meeting, other seçenekleri
   - **Title**: Aktivite başlığı (örn: "Telefon görüşmesi")
   - **Description**: Detaylı açıklama (opsiyonel)
   - **Activity Date & Time**: Tarih ve saat
3. **Save** butonuna tıkla
4. Sayfa yenilenecek ve yeni aktivite timeline'da görünecek

### Adım 5: Aktivite Tiplerini Test Et
Her aktivite tipi için farklı ikon ve renk görünmeli:
- 📞 **call** (mavi) - Telefon görüşmesi
- ✉️ **email** (açık mavi) - E-posta
- 📝 **note** (sarı) - Not
- 📅 **appointment** (yeşil) - Randevu
- ✅ **task** (gri) - Görev

### Adım 6: Aktivite Silme Testi
- Timeline'daki bir aktivitenin yanındaki **çöp kutusu** ikonuna tıkla
- Onay mesajı çıkacak
- Onayladıktan sonra aktivite silinecek

## 4. Otomatik Entegrasyon Testi

### Randevu Entegrasyonu:
1. **Randevular** menüsüne git
2. **Yeni Randevu** oluştur
3. Bir müşteri seç ve randevuyu kaydet
4. Müşteri detay sayfasına git
5. Timeline'da otomatik olarak **"Randevu: [Başlık]"** aktivitesi görünmeli
6. Aktiviteye tıklayınca randevu detay sayfasına yönlendirilmeli

### Görev Entegrasyonu:
1. **Görevler** menüsüne git
2. Yeni bir görev oluştur (müşteri bilgisi ile)
3. Görevi kaydet
4. Müşteri detay sayfasına git
5. Timeline'da otomatik olarak **"Görev: [Başlık]"** aktivitesi görünmeli
6. Görev tamamlandığında aktivite güncellenmeli

## 5. API Endpoint Testleri

### Postman veya Browser Console kullanarak:

#### Test 1: Aktivite Listesi
```javascript
// Browser Console'da (F12)
fetch('/api/aktiviteler?customer_id=1&limit=10')
  .then(r => r.json())
  .then(data => console.log(data));
```

#### Test 2: Aktivite Oluşturma
```javascript
fetch('/api/aktiviteler', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    musteri_id: 1,
    aktivite_tipi: 'call',
    baslik: 'Test Telefon Görüşmesi',
    aciklama: 'Bu bir test aktivitesidir',
    aktivite_tarihi: new Date().toISOString()
  })
})
.then(r => r.json())
.then(data => console.log(data));
```

#### Test 3: Aktivite Güncelleme
```javascript
fetch('/api/aktiviteler/1', {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    baslik: 'Güncellenmiş Başlık',
    aciklama: 'Güncellenmiş açıklama'
  })
})
.then(r => r.json())
.then(data => console.log(data));
```

#### Test 4: Aktivite Silme
```javascript
fetch('/api/aktiviteler/1', {
  method: 'DELETE'
})
.then(r => r.json())
.then(data => console.log(data));
```

## 6. Veritabanı Kontrolleri

### Aktivite Kayıtlarını Görüntüle:
```sql
-- Tüm aktiviteler
SELECT * FROM Aktiviteler ORDER BY AktiviteTarihi DESC;

-- Belirli müşterinin aktiviteleri
SELECT * FROM Aktiviteler WHERE MusteriID = 1 ORDER BY AktiviteTarihi DESC;

-- Aktivite tipi dağılımı
SELECT AktiviteTipi, COUNT(*) as sayi 
FROM Aktiviteler 
GROUP BY AktiviteTipi;

-- Son 7 günde aktivitesi olmayan müşteriler
SELECT m.*
FROM Musteriler m
WHERE m.Aktif = 1
  AND m.MusteriID NOT IN (
    SELECT DISTINCT a.MusteriID
    FROM Aktiviteler a
    WHERE a.AktiviteTarihi >= DATE_SUB(NOW(), INTERVAL 7 DAY)
  );
```

## 7. Hata Kontrolü

### Olası Hatalar ve Çözümleri:

**1. "Table 'Aktiviteler' doesn't exist"**
- Çözüm: Migration script'ini çalıştırın

**2. "Foreign key constraint fails"**
- Çözüm: Müşteri veya firma ID'sinin geçerli olduğundan emin olun

**3. "No activities found" ama randevu var**
- Çözüm: Randevu oluşturulduktan sonra aktivite otomatik oluşmalı. Eğer oluşmadıysa:
  - Console'da hata var mı kontrol edin
  - `app/routes/randevu.py` dosyasında entegrasyon kodunun olduğundan emin olun

**4. Timeline görünmüyor**
- Çözüm: 
  - `app/routes/musteri.py` dosyasında `aktiviteler` parametresinin template'e gönderildiğinden emin olun
  - Browser console'da JavaScript hatası var mı kontrol edin

## 8. Performans Testi

### Çok sayıda aktivite ile test:
```sql
-- Test verisi oluştur (100 aktivite)
INSERT INTO Aktiviteler (MusteriID, FirmaID, AktiviteTipi, Baslik, Aciklama, AktiviteTarihi, OlusturmaTarihi, GuncellemeTarihi)
SELECT 
    1 as MusteriID,
    1 as FirmaID,
    CASE (RAND() * 4)
        WHEN 0 THEN 'call'
        WHEN 1 THEN 'email'
        WHEN 2 THEN 'note'
        ELSE 'meeting'
    END as AktiviteTipi,
    CONCAT('Test Aktivite ', n) as Baslik,
    'Test açıklama' as Aciklama,
    DATE_SUB(NOW(), INTERVAL n DAY) as AktiviteTarihi,
    NOW() as OlusturmaTarihi,
    NOW() as GuncellemeTarihi
FROM (
    SELECT @row := @row + 1 as n
    FROM (SELECT 0 UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) t1,
    (SELECT 0 UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) t2,
    (SELECT @row := 0) r
    LIMIT 100
) numbers;
```

Sonra müşteri detay sayfasında timeline'ın hızlı yüklendiğini kontrol edin.

## 9. Test Checklist

- [ ] Migration başarıyla çalıştı
- [ ] Tablo oluşturuldu
- [ ] Uygulama hatasız başladı
- [ ] Müşteri detay sayfasında timeline görünüyor
- [ ] Manuel aktivite eklenebiliyor
- [ ] Aktivite silinebiliyor
- [ ] Randevu oluşturulunca otomatik aktivite oluşuyor
- [ ] Görev oluşturulunca otomatik aktivite oluşuyor
- [ ] API endpoint'leri çalışıyor
- [ ] Aktivite tiplerine göre doğru ikonlar görünüyor
- [ ] İlgili randevu/göreve link çalışıyor

## 10. Hızlı Test Komutları

### Python Console'da test:
```python
# Python shell'de
from app import create_app
from app.extensions import db
from app.models import Aktivite, Musteri

app = create_app()
with app.app_context():
    # İlk müşteriyi bul
    musteri = Musteri.query.first()
    print(f"Müşteri: {musteri.MusteriAdi} {musteri.MusteriSoyadi}")
    
    # Aktivite sayısı
    aktivite_sayisi = Aktivite.query.filter_by(MusteriID=musteri.MusteriID).count()
    print(f"Aktivite sayısı: {aktivite_sayisi}")
    
    # Son aktivite
    son_aktivite = Aktivite.query.filter_by(MusteriID=musteri.MusteriID).order_by(Aktivite.AktiviteTarihi.desc()).first()
    if son_aktivite:
        print(f"Son aktivite: {son_aktivite.Baslik} - {son_aktivite.AktiviteTipi}")
```

## Sorun Giderme

Eğer bir sorunla karşılaşırsanız:

1. **Browser Console'u açın** (F12) ve hataları kontrol edin
2. **Server log'larını kontrol edin** (terminal çıktısı)
3. **Veritabanı bağlantısını kontrol edin**
4. **Model import'larını kontrol edin** (`app/models.py`)

Herhangi bir hata görürseniz, hata mesajını paylaşın, birlikte çözelim!





