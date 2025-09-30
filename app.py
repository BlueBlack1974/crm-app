"""
CRM Uygulamasi - Ana Dosya
Randevu Defteri ve Kullanici Yonetimi
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel, gettext, ngettext, get_locale
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from functools import wraps
import smtplib
import ssl
from email.mime.text import MIMEText
import threading
from collections import Counter, defaultdict
from io import BytesIO
import csv

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-in-.env')
# Allow override via env; fallback to provided local credentials
_db_uri = os.environ.get('DATABASE_URL')
if not _db_uri:
    raise RuntimeError('DATABASE_URL is not set in environment (.env). Please define the SQLAlchemy URI.')
app.config['SQLALCHEMY_DATABASE_URI'] = _db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SMTP/E-posta ayarlari (env ile override edilebilir)
app.config['SMTP_HOST'] = os.environ.get('SMTP_HOST', '')
app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT', '587'))
app.config['SMTP_USER'] = os.environ.get('SMTP_USER', '')
app.config['SMTP_PASS'] = os.environ.get('SMTP_PASS', '')
app.config['SMTP_USE_TLS'] = os.environ.get('SMTP_USE_TLS', '1') == '1'
app.config['FROM_EMAIL'] = os.environ.get('FROM_EMAIL', app.config['SMTP_USER'])

# Initialize SQLAlchemy with app
db = SQLAlchemy(app)

# Babel konfigürasyonu
app.config['LANGUAGES'] = {
    'tr': 'Türkçe',
    'en': 'English'
}
app.config['BABEL_DEFAULT_LOCALE'] = 'tr'
app.config['BABEL_DEFAULT_TIMEZONE'] = 'Europe/Istanbul'

def get_locale():
    # Önce session'dan dil tercihini kontrol et
    if 'language' in session:
        return session['language']
    # Sonra request header'ından
    return app.config['BABEL_DEFAULT_LOCALE']

# Babel'i yeniden başlat
babel = Babel(app, locale_selector=get_locale)

# Login gerekli decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin gerekli decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin', False) and not session.get('ayarlar_modulu', False):
            flash('Bu sayfaya erişim yetkiniz yok!', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Sadece admin gerekli decorator (ayarlar modülü yetkisi yeterli değil)
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin', False):
            flash('Bu sayfaya erişim yetkiniz yok!', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Database Models
class Firma(db.Model):
    __tablename__ = 'Firmalar'
    
    FirmaID = db.Column(db.Integer, primary_key=True)
    FirmaAdi = db.Column(db.NVARCHAR(100), nullable=False)
    FirmaKodu = db.Column(db.NVARCHAR(20), unique=True, nullable=False)
    Adres = db.Column(db.NVARCHAR(200))
    Telefon = db.Column(db.NVARCHAR(20))
    Email = db.Column(db.NVARCHAR(100))
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    GuncellemeTarihi = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    GuncellemeTarihi = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    firma = db.relationship('Firma', backref='kullanicilar')
    
    def __repr__(self):
        return f'<Kullanici {self.KullaniciAdi}>'

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
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    MusteriTelefon = db.Column(db.NVARCHAR(20))
    MusteriEmail = db.Column(db.NVARCHAR(100))
    Durum = db.Column(db.NVARCHAR(20), default='Beklemede')
    IslemID = db.Column(db.Integer, db.ForeignKey('RandevuIslemler.IslemID'), nullable=True)
    OlusturanKullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    DefterID = db.Column(db.Integer, db.ForeignKey('RandevuDefterAyarlar.AyarID'), nullable=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    GuncellemeTarihi = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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

class RandevuYetki(db.Model):
    __tablename__ = 'RandevuYetkileri'
    
    RandevuYetkiID = db.Column(db.Integer, primary_key=True)
    RandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'), nullable=False)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False)
    GoruntulemeYetkisi = db.Column(db.Boolean, default=True)
    DuzenlemeYetkisi = db.Column(db.Boolean, default=False)
    SilmeYetkisi = db.Column(db.Boolean, default=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)

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
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)

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
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    GonderimTarihi = db.Column(db.DateTime)

    randevu = db.relationship('Randevu', overlaps="hatirlatmalar")

    def __repr__(self):
        return f'<RandevuHatirlatma {self.HatirlatmaID} randevu={self.RandevuID}>'

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
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
    firma = db.relationship('Firma', backref='sms_ayarlar')
    
    def __repr__(self):
        return f'<FirmaSMSAyar {self.SMSAyarID} firma={self.FirmaID}>'

# Müşteri Kategorileri
class MusteriKategori(db.Model):
    __tablename__ = 'MusteriKategorileri'

    KategoriID = db.Column(db.Integer, primary_key=True)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    KategoriAdi = db.Column(db.NVARCHAR(100), nullable=False)
    Renk = db.Column(db.NVARCHAR(20), default='#007bff')
    Aciklama = db.Column(db.NVARCHAR(500))
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)

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
    Cinsiyet = db.Column(db.NVARCHAR(10))  # 'Erkek', 'Kadın'
    KategoriID = db.Column(db.Integer, db.ForeignKey('MusteriKategorileri.KategoriID'))
    Notlar = db.Column(db.NVARCHAR(1000))
    ProfilFotografi = db.Column(db.NVARCHAR(500))
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    GuncellemeTarihi = db.Column(db.DateTime, default=datetime.utcnow)

    firma = db.relationship('Firma', backref='musteriler')
    kategori = db.relationship('MusteriKategori', backref='musteriler')

    @property
    def tam_adi(self):
        return f"{self.MusteriAdi} {self.MusteriSoyadi}"

    def __repr__(self):
        return f'<Musteri {self.MusteriID} {self.tam_adi}>'

# E-posta gonderim yardimcisi
def send_email_simple(to_email: str, subject: str, body: str) -> bool:
    host = app.config['SMTP_HOST']
    user = app.config['SMTP_USER']
    password = app.config['SMTP_PASS']
    port = app.config['SMTP_PORT']
    use_tls = app.config['SMTP_USE_TLS']
    from_email = app.config['FROM_EMAIL'] or user

    if not host or not user or not password or not to_email:
        return False

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    try:
        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port) as server:
                server.starttls(context=context)
                server.login(user, password)
                server.sendmail(from_email, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                server.login(user, password)
                server.sendmail(from_email, [to_email], msg.as_string())
        return True
    except Exception as e:
        # Sadece debug modunda hata mesajı yazdır
        if app.debug:
            print(f"E-posta gönderilemedi: {e}")
        return False

def send_email_with_firma_settings(firma_id: int, to_email: str, subject: str, body: str, from_name: str = None) -> bool:
    """Firma ayarlarını kullanarak e-posta gönder"""
    try:
        # Firma e-posta ayarlarını al
        email_ayar = FirmaEmailAyar.query.filter_by(FirmaID=firma_id, Aktif=True).first()
        
        if not email_ayar:
            # Sadece debug modunda hata mesajı yazdır
            if app.debug:
                print(f"Firma {firma_id} için aktif e-posta ayarı bulunamadı")
            return False
        
        # Gönderen bilgilerini ayarla
        from_email = email_ayar.VarsayilanGonderenEmail or email_ayar.KullaniciAdi
        from_name = from_name or email_ayar.VarsayilanGonderenAdi or "CRM Sistemi"
        
        # E-posta mesajını oluştur
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{from_email}>"
        msg['To'] = to_email
        
        # SMTP bağlantısı ve gönderim
        if email_ayar.SSL_Kullan:
            context = ssl.create_default_context()
            with smtplib.SMTP(email_ayar.SMTP_Sunucu, email_ayar.SMTP_Port) as server:
                server.starttls(context=context)
                server.login(email_ayar.KullaniciAdi, email_ayar.Sifre)
                server.sendmail(from_email, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(email_ayar.SMTP_Sunucu, email_ayar.SMTP_Port) as server:
                server.login(email_ayar.KullaniciAdi, email_ayar.Sifre)
                server.sendmail(from_email, [to_email], msg.as_string())
        
        # Sadece debug modunda başarı mesajı yazdır
        if app.debug:
            print(f"E-posta başarıyla gönderildi: {to_email}")
        return True
        
    except Exception as e:
        # Sadece debug modunda hata mesajı yazdır
        if app.debug:
            print(f"E-posta gönderilemedi (firma ayarları): {e}")
        return False

def send_sms_with_firma_settings(firma_id: int, phone_number: str, message: str) -> bool:
    """Firma ayarlarını kullanarak SMS gönder"""
    try:
        # Firma SMS ayarlarını al
        sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=firma_id, Aktif=True).first()
        
        if not sms_ayar:
            print(f"Firma {firma_id} için aktif SMS ayarı bulunamadı")
            return False
        
        # Telefon numarasını temizle (sadece rakamlar)
        phone_number = ''.join(filter(str.isdigit, phone_number))
        if not phone_number.startswith('90'):
            phone_number = '90' + phone_number
        
        # SMS firmasına göre gönderim
        if sms_ayar.SMSFirmasi == 'netgsm':
            return send_sms_netgsm(sms_ayar, phone_number, message)
        elif sms_ayar.SMSFirmasi == 'iletimerkezi':
            return send_sms_iletimerkezi(sms_ayar, phone_number, message)
        elif sms_ayar.SMSFirmasi == 'mesajnet':
            return send_sms_mesajnet(sms_ayar, phone_number, message)
        elif sms_ayar.SMSFirmasi == 'custom':
            return send_sms_custom(sms_ayar, phone_number, message)
        else:
            print(f"Desteklenmeyen SMS firması: {sms_ayar.SMSFirmasi}")
            return False
            
    except Exception as e:
        print(f"SMS gönderilemedi (firma ayarları): {e}")
        return False

def send_sms_netgsm(sms_ayar, phone_number: str, message: str) -> bool:
    """NetGSM API ile SMS gönder"""
    try:
        import requests
        
        url = "https://api.netgsm.com.tr/sms/send/get"
        params = {
            'usercode': sms_ayar.KullaniciAdi,
            'password': sms_ayar.Sifre,
            'gsmno': phone_number,
            'message': message,
            'msgheader': sms_ayar.GondericiAdi or 'CRM'
        }
        
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            result = response.text.strip()
            if result.startswith('00'):
                print(f"NetGSM SMS başarıyla gönderildi: {phone_number}")
                return True
            else:
                print(f"NetGSM SMS hatası: {result}")
                return False
        else:
            print(f"NetGSM API hatası: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"NetGSM SMS gönderim hatası: {e}")
        return False

def send_sms_iletimerkezi(sms_ayar, phone_number: str, message: str) -> bool:
    """İleti Merkezi API ile SMS gönder"""
    try:
        import requests
        
        url = "https://api.iletimerkezi.com/v1/send-sms"
        headers = {
            'Authorization': f'Bearer {sms_ayar.API_Key}',
            'Content-Type': 'application/json'
        }
        data = {
            'recipients': [phone_number],
            'message': message,
            'sender': sms_ayar.GondericiAdi or 'CRM'
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print(f"İleti Merkezi SMS başarıyla gönderildi: {phone_number}")
                return True
            else:
                print(f"İleti Merkezi SMS hatası: {result}")
                return False
        else:
            print(f"İleti Merkezi API hatası: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"İleti Merkezi SMS gönderim hatası: {e}")
        return False

def send_sms_mesajnet(sms_ayar, phone_number: str, message: str) -> bool:
    """MesajNet API ile SMS gönder"""
    try:
        import requests
        
        url = "https://api.mesajnet.com/sms/send"
        data = {
            'username': sms_ayar.KullaniciAdi,
            'password': sms_ayar.Sifre,
            'number': phone_number,
            'message': message,
            'sender': sms_ayar.GondericiAdi or 'CRM'
        }
        
        response = requests.post(url, data=data, timeout=30)
        if response.status_code == 200:
            result = response.text.strip()
            if 'success' in result.lower() or 'ok' in result.lower():
                print(f"MesajNet SMS başarıyla gönderildi: {phone_number}")
                return True
            else:
                print(f"MesajNet SMS hatası: {result}")
                return False
        else:
            print(f"MesajNet API hatası: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"MesajNet SMS gönderim hatası: {e}")
        return False

def send_sms_custom(sms_ayar, phone_number: str, message: str) -> bool:
    """Özel API ile SMS gönder"""
    try:
        import requests
        
        if not sms_ayar.API_URL:
            print("Özel API URL tanımlanmamış")
            return False
        
        # Özel API için genel POST isteği
        data = {
            'phone': phone_number,
            'message': message,
            'sender': sms_ayar.GondericiAdi or 'CRM'
        }
        
        # API Key varsa ekle
        if sms_ayar.API_Key:
            data['api_key'] = sms_ayar.API_Key
        if sms_ayar.API_Secret:
            data['api_secret'] = sms_ayar.API_Secret
        
        response = requests.post(sms_ayar.API_URL, json=data, timeout=30)
        if response.status_code == 200:
            print(f"Özel API SMS başarıyla gönderildi: {phone_number}")
            return True
        else:
            print(f"Özel API SMS hatası: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Özel API SMS gönderim hatası: {e}")
        return False

# Country State City API entegrasyonu
import requests
import json

# API Base URL
CSC_API_BASE = "https://api.countrystatecity.in/v1"

# API Key (ücretsiz tier için)
CSC_API_KEY = os.environ.get("CSC_API_KEY", "")  # https://countrystatecity.in/ adresinden alın

def _csc_headers():
    """CountryStateCity API için header üretir ve anahtardaki boşluk/çevresel boşlukları temizler."""
    key = (CSC_API_KEY or "").strip().replace(" ", "")
    return {"X-CSCAPI-KEY": key}

def get_countries():
    """Tüm ülkeleri getir"""
    try:
        headers = _csc_headers()
        url = f"{CSC_API_BASE}/countries"
        response = requests.get(url, headers=headers, timeout=10)
        if app.debug:
            print(f"CSC GET {url} -> {response.status_code}")
        if response.status_code == 200:
            countries = response.json()
            return [{"iso2": country["iso2"], "name": country["name"]} for country in countries]
        else:
            # Fallback: Statik liste
            if app.debug:
                try:
                    print(f"CSC countries non-200: {response.status_code} body={response.text[:200]}")
                except Exception:
                    pass
            return get_fallback_countries()
    except Exception as e:
        if app.debug:
            print(f"API hatası (ülkeler): {e}")
        return get_fallback_countries()

def get_states(country_iso2):
    """Belirli bir ülkenin eyaletlerini/şehirlerini getir"""
    try:
        headers = _csc_headers()
        url = f"{CSC_API_BASE}/countries/{country_iso2}/states"
        response = requests.get(url, headers=headers, timeout=10)
        if app.debug:
            print(f"CSC GET {url} -> {response.status_code}")
        if response.status_code == 200:
            states = response.json()
            return [{"iso2": state["iso2"], "name": state["name"]} for state in states]
        else:
            # Fallback: Statik veriler
            if app.debug:
                try:
                    print(f"CSC states non-200: {response.status_code} body={response.text[:200]}")
                except Exception:
                    pass
            return get_fallback_states(country_iso2)
    except Exception as e:
        if app.debug:
            print(f"API hatası (eyaletler): {e}")
        # Fallback: Statik veriler
        return get_fallback_states(country_iso2)

def get_cities(country_iso2, state_iso2=None):
    """Belirli bir ülke/eyaletin şehirlerini getir"""
    try:
        headers = _csc_headers()
        if state_iso2:
            url = f"{CSC_API_BASE}/countries/{country_iso2}/states/{state_iso2}/cities"
        else:
            url = f"{CSC_API_BASE}/countries/{country_iso2}/cities"
        
        response = requests.get(url, headers=headers, timeout=10)
        if app.debug:
            print(f"CSC GET {url} -> {response.status_code}")
        if response.status_code == 200:
            cities = response.json()
            return [{"name": city["name"]} for city in cities]
        else:
            # Fallback: Statik veriler
            if app.debug:
                try:
                    print(f"CSC cities non-200: {response.status_code} body={response.text[:200]}")
                except Exception:
                    pass
            return get_fallback_cities(country_iso2, state_iso2)
    except Exception as e:
        if app.debug:
            print(f"API hatası (şehirler): {e}")
        # Fallback: Statik veriler
        return get_fallback_cities(country_iso2, state_iso2)

def get_fallback_countries():
    """API çalışmazsa kullanılacak statik ülke listesi"""
    return [
        {"iso2": "TR", "name": "Turkey"},
        {"iso2": "US", "name": "United States"},
        {"iso2": "DE", "name": "Germany"},
        {"iso2": "FR", "name": "France"},
        {"iso2": "GB", "name": "United Kingdom"},
        {"iso2": "IT", "name": "Italy"},
        {"iso2": "ES", "name": "Spain"},
        {"iso2": "NL", "name": "Netherlands"},
        {"iso2": "BE", "name": "Belgium"},
        {"iso2": "AT", "name": "Austria"},
        {"iso2": "CH", "name": "Switzerland"},
        {"iso2": "CA", "name": "Canada"},
        {"iso2": "AU", "name": "Australia"},
        {"iso2": "JP", "name": "Japan"},
        {"iso2": "CN", "name": "China"},
        {"iso2": "KR", "name": "South Korea"},
        {"iso2": "RU", "name": "Russia"},
        {"iso2": "UA", "name": "Ukraine"},
        {"iso2": "PL", "name": "Poland"},
        {"iso2": "CZ", "name": "Czech Republic"},
        {"iso2": "HU", "name": "Hungary"},
        {"iso2": "RO", "name": "Romania"},
        {"iso2": "BG", "name": "Bulgaria"},
        {"iso2": "GR", "name": "Greece"},
        {"iso2": "PT", "name": "Portugal"},
        {"iso2": "SE", "name": "Sweden"},
        {"iso2": "NO", "name": "Norway"},
        {"iso2": "DK", "name": "Denmark"},
        {"iso2": "FI", "name": "Finland"},
        {"iso2": "IS", "name": "Iceland"},
        {"iso2": "IE", "name": "Ireland"},
        {"iso2": "NZ", "name": "New Zealand"},
        {"iso2": "BR", "name": "Brazil"},
        {"iso2": "AR", "name": "Argentina"},
        {"iso2": "MX", "name": "Mexico"},
        {"iso2": "ZA", "name": "South Africa"},
        {"iso2": "EG", "name": "Egypt"},
        {"iso2": "SA", "name": "Saudi Arabia"},
        {"iso2": "AE", "name": "United Arab Emirates"},
        {"iso2": "IL", "name": "Israel"},
        {"iso2": "IN", "name": "India"},
        {"iso2": "PK", "name": "Pakistan"},
        {"iso2": "BD", "name": "Bangladesh"},
        {"iso2": "TH", "name": "Thailand"},
        {"iso2": "VN", "name": "Vietnam"},
        {"iso2": "ID", "name": "Indonesia"},
        {"iso2": "MY", "name": "Malaysia"},
        {"iso2": "SG", "name": "Singapore"},
        {"iso2": "PH", "name": "Philippines"}
    ]

def get_fallback_states(country_iso2):
    """API çalışmazsa kullanılacak statik eyalet/şehir listesi"""
    if country_iso2 == "TR":
        # Türkiye illeri
        return [
            {"iso2": "01", "name": "Adana"}, {"iso2": "02", "name": "Adıyaman"}, {"iso2": "03", "name": "Afyonkarahisar"},
            {"iso2": "04", "name": "Ağrı"}, {"iso2": "05", "name": "Amasya"}, {"iso2": "06", "name": "Ankara"},
            {"iso2": "07", "name": "Antalya"}, {"iso2": "08", "name": "Artvin"}, {"iso2": "09", "name": "Aydın"},
            {"iso2": "10", "name": "Balıkesir"}, {"iso2": "11", "name": "Bilecik"}, {"iso2": "12", "name": "Bingöl"},
            {"iso2": "13", "name": "Bitlis"}, {"iso2": "14", "name": "Bolu"}, {"iso2": "15", "name": "Burdur"},
            {"iso2": "16", "name": "Bursa"}, {"iso2": "17", "name": "Çanakkale"}, {"iso2": "18", "name": "Çankırı"},
            {"iso2": "19", "name": "Çorum"}, {"iso2": "20", "name": "Denizli"}, {"iso2": "21", "name": "Diyarbakır"},
            {"iso2": "22", "name": "Edirne"}, {"iso2": "23", "name": "Elazığ"}, {"iso2": "24", "name": "Erzincan"},
            {"iso2": "25", "name": "Erzurum"}, {"iso2": "26", "name": "Eskişehir"}, {"iso2": "27", "name": "Gaziantep"},
            {"iso2": "28", "name": "Giresun"}, {"iso2": "29", "name": "Gümüşhane"}, {"iso2": "30", "name": "Hakkâri"},
            {"iso2": "31", "name": "Hatay"}, {"iso2": "32", "name": "Isparta"}, {"iso2": "33", "name": "Mersin"},
            {"iso2": "34", "name": "İstanbul"}, {"iso2": "35", "name": "İzmir"}, {"iso2": "36", "name": "Kars"},
            {"iso2": "37", "name": "Kastamonu"}, {"iso2": "38", "name": "Kayseri"}, {"iso2": "39", "name": "Kırklareli"},
            {"iso2": "40", "name": "Kırşehir"}, {"iso2": "41", "name": "Kocaeli"}, {"iso2": "42", "name": "Konya"},
            {"iso2": "43", "name": "Kütahya"}, {"iso2": "44", "name": "Malatya"}, {"iso2": "45", "name": "Manisa"},
            {"iso2": "46", "name": "Kahramanmaraş"}, {"iso2": "47", "name": "Mardin"}, {"iso2": "48", "name": "Muğla"},
            {"iso2": "49", "name": "Muş"}, {"iso2": "50", "name": "Nevşehir"}, {"iso2": "51", "name": "Niğde"},
            {"iso2": "52", "name": "Ordu"}, {"iso2": "53", "name": "Rize"}, {"iso2": "54", "name": "Sakarya"},
            {"iso2": "55", "name": "Samsun"}, {"iso2": "56", "name": "Siirt"}, {"iso2": "57", "name": "Sinop"},
            {"iso2": "58", "name": "Sivas"}, {"iso2": "59", "name": "Tekirdağ"}, {"iso2": "60", "name": "Tokat"},
            {"iso2": "61", "name": "Trabzon"}, {"iso2": "62", "name": "Tunceli"}, {"iso2": "63", "name": "Şanlıurfa"},
            {"iso2": "64", "name": "Uşak"}, {"iso2": "65", "name": "Van"}, {"iso2": "66", "name": "Yozgat"},
            {"iso2": "67", "name": "Zonguldak"}, {"iso2": "68", "name": "Aksaray"}, {"iso2": "69", "name": "Bayburt"},
            {"iso2": "70", "name": "Karaman"}, {"iso2": "71", "name": "Kırıkkale"}, {"iso2": "72", "name": "Batman"},
            {"iso2": "73", "name": "Şırnak"}, {"iso2": "74", "name": "Bartın"}, {"iso2": "75", "name": "Ardahan"},
            {"iso2": "76", "name": "Iğdır"}, {"iso2": "77", "name": "Yalova"}, {"iso2": "78", "name": "Karabük"},
            {"iso2": "79", "name": "Kilis"}, {"iso2": "80", "name": "Osmaniye"}, {"iso2": "81", "name": "Düzce"}
        ]
    elif country_iso2 == "US":
        # Amerika eyaletleri (önemli olanlar)
        return [
            {"iso2": "CA", "name": "California"}, {"iso2": "NY", "name": "New York"}, {"iso2": "TX", "name": "Texas"},
            {"iso2": "FL", "name": "Florida"}, {"iso2": "IL", "name": "Illinois"}, {"iso2": "PA", "name": "Pennsylvania"},
            {"iso2": "OH", "name": "Ohio"}, {"iso2": "GA", "name": "Georgia"}, {"iso2": "NC", "name": "North Carolina"},
            {"iso2": "MI", "name": "Michigan"}, {"iso2": "NJ", "name": "New Jersey"}, {"iso2": "VA", "name": "Virginia"},
            {"iso2": "WA", "name": "Washington"}, {"iso2": "AZ", "name": "Arizona"}, {"iso2": "MA", "name": "Massachusetts"},
            {"iso2": "TN", "name": "Tennessee"}, {"iso2": "IN", "name": "Indiana"}, {"iso2": "MO", "name": "Missouri"},
            {"iso2": "MD", "name": "Maryland"}, {"iso2": "WI", "name": "Wisconsin"}
        ]
    elif country_iso2 == "DE":
        # Almanya eyaletleri
        return [
            {"iso2": "BW", "name": "Baden-Württemberg"}, {"iso2": "BY", "name": "Bayern"}, {"iso2": "BE", "name": "Berlin"},
            {"iso2": "BB", "name": "Brandenburg"}, {"iso2": "HB", "name": "Bremen"}, {"iso2": "HH", "name": "Hamburg"},
            {"iso2": "HE", "name": "Hessen"}, {"iso2": "MV", "name": "Mecklenburg-Vorpommern"}, {"iso2": "NI", "name": "Niedersachsen"},
            {"iso2": "NW", "name": "Nordrhein-Westfalen"}, {"iso2": "RP", "name": "Rheinland-Pfalz"}, {"iso2": "SL", "name": "Saarland"},
            {"iso2": "SN", "name": "Sachsen"}, {"iso2": "ST", "name": "Sachsen-Anhalt"}, {"iso2": "SH", "name": "Schleswig-Holstein"},
            {"iso2": "TH", "name": "Thüringen"}
        ]
    else:
        return []

def get_fallback_cities(country_iso2, state_iso2=None):
    """API çalışmazsa kullanılacak statik şehir listesi"""
    if country_iso2 == "TR" and state_iso2:
        # Türkiye ilçeleri (sadece büyük şehirler için)
        city_data = {
            "01": [  # Adana
                {"name": "Seyhan"}, {"name": "Çukurova"}, {"name": "Yüreğir"}, {"name": "Sarıçam"},
                {"name": "Ceyhan"}, {"name": "Kozan"}, {"name": "İmamoğlu"}, {"name": "Karaisalı"},
                {"name": "Karataş"}, {"name": "Pozantı"}, {"name": "Saimbeyli"}, {"name": "Tufanbeyli"},
                {"name": "Yumurtalık"}, {"name": "Aladağ"}, {"name": "Feke"}
            ],
            "34": [  # İstanbul
                {"name": "Adalar"}, {"name": "Arnavutköy"}, {"name": "Ataşehir"}, {"name": "Avcılar"},
                {"name": "Bağcılar"}, {"name": "Bahçelievler"}, {"name": "Bakırköy"}, {"name": "Başakşehir"},
                {"name": "Bayrampaşa"}, {"name": "Beşiktaş"}, {"name": "Beykoz"}, {"name": "Beylikdüzü"},
                {"name": "Beyoğlu"}, {"name": "Büyükçekmece"}, {"name": "Çatalca"}, {"name": "Çekmeköy"},
                {"name": "Esenler"}, {"name": "Esenyurt"}, {"name": "Eyüpsultan"}, {"name": "Fatih"},
                {"name": "Gaziosmanpaşa"}, {"name": "Güngören"}, {"name": "Kadıköy"}, {"name": "Kağıthane"},
                {"name": "Kartal"}, {"name": "Küçükçekmece"}, {"name": "Maltepe"}, {"name": "Pendik"},
                {"name": "Sancaktepe"}, {"name": "Sarıyer"}, {"name": "Silivri"}, {"name": "Sultanbeyli"},
                {"name": "Sultangazi"}, {"name": "Şile"}, {"name": "Şişli"}, {"name": "Tuzla"},
                {"name": "Ümraniye"}, {"name": "Üsküdar"}, {"name": "Zeytinburnu"}
            ],
            "06": [  # Ankara
                {"name": "Akyurt"}, {"name": "Altındağ"}, {"name": "Ayaş"}, {"name": "Bala"},
                {"name": "Beypazarı"}, {"name": "Çamlıdere"}, {"name": "Çankaya"}, {"name": "Çubuk"},
                {"name": "Elmadağ"}, {"name": "Etimesgut"}, {"name": "Evren"}, {"name": "Gölbaşı"},
                {"name": "Güdül"}, {"name": "Haymana"}, {"name": "Kalecik"}, {"name": "Kazan"},
                {"name": "Keçiören"}, {"name": "Kızılcahamam"}, {"name": "Mamak"}, {"name": "Nallıhan"},
                {"name": "Polatlı"}, {"name": "Pursaklar"}, {"name": "Sincan"}, {"name": "Şereflikoçhisar"},
                {"name": "Yenimahalle"}
            ],
            "35": [  # İzmir
                {"name": "Aliağa"}, {"name": "Balçova"}, {"name": "Bayındır"}, {"name": "Bayraklı"},
                {"name": "Bergama"}, {"name": "Beydağ"}, {"name": "Bornova"}, {"name": "Buca"},
                {"name": "Çeşme"}, {"name": "Çiğli"}, {"name": "Dikili"}, {"name": "Foça"},
                {"name": "Gaziemir"}, {"name": "Güzelbahçe"}, {"name": "Karabağlar"}, {"name": "Karaburun"},
                {"name": "Karşıyaka"}, {"name": "Kemalpaşa"}, {"name": "Kınık"}, {"name": "Kiraz"},
                {"name": "Konak"}, {"name": "Menderes"}, {"name": "Menemen"}, {"name": "Narlıdere"},
                {"name": "Ödemiş"}, {"name": "Seferihisar"}, {"name": "Selçuk"}, {"name": "Tire"},
                {"name": "Torbalı"}, {"name": "Urla"}
            ],
            "07": [  # Antalya
                {"name": "Muratpaşa"}, {"name": "Kepez"}, {"name": "Konyaaltı"}, {"name": "Aksu"},
                {"name": "Döşemealtı"}, {"name": "Manavgat"}, {"name": "Alanya"}, {"name": "Serik"},
                {"name": "Kemer"}, {"name": "Gazipaşa"}, {"name": "Korkuteli"}, {"name": "Kumluca"},
                {"name": "Finike"}, {"name": "Kaş"}, {"name": "Elmalı"}, {"name": "Demre"},
                {"name": "Gündoğmuş"}, {"name": "İbradı"}
            ],
            "16": [  # Bursa
                {"name": "Osmangazi"}, {"name": "Yıldırım"}, {"name": "Nilüfer"}, {"name": "İnegöl"},
                {"name": "Gemlik"}, {"name": "Karacabey"}, {"name": "Mustafakemalpaşa"}, {"name": "Mudanya"},
                {"name": "Gürsu"}, {"name": "Kestel"}, {"name": "Yenişehir"}, {"name": "Orhangazi"},
                {"name": "Orhaneli"}, {"name": "Keles"}, {"name": "Harmancık"}, {"name": "Büyükorhan"}
            ]
        }
        return city_data.get(state_iso2, [])
    elif country_iso2 == "US" and state_iso2:
        # Amerika şehirleri (önemli eyaletler için)
        city_data = {
            "CA": [  # California
                {"name": "Los Angeles"}, {"name": "San Diego"}, {"name": "San Jose"}, {"name": "San Francisco"},
                {"name": "Fresno"}, {"name": "Sacramento"}, {"name": "Long Beach"}, {"name": "Oakland"},
                {"name": "Bakersfield"}, {"name": "Anaheim"}, {"name": "Santa Ana"}, {"name": "Riverside"},
                {"name": "Stockton"}, {"name": "Irvine"}, {"name": "Chula Vista"}, {"name": "Fremont"},
                {"name": "San Bernardino"}, {"name": "Modesto"}, {"name": "Fontana"}, {"name": "Oxnard"}
            ],
            "NY": [  # New York
                {"name": "New York City"}, {"name": "Buffalo"}, {"name": "Rochester"}, {"name": "Yonkers"},
                {"name": "Syracuse"}, {"name": "Albany"}, {"name": "New Rochelle"}, {"name": "Mount Vernon"},
                {"name": "Schenectady"}, {"name": "Utica"}, {"name": "White Plains"}, {"name": "Hempstead"},
                {"name": "Troy"}, {"name": "Niagara Falls"}, {"name": "Binghamton"}, {"name": "Freeport"},
                {"name": "Valley Stream"}, {"name": "Long Beach"}, {"name": "Rome"}, {"name": "Ithaca"}
            ],
            "TX": [  # Texas
                {"name": "Houston"}, {"name": "San Antonio"}, {"name": "Dallas"}, {"name": "Austin"},
                {"name": "Fort Worth"}, {"name": "El Paso"}, {"name": "Arlington"}, {"name": "Corpus Christi"},
                {"name": "Plano"}, {"name": "Lubbock"}, {"name": "Laredo"}, {"name": "Garland"},
                {"name": "Irving"}, {"name": "Amarillo"}, {"name": "Grand Prairie"}, {"name": "Brownsville"},
                {"name": "Pasadena"}, {"name": "Mesquite"}, {"name": "McKinney"}, {"name": "McAllen"}
            ],
            "FL": [  # Florida
                {"name": "Jacksonville"}, {"name": "Miami"}, {"name": "Tampa"}, {"name": "Orlando"},
                {"name": "St. Petersburg"}, {"name": "Hialeah"}, {"name": "Tallahassee"}, {"name": "Fort Lauderdale"},
                {"name": "Port St. Lucie"}, {"name": "Cape Coral"}, {"name": "Pembroke Pines"}, {"name": "Hollywood"},
                {"name": "Miramar"}, {"name": "Gainesville"}, {"name": "Coral Springs"}, {"name": "Miami Gardens"},
                {"name": "Clearwater"}, {"name": "Palm Bay"}, {"name": "West Palm Beach"}, {"name": "Pompano Beach"}
            ]
        }
        return city_data.get(state_iso2, [])
    elif country_iso2 == "DE" and state_iso2:
        # Almanya şehirleri (önemli eyaletler için)
        city_data = {
            "BY": [  # Bayern
                {"name": "München"}, {"name": "Nürnberg"}, {"name": "Augsburg"}, {"name": "Regensburg"},
                {"name": "Würzburg"}, {"name": "Ingolstadt"}, {"name": "Fürth"}, {"name": "Erlangen"},
                {"name": "Bayreuth"}, {"name": "Bamberg"}, {"name": "Aschaffenburg"}, {"name": "Landshut"},
                {"name": "Kempten"}, {"name": "Rosenheim"}, {"name": "Schweinfurt"}, {"name": "Passau"},
                {"name": "Hof"}, {"name": "Freising"}, {"name": "Straubing"}, {"name": "Dachau"}
            ],
            "NW": [  # Nordrhein-Westfalen
                {"name": "Köln"}, {"name": "Düsseldorf"}, {"name": "Dortmund"}, {"name": "Essen"},
                {"name": "Duisburg"}, {"name": "Bochum"}, {"name": "Wuppertal"}, {"name": "Bielefeld"},
                {"name": "Bonn"}, {"name": "Münster"}, {"name": "Gelsenkirchen"}, {"name": "Mönchengladbach"},
                {"name": "Aachen"}, {"name": "Krefeld"}, {"name": "Oberhausen"}, {"name": "Hagen"},
                {"name": "Hamm"}, {"name": "Mülheim"}, {"name": "Leverkusen"}, {"name": "Solingen"}
            ],
            "BW": [  # Baden-Württemberg
                {"name": "Stuttgart"}, {"name": "Mannheim"}, {"name": "Karlsruhe"}, {"name": "Freiburg"},
                {"name": "Heidelberg"}, {"name": "Heilbronn"}, {"name": "Ulm"}, {"name": "Pforzheim"},
                {"name": "Reutlingen"}, {"name": "Esslingen"}, {"name": "Tübingen"}, {"name": "Ludwigsburg"},
                {"name": "Konstanz"}, {"name": "Villingen-Schwenningen"}, {"name": "Aalen"}, {"name": "Sindelfingen"},
                {"name": "Schwäbisch Gmünd"}, {"name": "Friedrichshafen"}, {"name": "Offenburg"}, {"name": "Göppingen"}
            ]
        }
        return city_data.get(state_iso2, [])
    else:
        return []

# Dakikada bir calisan basit hatirlatma is parcacigi
def reminder_worker():
    with app.app_context():
        while True:
            try:
                now = datetime.utcnow()
                
                # Sadece gelecekteki randevular için hatırlatma kontrol et (24 saat içinde)
                future_limit = now + timedelta(hours=24)
                
                # Gonderilmemis ve epostasi olan hatirlatmalari getir
                # Sadece gelecekteki randevular için kontrol et
                pending = db.session.query(RandevuHatirlatma).join(Randevu).filter(
                    RandevuHatirlatma.Gonderildi == False,
                    RandevuHatirlatma.RecipientEmail != None,
                    RandevuHatirlatma.RecipientEmail != '',
                    Randevu.RandevuTarihi >= now,  # Gelecekteki randevular
                    Randevu.RandevuTarihi <= future_limit  # 24 saat içindeki randevular
                ).all()

                # Eğer gönderilecek hatırlatma yoksa, sessizce bekle
                if not pending:
                    import time
                    time.sleep(60)
                    continue

                for h in pending:
                    r = h.randevu
                    if not r:
                        continue
                    # Ne zaman gonderilmeli?
                    target_send_time = r.RandevuTarihi - timedelta(minutes=h.MinutesBefore)
                    # UTC varsayimi: RandevuTarihi zaten naive ise karşılaştırma naive-naive
                    if target_send_time <= now and not h.Gonderildi:
                        subject = f"Randevu Hatırlatma - {r.RandevuTarihi.strftime('%d.%m.%Y %H:%M')}"
                        body = (
                            f"Merhaba,\n\n"
                            f"{r.RandevuTarihi.strftime('%d.%m.%Y %H:%M')} tarihinde bir randevunuz bulunmaktadır.\n"
                            f"Referans: {r.RandevuBaslik}\n"
                            f"Süre: {r.RandevuSuresi or 60} dk\n\n"
                            f"Bu bir otomatik bilgilendirmedir."
                        )
                        # Önce firma ayarlarını kullan, yoksa genel ayarları kullan
                        ok = send_email_with_firma_settings(r.FirmaID, h.RecipientEmail, subject, body)
                        if not ok:
                            # Firma ayarları başarısız olursa genel ayarları dene
                            ok = send_email_simple(h.RecipientEmail, subject, body)
                        if ok:
                            h.Gonderildi = True
                            h.GonderimTarihi = datetime.utcnow()
                            db.session.commit()
            except Exception as e:
                print(f"Hatirlatma isci hatasi: {e}")
            finally:
                # 60 saniye bekle
                import time
                time.sleep(60)

# API: Ülke/Şehir/İlçe verileri
@app.route('/api/countries')
@login_required
def api_countries():
    """Tüm ülkeleri getir"""
    try:
        countries = get_countries()
        return jsonify(countries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/states/<country_iso2>')
@login_required
def api_states(country_iso2):
    """Belirli bir ülkenin eyaletlerini/şehirlerini getir"""
    try:
        states = get_states(country_iso2)
        return jsonify(states)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cities/<country_iso2>')
@app.route('/api/cities/<country_iso2>/<state_iso2>')
@login_required
def api_cities(country_iso2, state_iso2=None):
    """Belirli bir ülke/eyaletin şehirlerini getir"""
    try:
        cities = get_cities(country_iso2, state_iso2)
        return jsonify(cities)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API: Bildirimler
@app.route('/api/bildirimler')
@login_required
def api_bildirimler():
    items = Bildirim.query.filter_by(KullaniciID=session['user_id']).order_by(Bildirim.OlusturmaTarihi.desc()).limit(50).all()
    data = [
        {
            'id': b.BildirimID,
            'metin': b.Metin,
            'okundu': b.Okundu,
            'tip': b.Tip,
            'randevu_id': b.IlgiliRandevuID,
            'tarih': b.OlusturmaTarihi.strftime('%d.%m.%Y %H:%M')
        }
        for b in items
    ]
    unread = sum(1 for b in items if not b.Okundu)
    return jsonify({'success': True, 'items': data, 'unread': unread})

@app.route('/api/bildirimler/okundu', methods=['POST'])
@login_required
def api_bildirim_okundu():
    ids = request.json.get('ids', []) if request.is_json else []
    if not isinstance(ids, list):
        return jsonify({'success': False, 'message': 'ids listesi bekleniyor'}), 400
    Bildirim.query.filter(Bildirim.KullaniciID==session['user_id'], Bildirim.BildirimID.in_(ids)).update({'Okundu': True}, synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True})

# Yardimci: Kullanici ve randevu ayni firmada mi?
def _assert_same_firm_for_permission(kullanici_id: int, randevu_id: int) -> bool:
    kull = Kullanici.query.get(kullanici_id)
    rand = Randevu.query.get(randevu_id)
    if not kull or not rand:
        return False
    return kull.FirmaID == rand.FirmaID

@app.route('/set_language/<language>')
def set_language(language=None):
    if language and language in app.config['LANGUAGES']:
        session['language'] = language
        # Babel locale'ini manuel olarak güncelle
        from flask_babel import refresh
        refresh()
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Kullanici kontrolu
        user = Kullanici.query.filter_by(KullaniciAdi=username, Aktif=True).first()
        
        if user and user.Sifre == password:  # Geçici olarak düz metin karşılaştırma
            session['user_id'] = user.KullaniciID
            session['username'] = user.KullaniciAdi
            session['user_name'] = f"{user.Ad} {user.Soyad}"
            session['firma_id'] = user.FirmaID
            session['is_admin'] = user.Admin
            session['raporlar_modulu'] = user.RaporlarModulu
            session['ayarlar_modulu'] = user.AyarlarModulu
            
            flash('Başarıyla giriş yaptınız!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Başarıyla çıkış yaptınız!', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Kullanici randevularini getir
    if session.get('is_admin', False):
        # Admin tum randevulari gorebilir
        randevular = Randevu.query.filter_by(FirmaID=session['firma_id']).order_by(Randevu.RandevuTarihi.desc()).limit(10).all()
    else:
        # Normal kullanici sadece yetkili oldugu randevulari gorebilir
        randevular = db.session.query(Randevu).join(RandevuYetki).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id']
        ).order_by(Randevu.RandevuTarihi.desc()).limit(10).all()
    
    # Okunmamiş bildirim sayısı
    unread_count = Bildirim.query.filter_by(KullaniciID=session['user_id'], Okundu=False).count()
    return render_template('dashboard.html', randevular=randevular, unread_count=unread_count)

# Ayarlar Ana Sayfa
@app.route('/ayarlar')
@login_required
def ayarlar():
    # Modül izin kontrolü
    if not session.get('is_admin', False) and not session.get('ayarlar_modulu', False):
        flash('Bu sayfaya erişim yetkiniz yok', 'error')
        return redirect(url_for('dashboard'))
    unread_count = Bildirim.query.filter_by(KullaniciID=session['user_id'], Okundu=False).count()
    return render_template('ayarlar/index.html', unread_count=unread_count)

# Firma Ayarlari
@app.route('/ayarlar/firmalar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def ayarlar_firmalar():
    if request.method == 'POST':
        firma_adi = request.form.get('firma_adi')
        firma_kodu = request.form.get('firma_kodu')
        if not firma_adi or not firma_kodu:
            flash('Firma adı ve kodu zorunludur', 'error')
        else:
            if Firma.query.filter_by(FirmaKodu=firma_kodu).first():
                flash('Bu firma kodu zaten kullanılıyor', 'error')
            else:
                f = Firma(FirmaAdi=firma_adi, FirmaKodu=firma_kodu,
                          Adres=request.form.get('adres') or None,
                          Telefon=request.form.get('telefon') or None,
                          Email=request.form.get('email') or None)
                db.session.add(f)
                db.session.commit()
                flash('Firma eklendi', 'success')
        return redirect(url_for('ayarlar_firmalar'))

    firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
    return render_template('ayarlar/firmalar.html', firmalar=firmalar)

@app.route('/ayarlar/firmalar/sil/<int:firma_id>', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_firma_sil(firma_id):
    firma = Firma.query.get_or_404(firma_id)
    # Basit kontrol: Kullanıcı veya randevu bağlı ise silme (örnek amaçlı engelleme)
    if Kullanici.query.filter_by(FirmaID=firma.FirmaID).first() or Randevu.query.filter_by(FirmaID=firma.FirmaID).first():
        flash('Kullanıcı veya randevu bağlı firmalar silinemez', 'error')
    else:
        db.session.delete(firma)
        db.session.commit()
        flash('Firma silindi', 'success')
    return redirect(url_for('ayarlar_firmalar'))

@app.route('/ayarlar/firmalar/guncelle', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_firma_guncelle():
    try:
        firma_id = request.form.get('firma_id', type=int)
        if not firma_id:
            flash('Firma ID bulunamadı', 'error')
            return redirect(url_for('ayarlar_firmalar'))
        
        firma = Firma.query.get_or_404(firma_id)
        
        # Firma kodunun benzersizliğini kontrol et (kendi kodu hariç)
        existing_firma = Firma.query.filter(
            Firma.FirmaKodu == request.form['firma_kodu'],
            Firma.FirmaID != firma_id
        ).first()
        
        if existing_firma:
            flash('Bu firma kodu zaten kullanılıyor', 'error')
            return redirect(url_for('ayarlar_firmalar'))
        
        # Firma bilgilerini güncelle
        firma.FirmaAdi = request.form['firma_adi']
        firma.FirmaKodu = request.form['firma_kodu']
        firma.Adres = request.form.get('adres', '')
        firma.Telefon = request.form.get('telefon', '')
        firma.Email = request.form.get('email', '')
        firma.GuncellemeTarihi = datetime.utcnow()
        
        db.session.commit()
        flash('Firma başarıyla güncellendi', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Firma güncellenirken hata: {str(e)}', 'error')
    
    return redirect(url_for('ayarlar_firmalar'))

# Kullanici Ayarlari
@app.route('/ayarlar/kullanicilar', methods=['GET', 'POST'])
@login_required
@admin_required
def ayarlar_kullanicilar():
    if request.method == 'POST':
        kullanici_adi = request.form.get('kullanici_adi')
        email = request.form.get('email')
        firma_id = request.form.get('firma_id', type=int)
        sifre = request.form.get('sifre')
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        
        # Admin değilse sadece kendi firmasına kullanıcı ekleyebilir
        if not session.get('is_admin', False):
            firma_id = session.get('firma_id')
        
        if not all([kullanici_adi, email, firma_id, sifre, ad, soyad]):
            flash('Tüm alanlar zorunludur', 'error')
        elif Kullanici.query.filter((Kullanici.KullaniciAdi==kullanici_adi) | (Kullanici.Email==email)).first():
            flash('Kullanıcı adı veya e-posta mevcut', 'error')
        else:
            # Modül izinlerini al
            raporlar_modulu = 'raporlar_modulu' in request.form
            ayarlar_modulu = 'ayarlar_modulu' in request.form
            
            u = Kullanici(KullaniciAdi=kullanici_adi, Email=email, FirmaID=firma_id,
                          Sifre=sifre, Ad=ad, Soyad=soyad, Aktif=True,
                          RaporlarModulu=raporlar_modulu, AyarlarModulu=ayarlar_modulu)
            db.session.add(u)
            db.session.commit()
            flash('Kullanıcı eklendi', 'success')
        return redirect(url_for('ayarlar_kullanicilar'))

    # Admin ise tüm firmaları, değilse sadece kendi firmasını göster
    if session.get('is_admin', False):
        firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
        kullanicilar = Kullanici.query.order_by(Kullanici.KullaniciID.desc()).limit(100).all()
    else:
        firmalar = Firma.query.filter_by(FirmaID=session.get('firma_id')).all()
        kullanicilar = Kullanici.query.filter_by(FirmaID=session.get('firma_id')).order_by(Kullanici.KullaniciID.desc()).limit(100).all()
    
    return render_template('ayarlar/kullanicilar.html', firmalar=firmalar, kullanicilar=kullanicilar)

@app.route('/ayarlar/kullanicilar/duzenle/<int:kullanici_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def ayarlar_kullanici_duzenle(kullanici_id):
    kullanici = Kullanici.query.get_or_404(kullanici_id)
    
    # Admin değilse sadece kendi firmasının kullanıcılarını düzenleyebilir
    if not session.get('is_admin', False) and kullanici.FirmaID != session.get('firma_id'):
        flash('Bu kullanıcıyı düzenleme yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_kullanicilar'))
    
    if request.method == 'POST':
        kullanici_adi = request.form.get('kullanici_adi')
        email = request.form.get('email')
        firma_id = request.form.get('firma_id', type=int)
        sifre = request.form.get('sifre')
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        aktif = 'aktif' in request.form
        raporlar_modulu = 'raporlar_modulu' in request.form
        ayarlar_modulu = 'ayarlar_modulu' in request.form
        
        # Admin değilse firma değiştiremez
        if not session.get('is_admin', False):
            firma_id = kullanici.FirmaID
        
        if not all([kullanici_adi, email, firma_id, ad, soyad]):
            flash('Tüm alanlar zorunludur', 'error')
        else:
            # Kullanıcı adı ve email kontrolü (kendisi hariç)
            existing_user = Kullanici.query.filter(
                (Kullanici.KullaniciAdi == kullanici_adi) | (Kullanici.Email == email),
                Kullanici.KullaniciID != kullanici_id
            ).first()
            
            if existing_user:
                flash('Kullanıcı adı veya e-posta başka bir kullanıcı tarafından kullanılıyor', 'error')
            else:
                # Güncelleme
                kullanici.KullaniciAdi = kullanici_adi
                kullanici.Email = email
                kullanici.FirmaID = firma_id
                kullanici.Ad = ad
                kullanici.Soyad = soyad
                kullanici.Aktif = aktif
                kullanici.RaporlarModulu = raporlar_modulu
                kullanici.AyarlarModulu = ayarlar_modulu
                
                # Şifre güncelleme (sadece girilmişse)
                if sifre:
                    kullanici.Sifre = sifre
                
                db.session.commit()
                flash('Kullanıcı güncellendi', 'success')
                return redirect(url_for('ayarlar_kullanicilar'))
    
    # Admin ise tüm firmaları, değilse sadece kendi firmasını göster
    if session.get('is_admin', False):
        firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
    else:
        firmalar = Firma.query.filter_by(FirmaID=session.get('firma_id')).all()
    
    return render_template('ayarlar/kullanici_duzenle.html', kullanici=kullanici, firmalar=firmalar)

@app.route('/ayarlar/kullanicilar/sil/<int:kullanici_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_kullanici_sil(kullanici_id):
    if kullanici_id == session.get('user_id'):
        flash('Kendi hesabınızı silemezsiniz', 'error')
        return redirect(url_for('ayarlar_kullanicilar'))
    
    u = Kullanici.query.get_or_404(kullanici_id)
    
    # Admin değilse sadece kendi firmasının kullanıcılarını silebilir
    if not session.get('is_admin', False) and u.FirmaID != session.get('firma_id'):
        flash('Bu kullanıcıyı silme yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_kullanicilar'))
    
    db.session.delete(u)
    db.session.commit()
    flash('Kullanıcı silindi', 'success')
    return redirect(url_for('ayarlar_kullanicilar'))

# Randevu Defteri Ayarlari
@app.route('/ayarlar/defter', methods=['GET', 'POST'])
@login_required
@super_admin_required
def ayarlar_defter():
    if request.method == 'POST':
        ayar_id = request.form.get('ayar_id', type=int)
        firma_id = request.form.get('firma_id', type=int)
        defter_adi = request.form.get('defter_adi') or 'Varsayilan Defter'
        calisma_gunleri = ','.join(request.form.getlist('calisma_gunleri')) or '1,2,3,4,5'
        baslangic = request.form.get('baslangic') or '09:00'
        bitis = request.form.get('bitis') or '18:00'
        slot = request.form.get('slot', type=int) or 30

        if ayar_id:
            ayar = RandevuDefterAyar.query.get_or_404(ayar_id)
            ayar.FirmaID = firma_id
            ayar.DefterAdi = defter_adi
            ayar.CalismaGunleri = calisma_gunleri
            ayar.BaslangicSaati = baslangic
            ayar.BitisSaati = bitis
            ayar.SlotDakika = slot
        else:
            ayar = RandevuDefterAyar(
                FirmaID=firma_id,
                DefterAdi=defter_adi,
                CalismaGunleri=calisma_gunleri,
                BaslangicSaati=baslangic,
                BitisSaati=bitis,
                SlotDakika=slot
            )
            db.session.add(ayar)
        db.session.commit()

        # Kaydet ile birlikte blok girildiyse ekle
        t1 = request.form.get('blok_tarih1')
        t2 = request.form.get('blok_tarih2')
        s1 = request.form.get('blok_saat1')
        s2 = request.form.get('blok_saat2')
        aciklama = request.form.get('blok_aciklama')
        if t1 or t2 or s1 or s2 or (aciklama and aciklama.strip()):
            try:
                bas_t = datetime.strptime(t1, '%Y-%m-%d').date() if t1 else None
                bit_t = datetime.strptime(t2, '%Y-%m-%d').date() if t2 else None
            except Exception:
                flash('Blok tarih formatı geçersiz', 'error')
                return redirect(url_for('ayarlar_defter'))
            if not bas_t:
                flash('Blok için başlangıç tarihi zorunludur', 'error')
                return redirect(url_for('ayarlar_defter'))
            if bit_t and bit_t < bas_t:
                flash('Blok bitiş tarihi başlangıçtan önce olamaz', 'error')
                return redirect(url_for('ayarlar_defter'))
            try:
                yeni_blok = RandevuDefterBlok(
                    FirmaID=ayar.FirmaID,
                    DefterID=ayar.AyarID,
                    BaslangicTarih=bas_t,
                    BitisTarih=bit_t,
                    SaatBaslangic=s1 or None,
                    SaatBitis=s2 or None,
                    Aciklama=(aciklama or '').strip() or None,
                    Aktif=True
                )
                db.session.add(yeni_blok)
                db.session.commit()
                flash('Blok eklendi', 'success')
            except Exception as e:
                db.session.rollback()
                print('Blok ekleme hatası:', e)
                flash('Blok eklenemedi', 'error')

        flash('Randevu defteri ayarları kaydedildi', 'success')
        return redirect(url_for('ayarlar_defter'))

    firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
    ayarlar_list = RandevuDefterAyar.query.order_by(RandevuDefterAyar.AyarID.desc()).all()
    bloklar = RandevuDefterBlok.query.filter_by(FirmaID=session['firma_id']).order_by(RandevuDefterBlok.BlokID.desc()).all()
    
    # Mevcut firmanın kategorilerini getir
    kategoriler = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id']
    ).filter(MusteriKategori.Aktif == 1).order_by(MusteriKategori.KategoriAdi).all()
    
    return render_template('ayarlar/defter.html', firmalar=firmalar, ayarlar_list=ayarlar_list, kategoriler=kategoriler, bloklar=bloklar)

@app.route('/ayarlar/defter/blok/ekle', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_defter_blok_ekle():
    firma_id = session['firma_id']
    defter_id = request.form.get('blok_defter_id', type=int)
    t1 = request.form.get('blok_tarih1')
    t2 = request.form.get('blok_tarih2')
    s1 = request.form.get('blok_saat1')
    s2 = request.form.get('blok_saat2')
    aciklama = request.form.get('blok_aciklama', '')
    try:
        bas_t = datetime.strptime(t1, '%Y-%m-%d').date() if t1 else None
        bit_t = datetime.strptime(t2, '%Y-%m-%d').date() if t2 else None
    except Exception:
        flash('Tarih formatı geçersiz', 'error')
        return redirect(url_for('ayarlar_defter'))
    if not bas_t:
        flash('Başlangıç tarihi zorunludur', 'error')
        return redirect(url_for('ayarlar_defter'))
    if bit_t and bit_t < bas_t:
        flash('Bitiş tarihi başlangıçtan önce olamaz', 'error')
        return redirect(url_for('ayarlar_defter'))

    blok = RandevuDefterBlok(
        FirmaID=firma_id,
        DefterID=defter_id,
        BaslangicTarih=bas_t,
        BitisTarih=bit_t,
        SaatBaslangic=s1 or None,
        SaatBitis=s2 or None,
        Aciklama=aciklama,
        Aktif=True
    )
    db.session.add(blok)
    db.session.commit()
    flash('Saat kapatma bloğu eklendi', 'success')
    return redirect(url_for('ayarlar_defter'))

@app.route('/ayarlar/defter/blok/sil/<int:blok_id>', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_defter_blok_sil(blok_id: int):
    b = RandevuDefterBlok.query.filter_by(BlokID=blok_id, FirmaID=session['firma_id']).first()
    if not b:
        flash('Blok bulunamadı', 'error')
        return redirect(url_for('ayarlar_defter'))
    db.session.delete(b)
    db.session.commit()
    flash('Blok silindi', 'success')
    return redirect(url_for('ayarlar_defter'))

@app.route('/ayarlar/defter/pasiflestir/<int:ayar_id>', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_defter_pasiflestir(ayar_id: int):
    ayar = RandevuDefterAyar.query.get_or_404(ayar_id)
    ayar.Aktif = not (ayar.Aktif if ayar.Aktif is not None else True)
    db.session.commit()
    flash('Randevu defteri durumu güncellendi', 'success')
    return redirect(url_for('ayarlar_defter'))

# Kategori Yönetimi
@app.route('/ayarlar/kategori/ekle', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_kategori_ekle():
    kategori_adi = request.form.get('kategori_adi')
    kategori_renk = request.form.get('kategori_renk', '#007bff')
    kategori_aciklama = request.form.get('kategori_aciklama', '')
    kategori_aktif = request.form.get('kategori_aktif') == 'on'
    
    if not kategori_adi:
        flash('Kategori adı zorunludur', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    # Aynı isimde kategori var mı kontrol et
    existing = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id'],
        KategoriAdi=kategori_adi
    ).first()
    
    if existing:
        flash('Bu isimde bir kategori zaten mevcut', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    kategori = MusteriKategori(
        FirmaID=session['firma_id'],
        KategoriAdi=kategori_adi,
        Renk=kategori_renk,
        Aciklama=kategori_aciklama,
        Aktif=kategori_aktif
    )
    
    db.session.add(kategori)
    db.session.commit()
    
    flash('Kategori başarıyla eklendi', 'success')
    return redirect(url_for('ayarlar_defter'))

@app.route('/ayarlar/kategori/guncelle', methods=['POST'])
@login_required
@super_admin_required
def ayarlar_kategori_guncelle():
    kategori_id = request.form.get('kategori_id', type=int)
    kategori_adi = request.form.get('kategori_adi')
    kategori_renk = request.form.get('kategori_renk', '#007bff')
    kategori_aciklama = request.form.get('kategori_aciklama', '')
    kategori_aktif = request.form.get('kategori_aktif') == 'on'
    
    if not kategori_id or not kategori_adi:
        flash('Kategori bilgileri eksik', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    kategori = MusteriKategori.query.filter_by(
        KategoriID=kategori_id,
        FirmaID=session['firma_id']
    ).first()
    
    if not kategori:
        flash('Kategori bulunamadı', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    # Aynı isimde başka kategori var mı kontrol et
    existing = MusteriKategori.query.filter(
        MusteriKategori.FirmaID == session['firma_id'],
        MusteriKategori.KategoriAdi == kategori_adi,
        MusteriKategori.KategoriID != kategori_id
    ).first()
    
    if existing:
        flash('Bu isimde bir kategori zaten mevcut', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    kategori.KategoriAdi = kategori_adi
    kategori.Renk = kategori_renk
    kategori.Aciklama = kategori_aciklama
    kategori.Aktif = kategori_aktif
    
    db.session.commit()
    
    flash('Kategori başarıyla güncellendi', 'success')
    return redirect(url_for('ayarlar_defter'))

@app.route('/ayarlar/kategori/sil')
@login_required
@super_admin_required
def ayarlar_kategori_sil():
    kategori_id = request.args.get('id', type=int)
    
    if not kategori_id:
        flash('Kategori ID gerekli', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    kategori = MusteriKategori.query.filter_by(
        KategoriID=kategori_id,
        FirmaID=session['firma_id']
    ).first()
    
    if not kategori:
        flash('Kategori bulunamadı', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    # Bu kategoriyi kullanan müşteri var mı kontrol et
    musteri_count = Musteri.query.filter_by(KategoriID=kategori_id).count()
    
    if musteri_count > 0:
        flash(f'Bu kategoriyi kullanan {musteri_count} müşteri var. Önce müşterilerin kategorilerini değiştirin.', 'error')
        return redirect(url_for('ayarlar_defter'))
    
    db.session.delete(kategori)
    db.session.commit()
    
    flash('Kategori başarıyla silindi', 'success')
    return redirect(url_for('ayarlar_defter'))

# Randevu Referans Ayarlari
@app.route('/ayarlar/referanslar', methods=['GET', 'POST'])
@login_required
@admin_required
def ayarlar_referanslar():
    if request.method == 'POST':
        firma_id = request.form.get('firma_id', type=int)
        ad = request.form.get('ad')
        
        # Admin değilse sadece kendi firmasına referans ekleyebilir
        if not session.get('is_admin', False):
            firma_id = session.get('firma_id')
        
        if not firma_id or not ad:
            flash('Firma ve referans adı zorunludur', 'error')
        else:
            ref = RandevuReferans(FirmaID=firma_id, Ad=ad)
            db.session.add(ref)
            db.session.commit()
            flash('Referans eklendi', 'success')
        return redirect(url_for('ayarlar_referanslar'))

    # Admin ise tüm firmaları, değilse sadece kendi firmasını göster
    if session.get('is_admin', False):
        firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
        refs = db.session.query(RandevuReferans).order_by(RandevuReferans.ReferansID.desc()).limit(200).all()
    else:
        firmalar = Firma.query.filter_by(FirmaID=session.get('firma_id')).all()
        refs = db.session.query(RandevuReferans).filter_by(FirmaID=session.get('firma_id')).order_by(RandevuReferans.ReferansID.desc()).limit(200).all()
    
    return render_template('ayarlar/referanslar.html', firmalar=firmalar, referanslar=refs)

@app.route('/ayarlar/referanslar/sil/<int:ref_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_referans_sil(ref_id):
    ref = RandevuReferans.query.get_or_404(ref_id)
    
    # Admin değilse sadece kendi firmasının referanslarını silebilir
    if not session.get('is_admin', False) and ref.FirmaID != session.get('firma_id'):
        flash('Bu referansı silme yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_referanslar'))
    
    db.session.delete(ref)
    db.session.commit()
    flash('Referans silindi', 'success')
    return redirect(url_for('ayarlar_referanslar'))

# Randevu İşlemleri
@app.route('/ayarlar/islemler', methods=['GET', 'POST'])
@login_required
@admin_required
def ayarlar_islemler():
    if request.method == 'POST':
        # Firma, oturumdaki kullanıcıdan alınır (formdan değil)
        firma_id = session.get('firma_id')
        defter_id = request.form.get('defter_id', type=int)
        islem_adi = request.form.get('islem_adi')
        islem_aciklamasi = ''
        islem_suresi = 60
        islem_ucreti = 0.00
        
        # Her durumda sadece kendi firmasına eklenir
        if not firma_id:
            flash('Firma bilgisi bulunamadı', 'error')
            return redirect(url_for('ayarlar_islemler'))
            # Non-admin için defter doğrulaması: kendi firmasına ait değilse temizle
            if defter_id:
                dft = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=firma_id, Aktif=True).first()
                if not dft:
                    defter_id = None
        
        if not firma_id or not islem_adi:
            flash('Firma ve işlem adı zorunludur', 'error')
            return redirect(url_for('ayarlar_islemler'))
        # Defter seçimi zorunlu
        if not defter_id:
            flash('Defter seçimi zorunludur', 'error')
            return redirect(url_for('ayarlar_islemler'))
        # Seçilen defter firmaya ait mi?
        dft = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=firma_id, Aktif=True).first()
        if not dft:
            flash('Seçilen defter bulunamadı veya firmaya ait değil', 'error')
            return redirect(url_for('ayarlar_islemler'))
        else:
            islem = RandevuIslem(
                FirmaID=firma_id,
                DefterID=defter_id,
                IslemAdi=islem_adi,
                Aktif=True,
                OlusturmaTarihi=datetime.utcnow()
            )
            db.session.add(islem)
            db.session.commit()
            flash('İşlem eklendi', 'success')
        return redirect(url_for('ayarlar_islemler'))

    # Listeleme de oturumdaki firmaya göre yapılır
    aktif_firma_id = session.get('firma_id')
    islemler = db.session.query(RandevuIslem).filter_by(FirmaID=aktif_firma_id).order_by(RandevuIslem.IslemID.desc()).limit(200).all()
    defterler = RandevuDefterAyar.query.filter_by(FirmaID=aktif_firma_id, Aktif=True).order_by(RandevuDefterAyar.DefterAdi).all()
    
    return render_template('ayarlar/islemler.html', islemler=islemler, defterler=defterler)

@app.route('/ayarlar/islemler/guncelle/<int:islem_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_islem_guncelle(islem_id: int):
    firma_id = session.get('firma_id')
    if not firma_id:
        flash('Firma bilgisi bulunamadı', 'error')
        return redirect(url_for('ayarlar_islemler'))

    islem = RandevuIslem.query.filter_by(IslemID=islem_id, FirmaID=firma_id).first()
    if not islem:
        flash('İşlem bulunamadı veya yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_islemler'))

    islem_adi = request.form.get('islem_adi', '').strip()
    defter_id = request.form.get('defter_id', type=int)
    if not islem_adi or not defter_id:
        flash('İşlem adı ve defter zorunludur', 'error')
        return redirect(url_for('ayarlar_islemler'))

    dft = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=firma_id, Aktif=True).first()
    if not dft:
        flash('Seçilen defter bulunamadı veya firmaya ait değil', 'error')
        return redirect(url_for('ayarlar_islemler'))

    islem.IslemAdi = islem_adi
    islem.DefterID = defter_id
    db.session.commit()
    flash('İşlem güncellendi', 'success')
    return redirect(url_for('ayarlar_islemler'))

@app.route('/ayarlar/islemler/sil/<int:islem_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_islem_sil(islem_id):
    islem = RandevuIslem.query.get_or_404(islem_id)
    
    # Admin değilse sadece kendi firmasının işlemlerini silebilir
    if not session.get('is_admin', False) and islem.FirmaID != session.get('firma_id'):
        flash('Bu işlemi silme yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_islemler'))
    
    db.session.delete(islem)
    db.session.commit()
    flash('İşlem silindi', 'success')
    return redirect(url_for('ayarlar_islemler'))

# E-posta Ayarları
@app.route('/ayarlar/email')
@login_required
@admin_required
def ayarlar_email():
    # Admin ise firma seçimi yapabilir
    if session.get('is_admin', False):
        selected_firma_id = request.args.get('firma_id', type=int)
        if selected_firma_id:
            firma = Firma.query.get(selected_firma_id)
            if not firma:
                flash('Seçilen firma bulunamadı!', 'error')
                return redirect(url_for('ayarlar'))
        else:
            # İlk firma varsayılan olarak seçili
            firma = Firma.query.first()
            if not firma:
                flash('Hiç firma bulunamadı!', 'error')
                return redirect(url_for('ayarlar'))
            selected_firma_id = firma.FirmaID
        
        tum_firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
        email_ayar = FirmaEmailAyar.query.filter_by(FirmaID=selected_firma_id).first()
        
        return render_template('ayarlar/email.html', 
                             email_ayar=email_ayar, 
                             firma=firma, 
                             tum_firmalar=tum_firmalar,
                             selected_firma_id=selected_firma_id,
                             is_admin=True)
    else:
        # Normal kullanıcı sadece kendi firmasını görebilir
        firma = Firma.query.get(session['firma_id'])
        if not firma:
            flash('Firma bilgisi bulunamadı!', 'error')
            return redirect(url_for('ayarlar'))
        
        email_ayar = FirmaEmailAyar.query.filter_by(FirmaID=session['firma_id']).first()
        return render_template('ayarlar/email.html', 
                             email_ayar=email_ayar, 
                             firma=firma,
                             is_admin=False)

@app.route('/ayarlar/email/ekle', methods=['POST'])
@login_required
@admin_required
def ayarlar_email_ekle():
    try:
        # Admin ise seçilen firmayı kullan, değilse kendi firmasını
        if session.get('is_admin', False):
            firma_id = request.form.get('firma_id', type=int) or session['firma_id']
        else:
            firma_id = session['firma_id']
        
        email_ayar = FirmaEmailAyar(
            FirmaID=firma_id,
            SMTP_Sunucu=request.form['smtp_sunucu'],
            SMTP_Port=int(request.form['smtp_port']),
            KullaniciAdi=request.form['kullanici_adi'],
            Sifre=request.form['sifre'],
            SSL_Kullan='ssl_kullan' in request.form,
            VarsayilanGonderenAdi=request.form.get('gonderen_adi', ''),
            VarsayilanGonderenEmail=request.form.get('gonderen_email', ''),
            Aktif='aktif' in request.form
        )
        db.session.add(email_ayar)
        db.session.commit()
        flash('E-posta ayarları eklendi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'E-posta ayarları eklenirken hata: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_email', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_email'))

@app.route('/ayarlar/email/guncelle/<int:ayar_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_email_guncelle(ayar_id):
    try:
        # Admin ise herhangi bir firmanın ayarını güncelleyebilir
        if session.get('is_admin', False):
            email_ayar = FirmaEmailAyar.query.get_or_404(ayar_id)
        else:
            email_ayar = FirmaEmailAyar.query.filter_by(EmailAyarID=ayar_id, FirmaID=session['firma_id']).first_or_404()
        
        email_ayar.SMTP_Sunucu = request.form['smtp_sunucu']
        email_ayar.SMTP_Port = int(request.form['smtp_port'])
        email_ayar.KullaniciAdi = request.form['kullanici_adi']
        email_ayar.Sifre = request.form['sifre']
        email_ayar.SSL_Kullan = 'ssl_kullan' in request.form
        email_ayar.VarsayilanGonderenAdi = request.form.get('gonderen_adi', '')
        email_ayar.VarsayilanGonderenEmail = request.form.get('gonderen_email', '')
        email_ayar.Aktif = 'aktif' in request.form
        db.session.commit()
        flash('E-posta ayarları güncellendi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'E-posta ayarları güncellenirken hata: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_email', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_email'))

@app.route('/ayarlar/email/sil/<int:ayar_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_email_sil(ayar_id):
    try:
        email_ayar = FirmaEmailAyar.query.filter_by(EmailAyarID=ayar_id, FirmaID=session['firma_id']).first_or_404()
        db.session.delete(email_ayar)
        db.session.commit()
        flash('E-posta ayarları silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'E-posta ayarları silinirken hata: {str(e)}', 'error')
    return redirect(url_for('ayarlar_email'))

# SMS Ayarları
@app.route('/ayarlar/sms')
@login_required
@admin_required
def ayarlar_sms():
    # Admin ise firma seçimi yapabilir
    if session.get('is_admin', False):
        selected_firma_id = request.args.get('firma_id', type=int)
        if selected_firma_id:
            firma = Firma.query.get(selected_firma_id)
            if not firma:
                flash('Seçilen firma bulunamadı!', 'error')
                return redirect(url_for('ayarlar'))
        else:
            # İlk firma varsayılan olarak seçili
            firma = Firma.query.first()
            if not firma:
                flash('Hiç firma bulunamadı!', 'error')
                return redirect(url_for('ayarlar'))
            selected_firma_id = firma.FirmaID
        
        tum_firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
        sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=selected_firma_id).first()
        
        return render_template('ayarlar/sms.html', 
                             sms_ayar=sms_ayar, 
                             firma=firma, 
                             tum_firmalar=tum_firmalar,
                             selected_firma_id=selected_firma_id,
                             is_admin=True)
    else:
        # Normal kullanıcı sadece kendi firmasını görebilir
        firma = Firma.query.get(session['firma_id'])
        if not firma:
            flash('Firma bilgisi bulunamadı!', 'error')
            return redirect(url_for('ayarlar'))
        
        sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=session['firma_id']).first()
        return render_template('ayarlar/sms.html', 
                             sms_ayar=sms_ayar, 
                             firma=firma,
                             is_admin=False)

@app.route('/ayarlar/sms/ekle', methods=['POST'])
@login_required
@admin_required
def ayarlar_sms_ekle():
    try:
        sms_ayar = FirmaSMSAyar(
            FirmaID=session['firma_id'],
            SMSFirmasi=request.form['sms_firmasi'],
            API_Key=request.form.get('api_key', ''),
            API_Secret=request.form.get('api_secret', ''),
            KullaniciAdi=request.form.get('kullanici_adi', ''),
            Sifre=request.form.get('sifre', ''),
            GondericiAdi=request.form.get('gonderici_adi', ''),
            API_URL=request.form.get('api_url', ''),
            Aktif='aktif' in request.form
        )
        db.session.add(sms_ayar)
        db.session.commit()
        flash('SMS ayarları eklendi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'SMS ayarları eklenirken hata: {str(e)}', 'error')
    return redirect(url_for('ayarlar_sms'))

@app.route('/ayarlar/sms/guncelle/<int:ayar_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_sms_guncelle(ayar_id):
    try:
        sms_ayar = FirmaSMSAyar.query.filter_by(SMSAyarID=ayar_id, FirmaID=session['firma_id']).first_or_404()
        sms_ayar.SMSFirmasi = request.form['sms_firmasi']
        sms_ayar.API_Key = request.form.get('api_key', '')
        sms_ayar.API_Secret = request.form.get('api_secret', '')
        sms_ayar.KullaniciAdi = request.form.get('kullanici_adi', '')
        sms_ayar.Sifre = request.form.get('sifre', '')
        sms_ayar.GondericiAdi = request.form.get('gonderici_adi', '')
        sms_ayar.API_URL = request.form.get('api_url', '')
        sms_ayar.Aktif = 'aktif' in request.form
        db.session.commit()
        flash('SMS ayarları güncellendi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'SMS ayarları güncellenirken hata: {str(e)}', 'error')
    return redirect(url_for('ayarlar_sms'))

@app.route('/ayarlar/sms/sil/<int:ayar_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_sms_sil(ayar_id):
    try:
        sms_ayar = FirmaSMSAyar.query.filter_by(SMSAyarID=ayar_id, FirmaID=session['firma_id']).first_or_404()
        db.session.delete(sms_ayar)
        db.session.commit()
        flash('SMS ayarları silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'SMS ayarları silinirken hata: {str(e)}', 'error')
    return redirect(url_for('ayarlar_sms'))

@app.route('/randevular')
@login_required
def randevular():
    # Randevu listesi + referans ve defter filtresi
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuReferans.Ad).all()
    defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuDefterAyar.DefterAdi).all()
    
    ref_id = request.args.get('referans_id', type=int)
    defter_id = request.args.get('defter_id', type=int)
    
    ref = None
    defter = None
    if ref_id:
        ref = RandevuReferans.query.filter_by(ReferansID=ref_id, FirmaID=session['firma_id']).first()
    if defter_id:
        defter = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=session['firma_id']).first()

    base_query = Randevu.query if session.get('is_admin', False) else db.session.query(Randevu).join(RandevuYetki).filter(
        RandevuYetki.KullaniciID == session['user_id'],
        RandevuYetki.GoruntulemeYetkisi == True
    )

    q = base_query.filter(Randevu.FirmaID == session['firma_id'])
    if ref is not None:
        q = q.filter(Randevu.RandevuBaslik == ref.Ad)
    if defter is not None:
        q = q.filter(Randevu.DefterID == defter.AyarID)

    randevular = q.order_by(Randevu.RandevuTarihi.desc()).all()
    
    return render_template('randevular.html', 
                         randevular=randevular, 
                         referanslar=referanslar, 
                         defterler=defterler,
                         selected_referans_id=ref_id,
                         selected_defter_id=defter_id)

@app.route('/rapor/musteriler')
@login_required
def rapor_musteriler():
    # Modül izin kontrolü
    if not session.get('raporlar_modulu', False):
        flash('Bu sayfaya erişim yetkiniz yok', 'error')
        return redirect(url_for('dashboard'))
    """Müşteri raporu: filtreler, KPI'lar, tablo ve CSV dışa aktarım"""
    firma_id = session['firma_id']

    # Filtreler
    tarih_baslangic_str = request.args.get('baslangic')
    tarih_bitis_str = request.args.get('bitis')
    kategori_id = request.args.get('kategori_id', type=int)
    sadece_aktif = request.args.get('aktif', default='1')  # '1' aktif, '' hepsi
    iletisim_var = request.args.get('iletisim_var')  # 'telefon', 'email', 'herikisi'
    format_tip = request.args.get('format')  # 'csv' ise CSV döndür

    # Tarih aralığı
    try:
        baslangic = datetime.strptime(tarih_baslangic_str, '%Y-%m-%d') if tarih_baslangic_str else None
    except Exception:
        baslangic = None
    try:
        bitis = datetime.strptime(tarih_bitis_str, '%Y-%m-%d') if tarih_bitis_str else None
    except Exception:
        bitis = None

    # Müşteri temel sorgusu
    musteri_query = Musteri.query.filter_by(FirmaID=firma_id)
    if sadece_aktif == '1':
        musteri_query = musteri_query.filter(Musteri.Aktif == True)
    elif sadece_aktif == '0':
        musteri_query = musteri_query.filter(Musteri.Aktif == False)
    if kategori_id:
        musteri_query = musteri_query.filter(Musteri.KategoriID == kategori_id)
    if iletisim_var == 'telefon':
        musteri_query = musteri_query.filter(Musteri.Telefon.isnot(None), Musteri.Telefon != '')
    elif iletisim_var == 'email':
        musteri_query = musteri_query.filter(Musteri.Email.isnot(None), Musteri.Email != '')
    elif iletisim_var == 'herikisi':
        musteri_query = musteri_query.filter(
            Musteri.Telefon.isnot(None), Musteri.Telefon != '',
            Musteri.Email.isnot(None), Musteri.Email != ''
        )

    musteriler = musteri_query.order_by(Musteri.MusteriAdi, Musteri.MusteriSoyadi).all()

    # KPI'lar
    toplam_musteri = Musteri.query.filter_by(FirmaID=firma_id).count()
    aktif_musteri = Musteri.query.filter_by(FirmaID=firma_id, Aktif=True).count()
    yeni_musteri = 0
    if baslangic or bitis:
        q = Musteri.query.filter(Musteri.FirmaID == firma_id)
        if baslangic:
            q = q.filter(Musteri.OlusturmaTarihi >= baslangic)
        if bitis:
            q = q.filter(Musteri.OlusturmaTarihi < (bitis + timedelta(days=1)))
        yeni_musteri = q.count()

    # Randevu istatistikleri (müşteri başına randevu sayısı)
    randevu_q = db.session.query(Randevu.MusteriID, db.func.count(Randevu.RandevuID).label('adet')) 
    randevu_q = randevu_q.filter(Randevu.FirmaID == firma_id, Randevu.MusteriID.isnot(None))
    if baslangic:
        randevu_q = randevu_q.filter(Randevu.RandevuTarihi >= baslangic)
    if bitis:
        randevu_q = randevu_q.filter(Randevu.RandevuTarihi < (bitis + timedelta(days=1)))
    randevu_q = randevu_q.group_by(Randevu.MusteriID)
    musteri_id_to_randevu_adet = {mid: adet for mid, adet in randevu_q.all()}

    # Top N müşteriler (randevu sayısına göre) - SQL Server için alt sorgu ile
    randevu_count_sq = (
        db.session.query(
            Randevu.MusteriID.label('mid'),
            db.func.count(Randevu.RandevuID).label('adet')
        )
        .filter(Randevu.FirmaID == firma_id, Randevu.MusteriID.isnot(None))
    )
    if baslangic:
        randevu_count_sq = randevu_count_sq.filter(Randevu.RandevuTarihi >= baslangic)
    if bitis:
        randevu_count_sq = randevu_count_sq.filter(Randevu.RandevuTarihi < (bitis + timedelta(days=1)))
    randevu_count_sq = randevu_count_sq.group_by(Randevu.MusteriID).subquery()

    top_q = (
        db.session.query(Musteri, randevu_count_sq.c.adet)
        .join(randevu_count_sq, randevu_count_sq.c.mid == Musteri.MusteriID)
        .filter(Musteri.FirmaID == firma_id)
    )
    if sadece_aktif == '1':
        top_q = top_q.filter(Musteri.Aktif == True)
    if kategori_id:
        top_q = top_q.filter(Musteri.KategoriID == kategori_id)
    top_musteriler = top_q.order_by(db.desc(randevu_count_sq.c.adet)).limit(10).all()

    # CSV dışa aktarım
    if format_tip == 'csv':
        output = BytesIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['MusteriID', 'Ad', 'Soyad', 'Telefon', 'Email', 'Aktif', 'Kategori', 'OlusturmaTarihi', 'RandevuSayisi'])
        for m in musteriler:
            randevu_adet = musteri_id_to_randevu_adet.get(m.MusteriID, 0)
            writer.writerow([
                m.MusteriID,
                m.MusteriAdi,
                m.MusteriSoyadi,
                m.Telefon or '',
                m.Email or '',
                'Evet' if m.Aktif else 'Hayır',
                m.kategori.KategoriAdi if m.kategori else '',
                (m.OlusturmaTarihi.strftime('%Y-%m-%d %H:%M') if m.OlusturmaTarihi else ''),
                randevu_adet
            ])
        output.seek(0)
        filename = f"musteri_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name=filename)

    # Kategoriler dropdown için
    kategoriler = MusteriKategori.query.filter_by(FirmaID=firma_id).order_by(MusteriKategori.KategoriAdi).all()

    # Görüntülenecek satırlar için zenginleştirme
    rows = []
    for m in musteriler:
        rows.append({
            'id': m.MusteriID,
            'ad': m.MusteriAdi,
            'soyad': m.MusteriSoyadi,
            'tam_ad': m.tam_adi,
            'telefon': m.Telefon,
            'email': m.Email,
            'aktif': m.Aktif,
            'kategori': m.kategori.KategoriAdi if m.kategori else None,
            'olusturma': m.OlusturmaTarihi,
            'randevu_sayisi': musteri_id_to_randevu_adet.get(m.MusteriID, 0)
        })

    return render_template(
        'rapor_musteriler.html',
        rows=rows,
        toplam_musteri=toplam_musteri,
        aktif_musteri=aktif_musteri,
        yeni_musteri=yeni_musteri,
        top_musteriler=top_musteriler,
        kategoriler=kategoriler,
        filtreler={
            'baslangic': tarih_baslangic_str or '',
            'bitis': tarih_bitis_str or '',
            'kategori_id': kategori_id or '',
            'aktif': sadece_aktif,
            'iletisim_var': iletisim_var or ''
        }
    )

