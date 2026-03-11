# Aktivite / İletişim Geçmişi Modülü Dokümantasyonu

## Genel Bakış

Bu modül, müşterilerle yapılan tüm iletişim ve işlemleri kronolojik bir timeline olarak gösterir. Telefon görüşmeleri, e-postalar, notlar, randevular ve görevler gibi tüm aktiviteler tek bir yerde toplanır.

## Veritabanı Yapısı

### Tablo: `Aktiviteler`

**MySQL ve MSSQL uyumlu tasarım:**

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| AktiviteID | INT | Primary key (AUTO_INCREMENT / IDENTITY) |
| MusteriID | INT | Müşteri foreign key (NOT NULL) |
| FirmaID | INT | Firma foreign key (NOT NULL) |
| AktiviteTipi | VARCHAR(50) | 'call', 'email', 'note', 'appointment', 'task', 'meeting', 'proposal', 'other' |
| Baslik | VARCHAR(200) | Aktivite başlığı (NOT NULL) |
| Aciklama | TEXT / NVARCHAR(MAX) | Detaylı açıklama |
| IlgiliNesneTipi | VARCHAR(50) | 'appointment', 'task', 'proposal', vb. (opsiyonel) |
| IlgiliNesneID | INT | İlgili nesnenin ID'si (opsiyonel) |
| AktiviteTarihi | DATETIME / DATETIME2 | Aktivite tarihi/saati (NOT NULL) |
| EkBilgiler | TEXT / NVARCHAR(MAX) | JSON formatında ek bilgiler |
| OlusturanKullaniciID | INT | Oluşturan kullanıcı (opsiyonel) |
| OlusturmaTarihi | DATETIME / DATETIME2 | Kayıt oluşturma tarihi |
| GuncellemeTarihi | DATETIME / DATETIME2 | Son güncelleme tarihi |

**Index'ler:**
- `idx_musteri` (MusteriID)
- `idx_firma` (FirmaID)
- `idx_aktivite_tarihi` (AktiviteTarihi)
- `idx_aktivite_tipi` (AktiviteTipi)
- `idx_ilgili_nesne` (IlgiliNesneTipi, IlgiliNesneID)
- `idx_olusturan` (OlusturanKullaniciID)
- `idx_musteri_tarih` (MusteriID, AktiviteTarihi DESC) - Composite index

## Kurulum

### 1. Veritabanı Migration

**MySQL için:**
```bash
mysql -u kullanici -p crandyx_crm_db < database/create_activities_table_mysql.sql
```

**MSSQL için:**
```bash
sqlcmd -S server -d crandyx_crm_db -i database/create_activities_table_mssql.sql
```

### 2. Model ve Route'lar

Model ve route'lar zaten oluşturulmuş durumda:
- `app/models.py` - `Aktivite` modeli
- `app/routes/aktivite.py` - Activity blueprint
- `app/__init__.py` - Blueprint kayıtlı

## API Endpoint'leri

### 1. Aktivite Listesi
```
GET /api/aktiviteler?customer_id=123&limit=50&offset=0&activity_type=call
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "musteri_id": 123,
      "aktivite_tipi": "call",
      "baslik": "Telefon görüşmesi",
      "aciklama": "Müşteri ile görüşüldü...",
      "aktivite_tarihi": "2024-01-15T14:30:00",
      ...
    }
  ],
  "total": 25,
  "limit": 50,
  "offset": 0
}
```

### 2. Aktivite Oluşturma
```
POST /api/aktiviteler
Content-Type: application/json

{
  "musteri_id": 123,
  "aktivite_tipi": "call",
  "baslik": "Telefon görüşmesi",
  "aciklama": "Müşteri ile görüşüldü...",
  "aktivite_tarihi": "2024-01-15T14:30:00",
  "ilgili_nesne_tipi": "appointment",
  "ilgili_nesne_id": 456,
  "ek_bilgiler": {"telefon": "5551234567", "sure": "15 dakika"}
}
```

### 3. Aktivite Güncelleme
```
PUT /api/aktiviteler/123
Content-Type: application/json

{
  "baslik": "Güncellenmiş başlık",
  "aciklama": "Güncellenmiş açıklama"
}
```

### 4. Aktivite Silme
```
DELETE /api/aktiviteler/123
```

## Mevcut Modüllerle Entegrasyon

### Randevu Modülü

Randevu oluşturulduğunda veya güncellendiğinde otomatik olarak aktivite kaydı oluşturulur:

```python
from app.routes.aktivite import create_activity_for_appointment

# Randevu oluşturulduktan sonra
create_activity_for_appointment(randevu)
```

### Görev Modülü

Görev oluşturulduğunda, güncellendiğinde veya tamamlandığında otomatik aktivite kaydı oluşturulur:

```python
from app.routes.aktivite import create_activity_for_task

# Görev oluşturulduktan sonra
create_activity_for_task(todo)
```

## Örnek Sorgular

### 1. Müşterinin Son 10 Aktivitesi (ORM)

