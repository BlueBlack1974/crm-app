from app.extensions import db
from datetime import datetime

# Firma Modeli
class Firma(db.Model):
    __tablename__ = 'Firmalar'
    
    FirmaID = db.Column(db.Integer, primary_key=True)
    FirmaAdi = db.Column(db.NVARCHAR(100), nullable=False)
    FirmaKodu = db.Column(db.NVARCHAR(20), unique=True, nullable=False)
    Adres = db.Column(db.NVARCHAR(200))
    Telefon = db.Column(db.NVARCHAR(20))
    Email = db.Column(db.NVARCHAR(100))
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    # AI Asistan alanları (merkezi API key - sunucuda, firma başına limit)
    AIAktif = db.Column(db.Boolean, default=False)           # AI özelliği bu firma için açık mı?
    AIAylikLimit = db.Column(db.Integer, default=50)         # Aylık maks istek (0 = sınırsız)
    AIKullanimAy = db.Column(db.String(7), default='')       # Sayacın ayı (YYYY-MM)
    AIKullanilanSayi = db.Column(db.Integer, default=0)      # Bu ay yapılan istek sayısı

    def __repr__(self):
        return f'<Firma {self.FirmaAdi}>'

class Kullanici(db.Model):
    __tablename__ = 'Kullanicilar'
    
    KullaniciID = db.Column(db.Integer, primary_key=True)
    KullaniciAdi = db.Column(db.NVARCHAR(50), unique=True, nullable=False)
    Sifre = db.Column(db.NVARCHAR(255), nullable=False)
    Ad = db.Column(db.NVARCHAR(50), nullable=False)
    Soyad = db.Column(db.NVARCHAR(50), nullable=False)
    Email = db.Column(db.NVARCHAR(100), unique=True, nullable=False)
    Telefon = db.Column(db.NVARCHAR(20))
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    Admin = db.Column(db.Boolean, default=False)
    Aktif = db.Column(db.Boolean, default=True)
    RaporlarModulu = db.Column(db.Boolean, default=True)  # Raporlar modülüne erişim
    AyarlarModulu = db.Column(db.Boolean, default=False)  # Ayarlar modülüne erişim
    LogModulu = db.Column(db.Boolean, default=False)      # Log modülüne erişim
    WhatsAppModulu = db.Column(db.Boolean, default=False) # WhatsApp modülüne erişim
    InstagramModulu = db.Column(db.Boolean, default=False) # Instagram modülüne erişim
    AIModulu = db.Column(db.Boolean, default=False)       # AI Asistan modülüne erişim
    ProfilFotografi = db.Column(db.NVARCHAR(500))  # Profil fotoğrafı dosya yolu
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    # İlişkiler
    firma = db.relationship('Firma', backref='kullanicilar')
    
    def __repr__(self):
        return f'<Kullanici {self.KullaniciAdi}>'


class AktifOturum(db.Model):
    __tablename__ = 'AktifOturumlar'
    
    # Primary key
    AktifOturumID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    SessionToken = db.Column(db.String(255), nullable=False, unique=True)
    
    # IP ve UserAgent
    ClientIP = db.Column(db.String(50), nullable=True)
    UserAgent = db.Column(db.Text, nullable=True)
    
    # Tarih kolonları
    GirisZamani = db.Column(db.DateTime, default=lambda: datetime.now(), nullable=False)
    SonGorulmeZamani = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now(), nullable=False)

    kullanici = db.relationship('Kullanici', backref='aktif_oturum', uselist=False)

    def __repr__(self):
        return f'<AktifOturum {self.KullaniciID}>'