@app.route('/randevu/<int:randevu_id>/duzenle', methods=['GET', 'POST'])
@login_required
def randevu_duzenle(randevu_id):
    """Randevu düzenleme sayfası"""
    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first_or_404()
    
    # Yetki kontrolü
    if not session.get('is_admin', False) and randevu.OlusturanKullaniciID != session['user_id']:
        flash('Bu randevuyu düzenleme yetkiniz yok', 'error')
        return redirect(url_for('randevular'))
    
    if request.method == 'POST':
        try:
            # Form verilerini al
            tarih_gun = request.form.get('tarih_gun')
            saat = request.form.get('saat')
            referans_id = request.form.get('referans_id', type=int)
            randevu_suresi = request.form.get('randevu_suresi', type=int)
            randevu_notlar = request.form.get('randevu_notlar', '').strip()
            
            if not tarih_gun or not saat or not randevu_suresi:
                flash('Lütfen tüm zorunlu alanları doldurun', 'error')
                return redirect(url_for('randevu_duzenle', randevu_id=randevu_id))
            
            # Tarih/saat birleştir
            try:
                randevu_dt = datetime.strptime(f"{tarih_gun} {saat}", '%Y-%m-%d %H:%M')
            except ValueError:
                flash('Tarih/saat formatı geçersiz', 'error')
                return redirect(url_for('randevu_duzenle', randevu_id=randevu_id))
            
            # Referans bilgisini güncelle
            ref = None
            if referans_id:
                ref = RandevuReferans.query.filter_by(ReferansID=referans_id, FirmaID=session['firma_id']).first()
            
            # Randevu bilgilerini güncelle
            randevu.RandevuTarihi = randevu_dt
            randevu.RandevuSuresi = randevu_suresi
            randevu.RandevuNotlar = randevu_notlar
            randevu.GuncellemeTarihi = datetime.utcnow()
            
            # Referans güncelle - başlık otomatik olarak referans adı olur
            if ref:
                randevu.RandevuBaslik = ref.Ad
            else:
                # Referans seçilmediyse mevcut başlığı koru
                pass
            
            # Müşteri bilgilerini güncelle (eğer müşteri varsa)
            if randevu.musteri:
                # Telefon numarasını ülke kodu ile birleştir
                telefon_ulke_kodu = request.form.get('telefon_ulke_kodu', '+90')
                telefon_numara = request.form.get('musteri_telefon', '').replace(' ', '')
                tam_telefon = f"{telefon_ulke_kodu}{telefon_numara}" if telefon_numara else ''
                
                musteri_email = request.form.get('musteri_email', '').strip()
                
                if tam_telefon:
                    randevu.musteri.Telefon = tam_telefon
                if musteri_email:
                    randevu.musteri.Email = musteri_email
                
                randevu.musteri.GuncellemeTarihi = datetime.utcnow()
            
            db.session.commit()
            flash('Randevu ve müşteri bilgileri başarıyla güncellendi', 'success')
            return redirect(url_for('randevu_detay', randevu_id=randevu_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Randevu güncellenirken hata: {str(e)}', 'error')
            return redirect(url_for('randevu_duzenle', randevu_id=randevu_id))
    
    # GET request - formu doldur
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuReferans.Ad).all()
    
    # Randevu defteri ayarlarını al (minimum süre için)
    defter_ayar = RandevuDefterAyar.query.filter_by(
        FirmaID=session['firma_id'], 
        Aktif=True
    ).first()
    
    # Minimum süre: defter ayarındaki slot dakikası, yoksa varsayılan 30 dakika
    min_sure = defter_ayar.SlotDakika if defter_ayar else 30
    
    return render_template('randevu_duzenle.html', 
                         randevu=randevu, 
                         referanslar=referanslar,
                         min_sure=min_sure)

@app.route('/randevu/ekle', methods=['GET', 'POST'])
@login_required
def randevu_ekle():
    if request.method == 'POST':
        # Form alanlarini guvenle al
        tarih_gun = request.form.get('tarih_gun')
        saat = request.form.get('saat')
        defter_id = request.form.get('defter_id', type=int)
        referans_id = request.form.get('referans_id', type=int)
        islem_id = request.form.get('islem_id', type=int)
        if not tarih_gun or not saat or not defter_id:
            flash('Lütfen tarih, saat ve randevu defteri seçin', 'error')
            return redirect(url_for('randevu_ekle'))
        # Referans istege bagli; yok ise "Yok" kullan
        try:
            randevu_dt = datetime.strptime(f"{tarih_gun} {saat}", '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Tarih/saat formatı geçersiz', 'error')
            return redirect(url_for('randevu_ekle'))

        # Geçmiş tarih/saat için koruma
        now_local = datetime.now()
        if randevu_dt < now_local:
            flash('Geçmiş tarihe veya saate randevu verilemez', 'error')
            return redirect(url_for('randevu_ekle'))

        # Seçilen defteri kontrol et
        defter_ayar = RandevuDefterAyar.query.filter_by(
            AyarID=defter_id, 
            FirmaID=session['firma_id'], 
            Aktif=True
        ).first()
        if not defter_ayar:
            flash('Seçilen randevu defteri bulunamadı', 'error')
            return redirect(url_for('randevu_ekle'))
        
        # Süre validation - slot dakikasının katı olmalı
        randevu_suresi = int(request.form.get('sure', 10))
        if randevu_suresi % defter_ayar.SlotDakika != 0:
            flash(f'Randevu süresi {defter_ayar.SlotDakika} dakikanın katları olmalı', 'error')
            return redirect(url_for('randevu_ekle'))

        # Çakışan randevu ve blok kontrolü
        randevu_bas = randevu_dt
        randevu_bit = randevu_dt + timedelta(minutes=randevu_suresi)

        # 1) Mevcut randevularla çakışma (Python tarafında kontrol)
        day_start_chk = datetime(randevu_dt.year, randevu_dt.month, randevu_dt.day, 0, 0)
        day_end_chk = day_start_chk + timedelta(days=1)
        existing_for_defter = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID == defter_id,
            Randevu.RandevuTarihi >= day_start_chk,
            Randevu.RandevuTarihi < day_end_chk
        ).all()
        for r in existing_for_defter:
            r_start = r.RandevuTarihi
            r_dur = r.RandevuSuresi or 60
            r_end = r_start + timedelta(minutes=int(r_dur))
            if r_start < randevu_bit and randevu_bas < r_end:
                flash('Seçilen saat aralığında mevcut randevu var', 'error')
                return redirect(url_for('randevu_ekle'))

        # 2) Bloklarla çakışma
        from sqlalchemy import or_
        gun = randevu_dt.date()
        bloklar = db.session.query(RandevuDefterBlok).filter(
            RandevuDefterBlok.FirmaID == session['firma_id'],
            RandevuDefterBlok.Aktif == True,
            RandevuDefterBlok.BaslangicTarih <= gun,
            or_(RandevuDefterBlok.BitisTarih == None, RandevuDefterBlok.BitisTarih >= gun),
            or_(RandevuDefterBlok.DefterID == None, RandevuDefterBlok.DefterID == defter_id)
        ).all()

        def is_blocked_interval(bas: datetime, bit: datetime) -> bool:
            for b in bloklar:
                # Saat verilmemişse tüm gün kapalı
                if not b.SaatBaslangic or not b.SaatBitis:
                    return True
                try:
                    bh, bm = map(int, b.SaatBaslangic.split(':'))
                    eh, em = map(int, b.SaatBitis.split(':'))
                except Exception:
                    continue
                b_bas = datetime(gun.year, gun.month, gun.day, bh, bm)
                b_bit = datetime(gun.year, gun.month, gun.day, eh, em)
                if b_bas < bit and bas < b_bit:
                    return True
            return False

        if is_blocked_interval(randevu_bas, randevu_bit):
            flash('Seçilen saat aralığı kapalı (bloklandı)', 'error')
            return redirect(url_for('randevu_ekle'))

        # Referans basligini cek (varsa)
        ref = None
        if referans_id:
            ref = RandevuReferans.query.filter_by(ReferansID=referans_id, FirmaID=session['firma_id']).first()

        # Müşteri işlemleri
        secilen_musteri_id = request.form.get('secilen_musteri_id')
        musteri_id = None
        
        if secilen_musteri_id:
            # Mevcut müşteri seçildi
            musteri_id = int(secilen_musteri_id)
            musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=session['firma_id']).first()
            if not musteri:
                flash('Seçilen müşteri bulunamadı', 'error')
                return redirect(url_for('randevu_ekle'))
        else:
            # Telefon numarasını ülke kodu ile birleştir
            telefon_ulke_kodu = request.form.get('telefon_ulke_kodu', '+90')
            telefon_numara = request.form.get('musteri_telefon', '').replace(' ', '')
            tam_telefon = f"{telefon_ulke_kodu}{telefon_numara}" if telefon_numara else ''
            
            # Yeni müşteri oluştur
            musteri = Musteri(
                FirmaID=session['firma_id'],
                MusteriAdi=request.form['musteri_adi'],
                MusteriSoyadi=request.form['musteri_soyadi'],
                Telefon=tam_telefon,
                Email=request.form.get('musteri_email', ''),
                # Yeni adres alanları
                Ulke=request.form.get('musteri_ulke', 'Türkiye'),
                Sehir=request.form.get('musteri_sehir', ''),
                Ilce=request.form.get('musteri_ilce', ''),
                Adres=request.form.get('musteri_adres', ''),
                Cinsiyet=request.form.get('musteri_cinsiyet', ''),
                KategoriID=request.form.get('musteri_kategori', type=int) or None,
                Notlar=request.form.get('musteri_notlar', '')
            )
            db.session.add(musteri)
            db.session.flush()  # ID'yi almak için
            musteri_id = musteri.MusteriID

        randevu = Randevu(
            RandevuBaslik=(ref.Ad if ref else 'Yok'),
            RandevuAciklamasi=request.form['aciklama'],
            RandevuTarihi=randevu_dt,
            RandevuSuresi=randevu_suresi,
            MusteriAdi=request.form['musteri_adi'],
            MusteriTelefon=request.form.get('musteri_telefon', ''),
            MusteriEmail=request.form.get('musteri_email', ''),
            MusteriID=musteri_id,  # Müşteri ID'sini ekle
            IslemID=islem_id,  # İşlem ID'sini ekle
            OlusturanKullaniciID=session['user_id'],
            FirmaID=session['firma_id'],
            DefterID=defter_id  # Defter ID'sini ekle
        )
        
        db.session.add(randevu)
        db.session.commit()

        # Varsayilan: 60 ve 10 dk once hatirlatma (email varsa)
        try:
            if randevu.MusteriEmail:
                for before in [60, 10]:
                    h = RandevuHatirlatma(
                        RandevuID=randevu.RandevuID,
                        FirmaID=session['firma_id'],
                        RecipientEmail=randevu.MusteriEmail,
                        MinutesBefore=before
                    )
                    db.session.add(h)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Hatirlatma kaydi olusurken hata: {e}")

        # Bildirim: randevu olusturuldu (olusturana ve varsa yetkili kullanicilara)
        try:
            b = Bildirim(
                KullaniciID=session['user_id'],
                FirmaID=session['firma_id'],
                Metin=f"{randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M')} için randevu oluşturuldu",
                Tip='randevu',
                IlgiliRandevuID=randevu.RandevuID
            )
            db.session.add(b)
            db.session.commit()
        except Exception:
            db.session.rollback()
        
        # Olusturan kullaniciya tam yetki ver
        if _assert_same_firm_for_permission(session['user_id'], randevu.RandevuID):
            randevu_yetki = RandevuYetki(
                RandevuID=randevu.RandevuID,
                KullaniciID=session['user_id'],
                GoruntulemeYetkisi=True,
                DuzenlemeYetkisi=True,
                SilmeYetkisi=True
            )
            db.session.add(randevu_yetki)
            db.session.commit()
        else:
            flash('Farklı firmaya yetki verilemez', 'error')
        
        # Randevu oluşturulduğunda müşteriye e-posta gönder (e-posta varsa)
        if randevu.MusteriEmail:
            subject = f"Randevu Onayı - {randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M')}"
            body = (
                f"Merhaba {randevu.MusteriAdi or 'Değerli Müşterimiz'},\n\n"
                f"{randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M')} tarihinde randevunuz başarıyla oluşturulmuştur.\n"
                f"Referans: {randevu.RandevuBaslik}\n"
                f"Süre: {randevu.RandevuSuresi or 60} dakika\n\n"
                f"Randevu detayları için bizimle iletişime geçebilirsiniz.\n\n"
                f"İyi günler dileriz."
            )
            # Firma ayarlarını kullan, yoksa genel ayarları kullan
            email_sent = send_email_with_firma_settings(randevu.FirmaID, randevu.MusteriEmail, subject, body)
            if not email_sent:
                send_email_simple(randevu.MusteriEmail, subject, body)
        
        flash('Randevu başarıyla oluşturuldu!', 'success')
        return redirect(url_for('randevular'))
    # GET isteği
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuReferans.Ad).all()
    
    # Müşterileri al
    musteriler = Musteri.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(Musteri.MusteriAdi, Musteri.MusteriSoyadi).all()
    
    # Müşteri kategorilerini al
    musteri_kategoriler = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id']
    ).filter(MusteriKategori.Aktif == 1).all()
    
    # Randevu defteri ayarlarını al (tüm aktif defterler)
    defter_ayarlar = RandevuDefterAyar.query.filter_by(
        FirmaID=session['firma_id'], 
        Aktif=True
    ).order_by(RandevuDefterAyar.DefterAdi).all()
    
    
    # Eğer defter yoksa varsayılan defter oluştur
    if not defter_ayarlar:
        print(f"Firma {session['firma_id']} için defter bulunamadı, varsayılan defter oluşturuluyor...")
        varsayilan_defter = RandevuDefterAyar(
            FirmaID=session['firma_id'],
            DefterAdi='Varsayılan Defter',
            CalismaGunleri='1,2,3,4,5',
            BaslangicSaati='09:00',
            BitisSaati='18:00',
            SlotDakika=30,
            Aktif=True
        )
        db.session.add(varsayilan_defter)
        db.session.commit()
        defter_ayarlar = [varsayilan_defter]
    else:
        varsayilan_defter = defter_ayarlar[0]
    
    min_sure = varsayilan_defter.SlotDakika
    
    # İşlemler listesini al (varsayılan deftere göre filtrele, sonra JS değiştikçe AJAX ile alınabilir)
    islemler = RandevuIslem.query.filter_by(
        FirmaID=session.get('firma_id'), 
        Aktif=True
    ).filter(
        (RandevuIslem.DefterID == varsayilan_defter.AyarID) | (RandevuIslem.DefterID.is_(None))
    ).order_by(RandevuIslem.IslemAdi).all()
    
    # Ülkeleri getir
    countries = get_countries()
    
    return render_template('randevu_ekle.html', 
                         referanslar=referanslar,
                         islemler=islemler,
                         musteriler=musteriler,
                         musteri_kategoriler=musteri_kategoriler,
                         defter_ayarlar=defter_ayarlar,
                         varsayilan_defter=varsayilan_defter,
                         min_sure=min_sure,
                         countries=countries)