```python
from app.routes.aktivite import get_customer_activities

aktiviteler = get_customer_activities(musteri_id=123, limit=10)
```

### 2. Son 7 Günde Aktivitesi Olmayan Müşteriler (ORM)

```python
from app.routes.aktivite import get_customers_without_recent_activities

pasif_musteriler = get_customers_without_recent_activities(days=7)
```

### 3. SQL Sorguları (Manuel)

**MySQL:**
```sql
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

**MSSQL:**
```sql
-- Son 7 günde aktivitesi olmayan müşteriler
SELECT m.*
FROM Musteriler m
WHERE m.Aktif = 1
  AND m.MusteriID NOT IN (
    SELECT DISTINCT a.MusteriID
    FROM Aktiviteler a
    WHERE a.AktiviteTarihi >= DATEADD(DAY, -7, GETDATE())
  );
```

## Genişletilebilirlik

### 1. Dosya Eklentileri (Attachments)

Gelecekte eklenebilecek tablo:
```sql
CREATE TABLE AktiviteEkleri (
    EklentiID INT PRIMARY KEY,
    AktiviteID INT FOREIGN KEY REFERENCES Aktiviteler(AktiviteID),
    DosyaAdi VARCHAR(255),
    DosyaYolu VARCHAR(500),
    DosyaBoyutu INT,
    OlusturmaTarihi DATETIME
);
```

### 2. Etiketler (Tags)

Gelecekte eklenebilecek tablolar:
```sql
-- Etiketler tablosu
CREATE TABLE AktiviteEtiketleri (
    EtiketID INT PRIMARY KEY,
    EtiketAdi VARCHAR(50),
    Renk VARCHAR(7)
);

-- Çoktan çoğa ilişki
CREATE TABLE AktiviteEtiketBaglantilari (
    AktiviteID INT,
    EtiketID INT,
    PRIMARY KEY (AktiviteID, EtiketID)
);
```

### 3. Atama ve Raporlama

Mevcut yapı zaten `OlusturanKullaniciID` alanını içeriyor. Kullanıcı bazlı raporlar için:

```python
# Belirli kullanıcının aktiviteleri
aktiviteler = Aktivite.query.filter_by(
    OlusturanKullaniciID=user_id,
    FirmaID=firma_id
).order_by(Aktivite.AktiviteTarihi.desc()).all()
```

## Aktivite Tipleri

- **call**: Telefon görüşmesi
- **email**: E-posta
- **note**: Not
- **appointment**: Randevu (otomatik oluşturulur)
- **task**: Görev (otomatik oluşturulur)
- **meeting**: Toplantı
- **proposal**: Teklif (gelecekte)
- **other**: Diğer

## Mimari Notlar

1. **Veritabanı Bağımsızlığı**: SQLAlchemy ORM kullanılarak MySQL ve MSSQL arasında sorunsuz geçiş sağlanır.

2. **Performans**: Composite index (`idx_musteri_tarih`) müşteri bazlı timeline sorgularını hızlandırır.

3. **Genişletilebilirlik**: `IlgiliNesneTipi` ve `IlgiliNesneID` alanları sayesinde yeni modüller kolayca entegre edilebilir.

4. **JSON Desteği**: `EkBilgiler` alanı JSON formatında esnek veri saklama imkanı sunar.

5. **Otomatik Entegrasyon**: Randevu ve görev modülleriyle otomatik entegrasyon sayesinde manuel aktivite girişi minimuma indirilir.

## Kullanım Örnekleri

### Manuel Aktivite Ekleme

```python
from app.models import Aktivite
from datetime import datetime

aktivite = Aktivite(
    MusteriID=123,
    FirmaID=1,
    AktiviteTipi='call',
    Baslik='Telefon görüşmesi',
    Aciklama='Müşteri ile randevu hakkında konuşuldu.',
    AktiviteTarihi=datetime.now(),
    OlusturanKullaniciID=session['user_id']
)
db.session.add(aktivite)
db.session.commit()
```

### Timeline Görüntüleme

Müşteri detay sayfasında (`musteri_detay_modal.html`) timeline otomatik olarak gösterilir. Aktivite tiplerine göre farklı ikonlar ve renkler kullanılır.

## Sorun Giderme

### Migration Hataları

Eğer tablo zaten varsa:
- MySQL: `CREATE TABLE IF NOT EXISTS` kullanılır
- MSSQL: `IF NOT EXISTS` kontrolü yapılır

### Foreign Key Hataları

Müşteri veya firma silinirse, aktiviteler CASCADE ile silinir. Bu davranışı değiştirmek için migration scriptlerini düzenleyin.

## Gelecek Geliştirmeler

1. ✅ Temel aktivite modülü
2. ✅ Randevu entegrasyonu
3. ✅ Görev entegrasyonu
4. ⏳ Dosya ekleri
5. ⏳ Etiketler
6. ⏳ Aktivite şablonları
7. ⏳ Toplu aktivite işlemleri
8. ⏳ Aktivite raporları