class KullaniciLog(db.Model):
    __tablename__ = 'KullaniciLoglari'

    LogID = db.Column(db.Integer, primary_key=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    IslemTipi = db.Column(db.NVARCHAR(30), nullable=False)  # 'CREATE', 'UPDATE', 'DELETE', 'VIEW', 'CANCEL', 'LOGIN', 'LOGOUT'
    TabloAdi = db.Column(db.NVARCHAR(30), nullable=False)   # 'Randevu', 'Musteri', 'Rapor', 'Kullanici', 'Sistem'
    KayitID = db.Column(db.Integer)                         # İlgili kaydın ID'si (varsa)
    EskiVeri = db.Column(db.UnicodeText)                    # JSON format - değişiklik öncesi
    YeniVeri = db.Column(db.UnicodeText)                    # JSON format - değişiklik sonrası
    IslemDetayi = db.Column(db.NVARCHAR(500))               # İnsan okunabilir açıklama
    IPAdresi = db.Column(db.NVARCHAR(45))
    UserAgent = db.Column(db.NVARCHAR(500))
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), nullable=False)

    kullanici = db.relationship('Kullanici', backref='loglar')

    def __repr__(self):
        return f'<KullaniciLog {self.LogID} - {self.IslemTipi} - {self.TabloAdi}>'

class YetkiTipi(db.Model):
    __tablename__ = 'YetkiTipleri'
    
    YetkiID = db.Column(db.Integer, primary_key=True)
    YetkiAdi = db.Column(db.NVARCHAR(50), nullable=False)
    YetkiAciklamasi = db.Column(db.NVARCHAR(200))
    Aktif = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<YetkiTipi {self.YetkiAdi}>'