@app.route('/api/islemler')
@login_required
def api_islemler():
    firma_id = session.get('firma_id')
    defter_id = request.args.get('defter_id', type=int)
    q = RandevuIslem.query.filter_by(FirmaID=firma_id, Aktif=True)
    if defter_id:
        q = q.filter((RandevuIslem.DefterID == defter_id) | (RandevuIslem.DefterID.is_(None)))
    items = q.order_by(RandevuIslem.IslemAdi).all()
    return jsonify([
        {
            'IslemID': i.IslemID,
            'IslemAdi': i.IslemAdi
        } for i in items
    ])

@app.route('/randevu/<int:randevu_id>')
@login_required
def randevu_detay(randevu_id):
    # Yetki kontrolu
    if session.get('is_admin', False):
        randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
    else:
        randevu = db.session.query(Randevu).join(RandevuYetki).filter(
            Randevu.RandevuID == randevu_id,
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id']
        ).first()
    
    if not randevu:
        flash('Randevu bulunamadı veya erişim yetkiniz yok!', 'error')
        return redirect(url_for('randevular'))
    
    return render_template('randevu_detay.html', randevu=randevu)

@app.route('/randevu/sil/<int:randevu_id>', methods=['POST'])
@login_required
def randevu_sil(randevu_id):
    # Randevuyu ve erisim yetkisini kontrol et
    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
    if not randevu:
        flash('Randevu bulunamadı veya erişim yetkiniz yok', 'error')
        return redirect(url_for('randevular'))

    is_admin = session.get('is_admin', False)
    has_delete_perm = db.session.query(RandevuYetki).filter_by(
        RandevuID=randevu_id,
        KullaniciID=session['user_id'],
        SilmeYetkisi=True
    ).first() is not None

    if not (is_admin or randevu.OlusturanKullaniciID == session['user_id'] or has_delete_perm):
        flash('Silme yetkiniz yok', 'error')
        return redirect(url_for('randevular'))

    try:
        # Cascade delete ile tüm ilgili kayıtlar otomatik silinir
        db.session.delete(randevu)
        db.session.commit()
        flash('Randevu silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Randevu silinirken hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('randevular'))

@app.route('/randevu/durum/<int:randevu_id>', methods=['POST'])
@login_required
def randevu_durum(randevu_id):
    yeni_durum = request.form.get('durum')
    if yeni_durum not in ['Beklemede', 'Onaylandi', 'Iptal', 'Tamamlandi']:
        flash('Geçersiz durum', 'error')
        return redirect(url_for('randevular'))

    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
    if not randevu:
        flash('Randevu bulunamadı veya erişim yetkiniz yok', 'error')
        return redirect(url_for('randevular'))

    is_admin = session.get('is_admin', False)
    has_edit_perm = db.session.query(RandevuYetki).filter_by(
        RandevuID=randevu_id,
        KullaniciID=session['user_id'],
        DuzenlemeYetkisi=True
    ).first() is not None

    if not (is_admin or randevu.OlusturanKullaniciID == session['user_id'] or has_edit_perm):
        flash('Durum güncelleme yetkiniz yok', 'error')
        return redirect(url_for('randevular'))

    randevu.Durum = yeni_durum
    db.session.commit()
    flash('Randevu durumu güncellendi', 'success')
    return redirect(url_for('randevular'))

# Takvim Görünümü
@app.route('/takvim')
@login_required
def takvim():
    # Ay ve yıl parametreleri
    year = request.args.get('year', type=int) or datetime.now().year
    month = request.args.get('month', type=int) or datetime.now().month
    view_type = request.args.get('view', 'month')  # month, week
    
    # Tarih aralığı hesapla
    if view_type == 'month':
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
    else:  # week
        # Haftanın başlangıcını bul (Pazartesi)
        today = datetime.now()
        days_since_monday = today.weekday()
        start_date = today - timedelta(days=days_since_monday)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)
    
    # Randevuları getir
    if session.get('is_admin', False):
        randevular = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_date,
            Randevu.RandevuTarihi < end_date
        ).order_by(Randevu.RandevuTarihi).all()
    else:
        randevular = db.session.query(Randevu).join(RandevuYetki).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_date,
            Randevu.RandevuTarihi < end_date
        ).order_by(Randevu.RandevuTarihi).all()
    
    return render_template('takvim.html', 
                         randevular=randevular, 
                         year=year, 
                         month=month, 
                         view_type=view_type,
                         start_date=start_date,
                         end_date=end_date,
                         datetime=datetime,
                         timedelta=timedelta)

