# CRM - Randevu Defteri Sistemi

MSSQL Server ve Python Flask kullanılarak geliştirilmiş bir randevu defteri ve kullanıcı yönetim sistemi.

## Özellikler

- **Firma Bazlı Kullanıcı Yönetimi**: Her kullanıcı bir firmaya bağlı
- **Yetki Sistemi**: Kullanıcıların randevu görüntüleme, düzenleme ve silme yetkileri
- **Randevu Yönetimi**: Randevu oluşturma, düzenleme, onaylama ve takip
- **Admin Paneli**: Tam yetkili admin kullanıcı
- **Responsive Tasarım**: Bootstrap 5 ile modern arayüz

## Kurulum

### Gereksinimler

- Python 3.8+
- MSSQL Server
- ODBC Driver 17 for SQL Server

### 1. Projeyi İndirin

```bash
git clone <repository-url>
cd CRM
```

### 2. Python Sanal Ortamı Oluşturun

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# veya
source venv/bin/activate  # Linux/Mac
```

### 3. Gerekli Paketleri Yükleyin

```bash
pip install -r requirements.txt
```

### 4. Veritabanını Kurun

1. MSSQL Server'da `database/create_database.sql` dosyasını çalıştırın
2. Veritabanı bağlantı bilgilerini `config.py` dosyasında güncelleyin

### 5. Ortam Değişkenlerini Ayarlayın

`env_example.txt` dosyasını `.env` olarak kopyalayın ve kendi değerlerinizi girin:

```bash
copy env_example.txt .env
```

`.env` dosyasını düzenleyin:

```
SECRET_KEY=your-very-secret-key-here
DATABASE_URL=mssql+pyodbc://sa:YourPassword@localhost/CRM_DB?driver=ODBC+Driver+17+for+SQL+Server
```

### 6. Uygulamayı Çalıştırın

```bash
python app.py
```

Uygulama `http://localhost:5000` adresinde çalışacaktır.

## Varsayılan Giriş Bilgileri

- **Kullanıcı Adı**: admin
- **Şifre**: admin123

## Veritabanı Yapısı

### Tablolar

- **Firmalar**: Firma bilgileri
- **Kullanicilar**: Kullanıcı bilgileri ve firma bağlantısı
- **YetkiTipleri**: Sistem yetki tipleri
- **KullaniciYetkileri**: Kullanıcı-yetki ilişkileri
- **Randevular**: Randevu kayıtları
- **RandevuYetkileri**: Randevu-kullanıcı yetki ilişkileri

### Yetki Tipleri

- `RandevuGoruntuleme`: Randevuları görüntüleme
- `RandevuOlusturma`: Yeni randevu oluşturma
- `RandevuDuzenleme`: Randevu düzenleme
- `RandevuSilme`: Randevu silme
- `KullaniciYonetimi`: Kullanıcı yönetimi
- `FirmaYonetimi`: Firma yönetimi
- `Admin`: Tam yetki

## Kullanım

### Randevu Oluşturma

1. "Yeni Randevu" butonuna tıklayın
2. Randevu bilgilerini doldurun
3. Müşteri bilgilerini girin
4. "Randevu Oluştur" butonuna tıklayın

### Randevu Yönetimi

- **Görüntüleme**: Yetkili kullanıcılar randevuları görüntüleyebilir
- **Düzenleme**: Sadece oluşturan kullanıcı ve admin düzenleyebilir
- **Durum Değiştirme**: Beklemede → Onaylandı → Tamamlandı

### Kullanıcı Yetkileri

- Her kullanıcı oluşturduğu randevuya tam yetki alır
- Admin kullanıcı tüm randevulara erişebilir
- Yetki sistemi ile kullanıcıların hangi randevuları görebileceği kontrol edilir

## Geliştirme

### Proje Yapısı

```
CRM/
├── app.py                 # Ana uygulama dosyası
├── models.py              # Veritabanı modelleri
├── config.py              # Konfigürasyon ayarları
├── requirements.txt       # Python paket gereksinimleri
├── database/
│   └── create_database.sql # Veritabanı oluşturma scripti
├── templates/             # HTML şablonları
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── randevular.html
│   ├── randevu_ekle.html
│   └── randevu_detay.html
└── README.md
```

### Yeni Özellik Ekleme

1. `models.py` dosyasında yeni model tanımlayın
2. `app.py` dosyasında yeni route'lar ekleyin
3. `templates/` klasöründe yeni şablonlar oluşturun
4. Gerekirse yeni yetki tipleri ekleyin

## Güvenlik

- Şifreler hash'lenerek saklanır
- Session tabanlı kimlik doğrulama
- Yetki kontrolü her işlemde yapılır
- SQL injection koruması (SQLAlchemy ORM)

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## Destek

Herhangi bir sorun yaşarsanız lütfen issue açın veya iletişime geçin.