class KullaniciYetki(db.Model):
    __tablename__ = 'KullaniciYetkileri'
    
    KullaniciYetkiID = db.Column(db.Integer, primary_key=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    YetkiID = db.Column(db.Integer, db.ForeignKey('YetkiTipleri.YetkiID'), nullable=False)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # İlişkiler
    kullanici = db.relationship('Kullanici', backref='kullanici_yetkileri')
    yetki_tipi = db.relationship('YetkiTipi', backref='kullanici_yetkileri')
    
    __table_args__ = (db.UniqueConstraint('KullaniciID', 'YetkiID', name='uq_kullanici_yetki'),)
    
    def __repr__(self):
        return f'<KullaniciYetki {self.KullaniciID}-{self.YetkiID}>'

class Randevu(db.Model):
    __tablename__ = 'Randevular'
    
    RandevuID = db.Column(db.Integer, primary_key=True)
    RandevuBaslik = db.Column(db.NVARCHAR(100), nullable=False)
    RandevuAciklamasi = db.Column(db.NVARCHAR(500))
    RandevuTarihi = db.Column(db.DateTime, nullable=False)
    RandevuSuresi = db.Column(db.Integer, default=60)
    MusteriID = db.Column(db.Integer, db.ForeignKey('Musteriler.MusteriID'), nullable=True)
    MusteriAdi = db.Column(db.NVARCHAR(100))
    MusteriSoyadi = db.Column(db.NVARCHAR(100))
    MusteriTelefon = db.Column(db.NVARCHAR(20))
    MusteriEmail = db.Column(db.NVARCHAR(100))
    Durum = db.Column(db.NVARCHAR(20), default='Beklemede')
    IslemID = db.Column(db.Integer, db.ForeignKey('RandevuIslemler.IslemID'), nullable=True)
    OlusturanKullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    DefterID = db.Column(db.Integer, db.ForeignKey('RandevuDefterAyarlar.AyarID'), nullable=True)
    GorevID = db.Column(db.Integer, db.ForeignKey('Todos.TodoID'), nullable=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    # Yeni Eklenen Alanlar (Randevu Serisi)
    SeriID = db.Column(db.Integer, db.ForeignKey('RandevuSerileri.SeriID'), nullable=True)
    SeriNo = db.Column(db.Integer, nullable=True)
    
    # İlişkiler
    olusturan_kullanici = db.relationship('Kullanici', backref='olusturulan_randevular')
    firma = db.relationship('Firma', backref='randevular')
    musteri = db.relationship('Musteri', backref='randevular')
    islem = db.relationship('RandevuIslem', backref='randevular')
    defter = db.relationship('RandevuDefterAyar', backref='randevular')
    bildirimler = db.relationship('Bildirim', foreign_keys='Bildirim.IlgiliRandevuID', cascade='all, delete-orphan')
    hatirlatmalar = db.relationship('RandevuHatirlatma', cascade='all, delete-orphan')
    yetkiler = db.relationship('RandevuYetki', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Randevu {self.RandevuBaslik}>'

# Randevu Serileri Model
class RandevuSeri(db.Model):
    __tablename__ = 'RandevuSerileri'
    
    SeriID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    MusteriID = db.Column(db.Integer, db.ForeignKey('Musteriler.MusteriID'), nullable=False)
    DefterID = db.Column(db.Integer, db.ForeignKey('RandevuDefterAyarlar.AyarID'), nullable=False)
    IslemID = db.Column(db.Integer, db.ForeignKey('RandevuIslemler.IslemID'), nullable=True)
    Baslik = db.Column(db.NVARCHAR(200), nullable=False)
    ToplamRandevu = db.Column(db.Integer, nullable=False)
    TamamlananRandevu = db.Column(db.Integer, default=0)
    Durum = db.Column(db.NVARCHAR(20), default='Aktif')  # Aktif, Tamamlandi, Iptal
    Aciklama = db.Column(db.NVARCHAR(500))
    OlusturanKullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # İlişkiler
    firma = db.relationship('Firma', backref='randevu_serileri')
    musteri = db.relationship('Musteri', backref='randevu_serileri')
    defter = db.relationship('RandevuDefterAyar', backref='randevu_serileri')
    islem = db.relationship('RandevuIslem', backref='randevu_serileri')
    olusturan_kullanici = db.relationship('Kullanici', backref='olusturdugu_seriler')
    randevular = db.relationship('Randevu', backref='seri_grubu', lazy=True)
    
    def __repr__(self):
        return f'<RandevuSeri {self.SeriID} - {self.Baslik}>'

class RandevuYetki(db.Model):
    __tablename__ = 'RandevuYetkileri'
    
    RandevuYetkiID = db.Column(db.Integer, primary_key=True)
    RandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'), nullable=False)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    GoruntulemeYetkisi = db.Column(db.Boolean, default=True)
    DuzenlemeYetkisi = db.Column(db.Boolean, default=False)
    SilmeYetkisi = db.Column(db.Boolean, default=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # İlişkiler
    randevu = db.relationship('Randevu', overlaps="yetkiler")
    kullanici = db.relationship('Kullanici', backref='randevu_yetkileri')
    
    __table_args__ = (db.UniqueConstraint('RandevuID', 'KullaniciID', name='uq_randevu_kullanici'),)
    
    def __repr__(self):
        return f'<RandevuYetki {self.RandevuID}-{self.KullaniciID}>'

# Randevu Defteri Ayarlari Modeli
class RandevuDefterAyar(db.Model):
    __tablename__ = 'RandevuDefterAyarlar'

    AyarID = db.Column(db.Integer, primary_key=True)
    DefterAdi = db.Column(db.NVARCHAR(100), nullable=False, default='Varsayilan Defter')
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    CalismaGunleri = db.Column(db.NVARCHAR(50), default='1,2,3,4,5')  # 1=Mon ... 7=Sun
    BaslangicSaati = db.Column(db.NVARCHAR(5), default='09:00')
    BitisSaati = db.Column(db.NVARCHAR(5), default='18:00')
    SlotDakika = db.Column(db.Integer, default=30)
    Aktif = db.Column(db.Boolean, default=True)

    firma = db.relationship('Firma', backref='defter_ayarlar')

    def __repr__(self):
        return f'<RandevuDefterAyar {self.AyarID}-{self.DefterAdi}>'

# Randevu Defteri Bloklama: Belirli tarih/saat araliklarini kapatma
class RandevuDefterBlok(db.Model):
    __tablename__ = 'RandevuDefterBloklar'

    BlokID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    DefterID = db.Column(db.Integer, db.ForeignKey('RandevuDefterAyarlar.AyarID'), nullable=True)  # None: tüm defterler
    BaslangicTarih = db.Column(db.Date, nullable=False)
    BitisTarih = db.Column(db.Date, nullable=True)  # null ise tek gün
    SaatBaslangic = db.Column(db.NVARCHAR(5), nullable=True)  # 'HH:MM'
    SaatBitis = db.Column(db.NVARCHAR(5), nullable=True)
    Aciklama = db.Column(db.NVARCHAR(200), nullable=True)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())

    firma = db.relationship('Firma')
    defter = db.relationship('RandevuDefterAyar')

# Randevu Referanslari
class RandevuReferans(db.Model):
    __tablename__ = 'RandevuReferanslari'

    ReferansID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    Ad = db.Column(db.NVARCHAR(100), nullable=False)
    Aktif = db.Column(db.Boolean, default=True)

    firma = db.relationship('Firma', backref='randevu_referanslar')

    def __repr__(self):
        return f'<RandevuReferans {self.ReferansID}-{self.Ad}>'

# Randevu İşlemleri
class RandevuIslem(db.Model):
    __tablename__ = 'RandevuIslemler'
    
    IslemID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    DefterID = db.Column(db.Integer, db.ForeignKey('RandevuDefterAyarlar.AyarID'), nullable=True)
    IslemAdi = db.Column(db.NVARCHAR(100), nullable=False)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # İlişkiler
    firma = db.relationship('Firma', backref='randevu_islemleri')
    defter = db.relationship('RandevuDefterAyar', backref='randevu_islemleri')
    
    def __repr__(self):
        return f'<RandevuIslem {self.IslemID}: {self.IslemAdi}>'

# Bildirimler
class Bildirim(db.Model):
    __tablename__ = 'Bildirimler'

    BildirimID = db.Column(db.Integer, primary_key=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    Metin = db.Column(db.NVARCHAR(300), nullable=False)
    Okundu = db.Column(db.Boolean, default=False)
    Tip = db.Column(db.NVARCHAR(30), default='genel')
    IlgiliRandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'))
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())

    kullanici = db.relationship('Kullanici')
    firma = db.relationship('Firma')
    randevu = db.relationship('Randevu', foreign_keys=[IlgiliRandevuID], overlaps="bildirimler")

    def __repr__(self):
        return f'<Bildirim {self.BildirimID} kullanici={self.KullaniciID}>'

# Randevu Hatirlatma
class RandevuHatirlatma(db.Model):
    __tablename__ = 'RandevuHatirlatmalar'

    HatirlatmaID = db.Column(db.Integer, primary_key=True)
    RandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'), nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    RecipientEmail = db.Column(db.NVARCHAR(200))
    MinutesBefore = db.Column(db.Integer, default=60)
    Gonderildi = db.Column(db.Boolean, default=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GonderimTarihi = db.Column(db.DateTime)

    randevu = db.relationship('Randevu', overlaps="hatirlatmalar")

    def __repr__(self):
        return f'<RandevuHatirlatma {self.HatirlatmaID} randevu={self.RandevuID}>'

# Randevu SMS Hatirlatma
class RandevuSMSHatirlatma(db.Model):
    __tablename__ = 'RandevuSMSHatirlatmalar'

    HatirlatmaID = db.Column(db.Integer, primary_key=True)
    RandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'), nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    RecipientPhone = db.Column(db.NVARCHAR(20))
    MinutesBefore = db.Column(db.Integer, default=1440)
    Gonderildi = db.Column(db.Boolean, default=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GonderimTarihi = db.Column(db.DateTime)

    randevu = db.relationship('Randevu')

    def __repr__(self):
        return f'<RandevuSMSHatirlatma {self.HatirlatmaID} randevu={self.RandevuID}>'

# E-posta Ayarları
class FirmaEmailAyar(db.Model):
    __tablename__ = 'FirmaEmailAyarlari'
    
    EmailAyarID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    SMTP_Sunucu = db.Column(db.NVARCHAR(200), nullable=False)
    SMTP_Port = db.Column(db.Integer, nullable=False)
    KullaniciAdi = db.Column(db.NVARCHAR(200), nullable=False)
    Sifre = db.Column(db.NVARCHAR(200), nullable=False)
    SSL_Kullan = db.Column(db.Boolean, default=True)
    VarsayilanGonderenAdi = db.Column(db.NVARCHAR(200))
    VarsayilanGonderenEmail = db.Column(db.NVARCHAR(200))
    # Varsayılan e-posta içerik ayarları
    VarsayilanEmailKonu = db.Column(db.NVARCHAR(200))
    VarsayilanEmailMetni = db.Column(db.NVARCHAR(None)) # max
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='email_ayarlar')
    
    def __repr__(self):
        return f'<FirmaEmailAyar {self.EmailAyarID} firma={self.FirmaID}>'

# SMS Ayarları
class FirmaSMSAyar(db.Model):
    __tablename__ = 'FirmaSMSAyarlari'
    
    SMSAyarID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    SMSFirmasi = db.Column(db.NVARCHAR(50), nullable=False)  # 'netgsm', 'iletimerkezi', 'mesajnet', 'custom'
    API_Key = db.Column(db.NVARCHAR(500))
    API_Secret = db.Column(db.NVARCHAR(500))
    KullaniciAdi = db.Column(db.NVARCHAR(200))
    Sifre = db.Column(db.NVARCHAR(200))
    GondericiAdi = db.Column(db.NVARCHAR(20))
    API_URL = db.Column(db.NVARCHAR(500))
    # Varsayılan SMS metni
    VarsayilanSMSMetni = db.Column(db.NVARCHAR(1000))
    # Zamanlama seçenekleri
    SMSGonderOnCreate = db.Column(db.Boolean, default=False)
    SMSGonder24SaatOnce = db.Column(db.Boolean, default=False)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='sms_ayarlar')
    
    def __repr__(self):
        return f'<FirmaSMSAyar {self.SMSAyarID} firma={self.FirmaID}>'

# WhatsApp Ayarları
class FirmaWhatsAppAyar(db.Model):
    __tablename__ = 'FirmaWhatsAppAyarlari'
    
    WhatsAppAyarID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    AccessToken = db.Column(db.Text, nullable=True)
    PhoneNumberID = db.Column(db.String(50), nullable=True)
    BusinessAccountID = db.Column(db.String(50), nullable=True)
    WebhookVerifyToken = db.Column(db.String(100), nullable=True)
    TestNumarasi = db.Column(db.String(20), nullable=True)  # Test için kayıtlı numara
    # Varsayılan mesaj şablonları
    RandevuOlusturmaMesaji = db.Column(db.Text, nullable=True)
    RandevuHatirlatmaMesaji = db.Column(db.Text, nullable=True)
    RandevuIptalMesaji = db.Column(db.Text, nullable=True)
    # Zamanlama seçenekleri
    MesajGonderOnCreate = db.Column(db.Boolean, default=False)
    MesajGonder24SaatOnce = db.Column(db.Boolean, default=False)
    MesajGonder1SaatOnce = db.Column(db.Boolean, default=False)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='whatsapp_ayarlar')
    
    def __repr__(self):
        return f'<FirmaWhatsAppAyar {self.WhatsAppAyarID} firma={self.FirmaID}>'

# Instagram Ayarları
class FirmaInstagramAyar(db.Model):
    __tablename__ = 'FirmaInstagramAyarlari'
    
    InstagramAyarID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    FacebookPageID = db.Column(db.String(50), nullable=True)
    InstagramBusinessAccountID = db.Column(db.String(50), nullable=True)
    AccessToken = db.Column(db.Text, nullable=True)
    WebhookSecret = db.Column(db.String(100), nullable=True)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='instagram_ayarlar')
    
    def __repr__(self):
        return f'<FirmaInstagramAyar {self.InstagramAyarID} firma={self.FirmaID}>'

# Instagram Mesajları
class InstagramMesaj(db.Model):
    __tablename__ = 'InstagramMesajlar'

    MesajID = db.Column(db.Integer, primary_key=True)
    InstagramMessageID = db.Column(db.String(100), unique=True, nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    MusteriID = db.Column(db.Integer, db.ForeignKey('Musteriler.MusteriID'), nullable=True)
    GonderenID = db.Column(db.String(50), nullable=False)
    AliciID = db.Column(db.String(50), nullable=False)
    MesajMetni = db.Column(db.Text)
    Yyon = db.Column(db.String(10), nullable=False)  # 'GELEN' veya 'GIDEN'
    Okundu = db.Column(db.Boolean, default=False, nullable=False)  # Okunmamış mesajlar için
    Tarih = db.Column(db.DateTime, default=lambda: datetime.now())
    
    firma = db.relationship('Firma', backref='instagram_mesajlar')
    musteri = db.relationship('Musteri', backref='instagram_mesajlar')

    def __repr__(self):
        return f'<InstagramMesaj {self.MesajID}>'

# Sistem Ayarları (Veritabanı Konfigürasyonu)
class SistemAyar(db.Model):
    __tablename__ = 'SistemAyarlar'
    
    AyarID = db.Column(db.Integer, primary_key=True)
    AyarAdi = db.Column(db.String(100), unique=True, nullable=False)  # 'database_type', 'database_mssql_url', 'database_mysql_url'
    AyarDegeri = db.Column(db.Text, nullable=True)  # JSON veya string değer
    Aciklama = db.Column(db.NVARCHAR(500))
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    def __repr__(self):
        return f'<SistemAyar {self.AyarAdi}={self.AyarDegeri}>'

# Müşteri Kategorileri
class MusteriKategori(db.Model):
    __tablename__ = 'MusteriKategorileri'

    KategoriID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    KategoriAdi = db.Column(db.NVARCHAR(100), nullable=False)
    Renk = db.Column(db.NVARCHAR(20), default='#007bff')
    Aciklama = db.Column(db.NVARCHAR(500))
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())

    firma = db.relationship('Firma', backref='musteri_kategoriler')

    def __repr__(self):
        return f'<MusteriKategori {self.KategoriID} {self.KategoriAdi}>'

# Müşteriler
class Musteri(db.Model):
    __tablename__ = 'Musteriler'

    MusteriID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    MusteriAdi = db.Column(db.NVARCHAR(100), nullable=False)
    MusteriSoyadi = db.Column(db.NVARCHAR(100), nullable=False)
    Telefon = db.Column(db.NVARCHAR(20))
    Email = db.Column(db.NVARCHAR(200))
    # Adres bilgileri - 4 ayrı alan
    Ulke = db.Column(db.NVARCHAR(100), default='Türkiye')
    Sehir = db.Column(db.NVARCHAR(100))
    Ilce = db.Column(db.NVARCHAR(100))
    Adres = db.Column(db.NVARCHAR(500))
    DogumTarihi = db.Column(db.Date)
    Yas = db.Column(db.Integer)  # Yaş alanı
    Cinsiyet = db.Column(db.NVARCHAR(10))  # 'Erkek', 'Kadın'
    KategoriID = db.Column(db.Integer, db.ForeignKey('MusteriKategorileri.KategoriID'))
    Notlar = db.Column(db.NVARCHAR(1000))
    ProfilFotografi = db.Column(db.NVARCHAR(500))
    InstagramKullaniciAdi = db.Column(db.NVARCHAR(100))  # Instagram Kullanıcı Adı
    Aktif = db.Column(db.Boolean, default=True)
    OlusturanKullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'))
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now())

    firma = db.relationship('Firma', backref='musteriler')
    kategori = db.relationship('MusteriKategori', backref='musteriler')
    olusturan_kullanici = db.relationship('Kullanici', backref='olusturulan_musteriler', foreign_keys=[OlusturanKullaniciID])

    @property
    def tam_adi(self):
        return f"{self.MusteriAdi} {self.MusteriSoyadi}"

    def __repr__(self):
        return f'<Musteri {self.MusteriID} {self.tam_adi}>'