# API: Randevu taşıma (drag & drop)
@app.route('/api/randevu/tasi', methods=['POST'])
@login_required
def api_randevu_tasi():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "JSON verisi bulunamadı"}), 400
            
        randevu_id = data.get('randevu_id')
        yeni_tarih = data.get('yeni_tarih')  # YYYY-MM-DD HH:MM format
        
        print(f"API çağrısı - Randevu ID: {randevu_id}, Yeni Tarih: {yeni_tarih}")
        
        if not randevu_id or not yeni_tarih:
            return jsonify({"success": False, "message": "Eksik parametre"}), 400
        
        try:
            yeni_dt = datetime.strptime(yeni_tarih, '%Y-%m-%d %H:%M')
        except ValueError as e:
            print(f"Tarih parse hatası: {e}")
            return jsonify({"success": False, "message": "Geçersiz tarih formatı"}), 400
    except Exception as e:
        print(f"Genel hata: {e}")
        return jsonify({"success": False, "message": "Sunucu hatası"}), 500
    
    # Randevuyu bul ve yetki kontrolü
    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
    if not randevu:
        return jsonify({"success": False, "message": "Randevu bulunamadı"}), 404
    
    is_admin = session.get('is_admin', False)
    has_edit_perm = db.session.query(RandevuYetki).filter_by(
        RandevuID=randevu_id,
        KullaniciID=session['user_id'],
        DuzenlemeYetkisi=True
    ).first() is not None
    
    if not (is_admin or randevu.OlusturanKullaniciID == session['user_id'] or has_edit_perm):
        return jsonify({"success": False, "message": "Yetkiniz yok"}), 403
    
    # Çakışma kontrolü
    randevu_suresi = randevu.RandevuSuresi or 60
    bitis_tarihi = yeni_dt + timedelta(minutes=randevu_suresi)
    
    # Mevcut randevuları kontrol et
    mevcut_randevular = Randevu.query.filter(
        Randevu.FirmaID == session['firma_id'],
        Randevu.RandevuID != randevu_id
    ).all()
    
    cakisan = None
    for mevcut in mevcut_randevular:
        mevcut_suresi = mevcut.RandevuSuresi or 60
        mevcut_bitis = mevcut.RandevuTarihi + timedelta(minutes=mevcut_suresi)
        
        # Çakışma kontrolü: yeni randevu mevcut randevu ile çakışıyor mu?
        if (yeni_dt < mevcut_bitis and bitis_tarihi > mevcut.RandevuTarihi):
            cakisan = mevcut
            break
    
    if cakisan:
        return jsonify({"success": False, "message": "Bu saatte başka randevu var"}), 400
    
    # Tarihi güncelle
    try:
        eski_tarih = randevu.RandevuTarihi
        randevu.RandevuTarihi = yeni_dt
        db.session.commit()
        print(f"Randevu {randevu_id} başarıyla taşındı")

        # Bildirim: randevu taşındı (olusturana bildirim)
        try:
            b = Bildirim(
                KullaniciID=randevu.OlusturanKullaniciID,
                FirmaID=session['firma_id'],
                Metin=f"Randevu {eski_tarih.strftime('%d.%m.%Y %H:%M')} -> {yeni_dt.strftime('%d.%m.%Y %H:%M')} taşındı",
                Tip='randevu',
                IlgiliRandevuID=randevu.RandevuID
            )
            db.session.add(b)
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Randevu taşındığında müşteriye e-posta gönder (e-posta varsa)
        if randevu.MusteriEmail:
            subject = f"Randevu Tarihi Değişikliği - {yeni_dt.strftime('%d.%m.%Y %H:%M')}"
            body = (
                f"Merhaba {randevu.MusteriAdi or 'Değerli Müşterimiz'},\n\n"
                f"Randevu tarihiniz değiştirilmiştir:\n"
                f"Eski Tarih: {eski_tarih.strftime('%d.%m.%Y %H:%M')}\n"
                f"Yeni Tarih: {yeni_dt.strftime('%d.%m.%Y %H:%M')}\n"
                f"Referans: {randevu.RandevuBaslik}\n"
                f"Süre: {randevu.RandevuSuresi or 60} dakika\n\n"
                f"Bu değişiklik hakkında sorularınız için bizimle iletişime geçebilirsiniz.\n\n"
                f"İyi günler dileriz."
            )
            # Firma ayarlarını kullan, yoksa genel ayarları kullan
            email_sent = send_email_with_firma_settings(randevu.FirmaID, randevu.MusteriEmail, subject, body)
            if not email_sent:
                send_email_simple(randevu.MusteriEmail, subject, body)

        return jsonify({"success": True, "message": "Randevu taşındı"})
    except Exception as e:
        db.session.rollback()
        print(f"Veritabanı hatası: {e}")
        return jsonify({"success": False, "message": "Veritabanı hatası"}), 500