# Görev Durumları
class TodoDurum(db.Model):
    __tablename__ = 'TodoDurumlar'
    
    DurumID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    DurumAdi = db.Column(db.NVARCHAR(50), nullable=False)
    DurumAciklamasi = db.Column(db.NVARCHAR(200))
    Renk = db.Column(db.NVARCHAR(7), default='#007bff')  # Hex renk kodu
    Sira = db.Column(db.Integer, default=0)  # Sıralama için
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    
    # İlişkiler
    firma = db.relationship('Firma', backref='todo_durumlar', lazy=True)
    
    def __repr__(self):
        return f'<TodoDurum {self.DurumAdi}>'

class Todo(db.Model):
    __tablename__ = 'Todos'
    
    TodoID = db.Column(db.Integer, primary_key=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    Baslik = db.Column(db.NVARCHAR(200), nullable=False)
    Aciklama = db.Column(db.Text)
    Oncelik = db.Column(db.Enum('Düşük', 'Orta', 'Yüksek', name='oncelik_enum'), default='Orta')
    DurumID = db.Column(db.Integer, db.ForeignKey('TodoDurumlar.DurumID'), nullable=True)  # Yeni alan
    Tip = db.Column(db.Enum('Kisisel', 'Randevu', name='todo_tip_enum'), default='Kisisel')  # Yeni alan
    BitisTarihi = db.Column(db.DateTime)
    HatirlatmaTarihi = db.Column(db.DateTime)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now())
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    TamamlanmaTarihi = db.Column(db.DateTime)
    # Müşteri bilgileri
    MusteriAdi = db.Column(db.NVARCHAR(100))
    MusteriSoyadi = db.Column(db.NVARCHAR(100))
    MusteriTelefon = db.Column(db.NVARCHAR(20))
    MusteriEmail = db.Column(db.NVARCHAR(100))
    # Randevu alanları
    RandevuTarihi = db.Column(db.Date)
    RandevuSaati = db.Column(db.NVARCHAR(10))  # HH:MM formatında
    RandevuDefteriID = db.Column(db.Integer, db.ForeignKey('RandevuDefterAyarlar.AyarID'), nullable=True)
    RandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'), nullable=True)
    AtananKullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=True)
    
    # İlişkiler
    kullanici = db.relationship('Kullanici', foreign_keys=[KullaniciID], backref='todos', lazy=True)
    atanan_kullanici = db.relationship('Kullanici', foreign_keys=[AtananKullaniciID], backref='atanan_todos', lazy=True)
    durum = db.relationship('TodoDurum', backref='todos', lazy=True)
    
    def __repr__(self):
        return f'<Todo {self.Baslik}>'