# API: Secilebilir saat slotlari
@app.route('/api/slots')
@login_required
def api_slots():
    # Inputs
    date_str = request.args.get('date')  # YYYY-MM-DD
    defter_id = request.args.get('defter_id', type=int)
    include_unavailable = request.args.get('all', '0') == '1'
    if not date_str:
        return jsonify({"success": False, "message": "date parametresi zorunlu"}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"success": False, "message": "date formatı YYYY-MM-DD olmalı"}), 400

    # Firma ayarlari
    firma_id = session['firma_id']
    
    # Eğer defter_id verilmişse, o defteri kullan
    if defter_id:
        ayar = RandevuDefterAyar.query.filter_by(
            AyarID=defter_id, 
            FirmaID=firma_id, 
            Aktif=True
        ).first()
        if not ayar:
            return jsonify({"success": False, "message": "Belirtilen defter bulunamadı"}), 400
    else:
        # Varsayılan olarak ilk aktif defteri kullan
        ayar = RandevuDefterAyar.query.filter_by(FirmaID=firma_id, Aktif=True).order_by(RandevuDefterAyar.AyarID.desc()).first()
    
    if not ayar:
        # Varsayilan
        calisma_gunleri = {'1','2','3','4','5'}
        baslangic = '09:00'
        bitis = '18:00'
        slot_dk = 30
    else:
        calisma_gunleri = set((ayar.CalismaGunleri or '1,2,3,4,5').split(','))
        baslangic = ayar.BaslangicSaati or '09:00'
        bitis = ayar.BitisSaati or '18:00'
        slot_dk = ayar.SlotDakika or 30

    # Gun uygun mu?
    # Python weekday(): Monday=0..Sunday=6 -> our mapping 1..7
    weekday_num = (target_date.weekday() + 1)  # 1..7
    if str(weekday_num) not in calisma_gunleri:
        return jsonify({"success": True, "slots": []})

    # Saat araligi
    def parse_hhmm(s):
        h, m = s.split(':')
        return int(h), int(m)
    sh, sm = parse_hhmm(baslangic)
    eh, em = parse_hhmm(bitis)
    start_dt = datetime(target_date.year, target_date.month, target_date.day, sh, sm)
    end_dt = datetime(target_date.year, target_date.month, target_date.day, eh, em)

    # Bloklar (kapatilan araliklar)
    from sqlalchemy import or_, and_
    bloklar = db.session.query(RandevuDefterBlok).filter(
        RandevuDefterBlok.FirmaID == firma_id,
        RandevuDefterBlok.Aktif == True,
        # Tarih araligi kapsama
        or_(
            RandevuDefterBlok.BitisTarih == None,
            RandevuDefterBlok.BitisTarih >= target_date
        ),
        RandevuDefterBlok.BaslangicTarih <= target_date,
        # Defter filtresi: None tüm defterler veya seçili defter
        or_(
            RandevuDefterBlok.DefterID == None,
            RandevuDefterBlok.DefterID == (ayar.AyarID if ayar else None)
        )
    ).all()

    def is_blocked(slot_start: datetime, slot_end: datetime) -> bool:
        if not bloklar:
            return False
        for b in bloklar:
            # Saat belirtilmemişse tüm gün bloklu kabul et
            if not b.SaatBaslangic or not b.SaatBitis:
                return True
            try:
                bh, bm = map(int, b.SaatBaslangic.split(':'))
                ehh, emm = map(int, b.SaatBitis.split(':'))
            except Exception:
                continue
            b_start = datetime(target_date.year, target_date.month, target_date.day, bh, bm)
            b_end = datetime(target_date.year, target_date.month, target_date.day, ehh, emm)
            if b_start < slot_end and slot_start < b_end:
                return True
        return False

    # O gun var olan randevular (firma icinde)
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0)
    day_end = day_start + timedelta(days=1)
    existing = Randevu.query.filter(
        Randevu.FirmaID == firma_id,
        Randevu.RandevuTarihi >= day_start,
        Randevu.RandevuTarihi < day_end
    ).all()

    def is_overlapping(slot_start: datetime, slot_end: datetime) -> bool:
        for r in existing:
            r_start = r.RandevuTarihi
            r_end = r_start + timedelta(minutes=(r.RandevuSuresi or 60))
            if r_start < slot_end and slot_start < r_end:
                return True
        return False

    # Slotlari olustur
    slots = []
    cur = start_dt
    while cur + timedelta(minutes=slot_dk) <= end_dt:
        slot_end = cur + timedelta(minutes=slot_dk)
        taken = is_overlapping(cur, slot_end)
        blocked = is_blocked(cur, slot_end)
        slot_label = cur.strftime('%H:%M')
        if include_unavailable or (not taken and not blocked):
            slots.append({"time": slot_label, "available": (not taken and not blocked)})
        cur += timedelta(minutes=slot_dk)

    return jsonify({"success": True, "slots": slots})