# =====================================================
# Activity / İletişim Geçmişi Modeli
# =====================================================
# MySQL ve MSSQL ile uyumlu tasarım
class Aktivite(db.Model):
    __tablename__ = 'Aktiviteler'
    
    # Primary key (MySQL: AUTO_INCREMENT, MSSQL: IDENTITY(1,1))
    AktiviteID = db.Column(db.Integer, primary_key=True)
    
    # Müşteri ilişkisi (zorunlu)
    MusteriID = db.Column(db.Integer, db.ForeignKey('Musteriler.MusteriID'), nullable=False)
    
    # Firma ilişkisi (filtreleme için)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    
    # Aktivite tipi: 'call', 'email', 'note', 'appointment', 'task', 'meeting', 'proposal', 'other'
    # VARCHAR(50) / NVARCHAR(50) - her iki veritabanında da çalışır
    AktiviteTipi = db.Column(db.NVARCHAR(50), nullable=False)
    
    # Başlık ve açıklama
    Baslik = db.Column(db.NVARCHAR(200), nullable=False)
    # TEXT (MySQL) / NVARCHAR(MAX) (MSSQL) - SQLAlchemy Text tipi her ikisinde de çalışır
    Aciklama = db.Column(db.Text)
    
    # İlişkili nesne (opsiyonel - genişletilebilirlik için)
    # Örn: 'appointment', 'task', 'proposal', 'invoice' vb.
    IlgiliNesneTipi = db.Column(db.NVARCHAR(50), nullable=True)
    IlgiliNesneID = db.Column(db.Integer, nullable=True)
    
    # Aktivite tarihi/saati (kronolojik sıralama için)
    # DATETIME (MySQL) / DATETIME2 (MSSQL) - SQLAlchemy DateTime tipi her ikisinde de çalışır
    AktiviteTarihi = db.Column(db.DateTime, nullable=False)
    
    # Ek bilgiler (JSON formatında saklanabilir)
    # MySQL: JSON tipi, MSSQL: NVARCHAR(MAX) (JSON string olarak)
    # SQLAlchemy'de JSON tipi kullanılabilir (MySQL 5.7+, MSSQL 2016+)
    # Geriye dönük uyumluluk için Text kullanıyoruz
    EkBilgiler = db.Column(db.Text)  # JSON string olarak saklanır
    
    # Oluşturan kullanıcı
    OlusturanKullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=True)
    
    # Tarih alanları
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), nullable=False)
    GuncellemeTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now(), nullable=False)
    
    # İlişkiler
    musteri = db.relationship('Musteri', backref='aktiviteler', lazy=True)
    firma = db.relationship('Firma', backref='aktiviteler', lazy=True)
    olusturan_kullanici = db.relationship('Kullanici', foreign_keys=[OlusturanKullaniciID], backref='olusturdugu_aktiviteler', lazy=True)
    
    def __repr__(self):
        return f'<Aktivite {self.AktiviteTipi} - {self.Baslik}>'
    
    def to_dict(self):
        """Aktiviteyi dictionary formatına çevir (API için)"""
        return {
            'id': self.AktiviteID,
            'musteri_id': self.MusteriID,
            'firma_id': self.FirmaID,
            'aktivite_tipi': self.AktiviteTipi,
            'baslik': self.Baslik,
            'aciklama': self.Aciklama,
            'ilgili_nesne_tipi': self.IlgiliNesneTipi,
            'ilgili_nesne_id': self.IlgiliNesneID,
            'aktivite_tarihi': self.AktiviteTarihi.isoformat() if self.AktiviteTarihi else None,
            'ek_bilgiler': self.EkBilgiler,  # JSON string
            'olusturan_kullanici_id': self.OlusturanKullaniciID,
            'olusturan_kullanici_adi': f"{self.olusturan_kullanici.Ad} {self.olusturan_kullanici.Soyad}" if self.olusturan_kullanici else None,
            'olusturma_tarihi': self.OlusturmaTarihi.isoformat() if self.OlusturmaTarihi else None,
            'guncelleme_tarihi': self.GuncellemeTarihi.isoformat() if self.GuncellemeTarihi else None
        }