# JSON API: Defter blokları (listele/ekle/sil) - randevu ekranından inline yönetim için
@app.route('/api/defter_bloklar', methods=['GET'])
@login_required
def api_defter_bloklar_liste():
    firma_id = session['firma_id']
    defter_id = request.args.get('defter_id', type=int)
    q = RandevuDefterBlok.query.filter_by(FirmaID=firma_id).order_by(RandevuDefterBlok.BlokID.desc())
    if defter_id:
        q = q.filter((RandevuDefterBlok.DefterID == defter_id) | (RandevuDefterBlok.DefterID.is_(None)))
    items = []
    for b in q.all():
        items.append({
            'BlokID': b.BlokID,
            'DefterID': b.DefterID,
            'DefterAdi': b.defter.DefterAdi if b.defter else 'Tümü',
            'BaslangicTarih': b.BaslangicTarih.strftime('%Y-%m-%d') if b.BaslangicTarih else None,
            'BitisTarih': b.BitisTarih.strftime('%Y-%m-%d') if b.BitisTarih else None,
            'SaatBaslangic': b.SaatBaslangic,
            'SaatBitis': b.SaatBitis,
            'Aciklama': b.Aciklama,
            'Aktif': b.Aktif,
        })
    return jsonify({'success': True, 'items': items})

@app.route('/api/defter_bloklar', methods=['POST'])
@login_required
def api_defter_blok_ekle():
    firma_id = session['firma_id']
    payload = request.get_json(silent=True) or {}
    defter_id = payload.get('defter_id')
    tarih1 = payload.get('tarih1')
    tarih2 = payload.get('tarih2')
    saat1 = payload.get('saat1')
    saat2 = payload.get('saat2')
    aciklama = payload.get('aciklama') or ''
    try:
        bas_t = datetime.strptime(tarih1, '%Y-%m-%d').date() if tarih1 else None
        bit_t = datetime.strptime(tarih2, '%Y-%m-%d').date() if tarih2 else None
    except Exception:
        return jsonify({'success': False, 'message': 'Geçersiz tarih formatı'}), 400
    if not bas_t:
        return jsonify({'success': False, 'message': 'Başlangıç tarihi zorunlu'}), 400
    if bit_t and bit_t < bas_t:
        return jsonify({'success': False, 'message': 'Bitiş tarihi başlangıçtan önce olamaz'}), 400

    blok = RandevuDefterBlok(
        FirmaID=firma_id,
        DefterID=int(defter_id) if defter_id else None,
        BaslangicTarih=bas_t,
        BitisTarih=bit_t,
        SaatBaslangic=saat1 or None,
        SaatBitis=saat2 or None,
        Aciklama=aciklama,
        Aktif=True
    )
    db.session.add(blok)
    db.session.commit()
    return jsonify({'success': True, 'id': blok.BlokID})