class KullaniciMesaj(db.Model):
    __tablename__ = 'KullaniciMesajlari'
    
    MesajID = db.Column(db.Integer, primary_key=True)
    GonderenID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    AliciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    Mesaj = db.Column(db.UnicodeText, nullable=False)
    Okundu = db.Column(db.Boolean, default=False)
    GonderenSilindi = db.Column(db.Boolean, default=False)
    AliciSilindi = db.Column(db.Boolean, default=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=lambda: datetime.now(), nullable=False)
    OkunmaTarihi = db.Column(db.DateTime, nullable=True)
    
    # İlişkiler
    gonderen = db.relationship('Kullanici', foreign_keys=[GonderenID], backref='gonderilen_mesajlar')
    alici = db.relationship('Kullanici', foreign_keys=[AliciID], backref='alinan_mesajlar')
    
    def __repr__(self):
        return f'<KullaniciMesaj {self.MesajID} - {self.GonderenID} -> {self.AliciID}>'
    
    def to_dict(self):
        return {
            'mesaj_id': self.MesajID,
            'gonderen_id': self.GonderenID,
            'alici_id': self.AliciID,
            'mesaj': self.Mesaj,
            'okundu': self.Okundu,
            'gonderen_silindi': self.GonderenSilindi,
            'alici_silindi': self.AliciSilindi,
            'olusturma_tarihi': self.OlusturmaTarihi.isoformat() if self.OlusturmaTarihi else None,
            'okunma_tarihi': self.OkunmaTarihi.isoformat() if self.OkunmaTarihi else None,
            'gonderen_adi': f"{self.gonderen.Ad} {self.gonderen.Soyad}" if self.gonderen else None,
            'alici_adi': f"{self.alici.Ad} {self.alici.Soyad}" if self.alici else None
        }

class SifreSifirlamaToken(db.Model):
    __tablename__ = 'SifreSifirlamaTokenlari'
    
    TokenID = db.Column(db.Integer, primary_key=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    Token = db.Column(db.NVARCHAR(100), unique=True, nullable=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    GecerlilikSuresi = db.Column(db.DateTime, nullable=False)
    Kullanildi = db.Column(db.Boolean, default=False)
    
    kullanici = db.relationship('Kullanici', backref='sifirlama_tokenlari', lazy=True)
    
    def __repr__(self):
        return f'<SifreSifirlamaToken {self.KullaniciID}>'