@app.route('/api/defter_bloklar/<int:blok_id>', methods=['DELETE'])
@login_required
def api_defter_blok_sil(blok_id: int):
    b = RandevuDefterBlok.query.filter_by(BlokID=blok_id, FirmaID=session['firma_id']).first()
    if not b:
        return jsonify({'success': False, 'message': 'Blok bulunamadı'}), 404
    db.session.delete(b)
    db.session.commit()
    return jsonify({'success': True})

# Raporlar Sayfasi
@app.route('/raporlar')
@login_required
def raporlar():
    # Modül izin kontrolü
    if not session.get('raporlar_modulu', False):
        flash('Bu sayfaya erişim yetkiniz yok', 'error')
        return redirect(url_for('dashboard'))
    # Varsayilan tarih araligi: son 30 gun
    end_str = request.args.get('bitis')
    start_str = request.args.get('baslangic')
    today = datetime.now().date()
    default_start = today - timedelta(days=30)
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else default_start
    except ValueError:
        start_date = default_start
    try:
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else today
    except ValueError:
        end_date = today

    return render_template('raporlar.html', baslangic=start_date.strftime('%Y-%m-%d'), bitis=end_date.strftime('%Y-%m-%d'))

# Raporlar API - Ozet
@app.route('/api/raporlar/ozet')
@login_required
def api_raporlar_ozet():
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    try:
        start_date = datetime.strptime(baslangic, '%Y-%m-%d').date() if baslangic else (datetime.now().date() - timedelta(days=30))
        end_date = datetime.strptime(bitis, '%Y-%m-%d').date() if bitis else datetime.now().date()
    except ValueError:
        return jsonify({"success": False, "message": "Tarih formatı YYYY-MM-DD olmalı"}), 400

    # Tarihleri kapsayan datetime araligi
    start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    # Izin farkindaligi
    if session.get('is_admin', False):
        q = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_dt,
            Randevu.RandevuTarihi <= end_dt
        )
    else:
        q = db.session.query(Randevu).join(RandevuYetki).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_dt,
            Randevu.RandevuTarihi <= end_dt
        )

    items = q.all()

    toplam = len(items)
    durum_counter = Counter(r.Durum or 'Bilinmiyor' for r in items)
    ref_counter = Counter(r.RandevuBaslik or 'Yok' for r in items)

    saat_counter = defaultdict(int)
    for r in items:
        saat_counter[r.RandevuTarihi.hour] += 1
    saatler = list(range(0,24))
    saat_deger = [saat_counter.get(h, 0) for h in saatler]

    return jsonify({
        "success": True,
        "toplam": toplam,
        "durumlar": durum_counter,
        "referanslar": ref_counter,
        "saatler": {"labels": saatler, "values": saat_deger}
    })

@app.route('/api/musteri/ara')
@login_required
def api_musteri_ara():
    """Müşteri arama API endpoint'i"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:  # En az 2 karakter gerekli
        return jsonify([])
    
    # Mevcut firmanın müşterilerini ara
    musteriler = Musteri.query.filter(
        Musteri.FirmaID == session['firma_id'],
        Musteri.Aktif == True,
        db.or_(
            Musteri.MusteriAdi.ilike(f'%{query}%'),
            Musteri.MusteriSoyadi.ilike(f'%{query}%'),
            db.func.concat(Musteri.MusteriAdi, ' ', Musteri.MusteriSoyadi).ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    sonuc = []
    for musteri in musteriler:
        sonuc.append({
            'id': musteri.MusteriID,
            'adi': musteri.MusteriAdi,
            'soyadi': musteri.MusteriSoyadi,
            'tam_adi': musteri.tam_adi,
            'telefon': musteri.Telefon or '',
            'email': musteri.Email or '',
            'kategori': musteri.kategori.KategoriAdi if musteri.kategori else 'Kategori Yok',
            'kategori_id': musteri.kategori.KategoriID if musteri.kategori else None,
            'kategori_rengi': musteri.kategori.Renk if musteri.kategori else '#6c757d'
        })
    
    return jsonify(sonuc)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Hatirlatma worker'i arka planda baslat
    worker_thread = threading.Thread(target=reminder_worker, daemon=True)
    worker_thread.start()
    app.run(debug=True, host='0.0.0.0', port=5000)
