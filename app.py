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
from io import BytesIO, StringIO
import csv
from sqlalchemy import or_
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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

# Parola karmaşıklık kontrolü
import re
def is_password_strong(password: str) -> bool:
    if not password or len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True

@app.before_request
def enforce_password_change():
    # Zorunlu parola değişimi: giriş yapılmışsa ve bayrak açıksa, sadece izinli endpointlere erişsin
    if 'user_id' in session and session.get('must_change_password'):
        allowed = set(['sifre_degistir', 'logout', 'set_language', 'static'])
        if request.endpoint not in allowed:
            return redirect(url_for('sifre_degistir'))

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


class AktifOturum(db.Model):
    __tablename__ = 'AktifOturumlar'

    AktifOturumID = db.Column(db.Integer, primary_key=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'), nullable=False, unique=True)
    SessionToken = db.Column(db.String(64), nullable=False)
    GirisZamani = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    SonGorulmeZamani = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    ClientIP = db.Column(db.String(64))
    UserAgent = db.Column(db.String(255))

    kullanici = db.relationship('Kullanici', backref='aktif_oturum', uselist=False)

    def __repr__(self):
        return f'<AktifOturum {self.KullaniciID}>'

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
    MusteriSoyadi = db.Column(db.NVARCHAR(100))
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

# Randevu SMS Hatirlatma
class RandevuSMSHatirlatma(db.Model):
    __tablename__ = 'RandevuSMSHatirlatmalar'

    HatirlatmaID = db.Column(db.Integer, primary_key=True)
    RandevuID = db.Column(db.Integer, db.ForeignKey('Randevular.RandevuID'), nullable=False)
    FirmaID = db.Column(db.Integer, db.ForeignKey('Firmalar.FirmaID'), nullable=False)
    RecipientPhone = db.Column(db.NVARCHAR(20))
    MinutesBefore = db.Column(db.Integer, default=1440)
    Gonderildi = db.Column(db.Boolean, default=False)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
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
    VarsayilanEmailMetni = db.Column(db.NVARCHAR(max))
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
    # Varsayılan SMS metni
    VarsayilanSMSMetni = db.Column(db.NVARCHAR(1000))
    # Zamanlama seçenekleri
    SMSGonderOnCreate = db.Column(db.Boolean, default=False)
    SMSGonder24SaatOnce = db.Column(db.Boolean, default=False)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    # Varsayılan mesaj şablonları
    RandevuOlusturmaMesaji = db.Column(db.Text, nullable=True)
    RandevuHatirlatmaMesaji = db.Column(db.Text, nullable=True)
    RandevuIptalMesaji = db.Column(db.Text, nullable=True)
    # Zamanlama seçenekleri
    MesajGonderOnCreate = db.Column(db.Boolean, default=False)
    MesajGonder24SaatOnce = db.Column(db.Boolean, default=False)
    MesajGonder1SaatOnce = db.Column(db.Boolean, default=False)
    Aktif = db.Column(db.Boolean, default=True)
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    GuncellemeTarihi = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    firma = db.relationship('Firma', backref='whatsapp_ayarlar')
    
    def __repr__(self):
        return f'<FirmaWhatsAppAyar {self.WhatsAppAyarID} firma={self.FirmaID}>'

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
    Yas = db.Column(db.Integer)  # Yaş alanı
    Cinsiyet = db.Column(db.NVARCHAR(10))  # 'Erkek', 'Kadın'
    KategoriID = db.Column(db.Integer, db.ForeignKey('MusteriKategorileri.KategoriID'))
    Notlar = db.Column(db.NVARCHAR(1000))
    ProfilFotografi = db.Column(db.NVARCHAR(500))
    Aktif = db.Column(db.Boolean, default=True)
    OlusturanKullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.KullaniciID'))
    OlusturmaTarihi = db.Column(db.DateTime, default=datetime.utcnow)
    GuncellemeTarihi = db.Column(db.DateTime, default=datetime.utcnow)

    firma = db.relationship('Firma', backref='musteriler')
    kategori = db.relationship('MusteriKategori', backref='musteriler')
    olusturan_kullanici = db.relationship('Kullanici', backref='olusturulan_musteriler', foreign_keys=[OlusturanKullaniciID])

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
        
        # Telefon numarası normalizasyonu: çoğu sağlayıcı için 90XXXXXXXXXX
        # Corvass için esnek format gerekir; orijinali ayrıca iletelim
        original_phone_input = phone_number
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
        elif sms_ayar.SMSFirmasi == 'corvass':
            return send_sms_corvass(sms_ayar, original_phone_input, message)
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

def send_sms_corvass(sms_ayar, phone_number: str, message: str) -> bool:
    """Corvass API ile SMS gönder

    Not: API entegrasyonu sağlayıcı dökümantasyonuna göre değişebilir. Burada
    genel bir REST POST akışı uygulanmıştır. `API_URL` tanımlıysa o kullanılır,
    yoksa varsayılan bir uç noktaya istek gönderilir.
    """
    try:
        import requests

        api_url = (sms_ayar.API_URL or '').strip() or 'https://api.corvass.com/sms/send'

        # Corvass beklenen şema
        payload = {
            'Authentication': {
                'apikey': sms_ayar.API_Key or '',
                'apisecret': sms_ayar.API_Secret or ''
            },
            'message': message,
            'msisdnArray': [phone_number],
            'originator': sms_ayar.GondericiAdi or 'Corvass.NET',
            # İsteğe bağlı alanlar: gönderilmemişse sağlayıcı defaults kullanır
            # 'senddate': 'YYYY-MM-DD HH:mm:ss',
            # 'tags': [],
            # 'description': '',
            # 'messageType': 'B',
            # 'recipientType': 'TACIR'
        }

        headers = { 'Content-Type': 'application/json' }

        response = requests.post(api_url, json=payload, headers=headers, timeout=30)

        # Yanıtı ayrıntılı logla
        try:
            resp_json = response.json()
        except Exception:
            resp_json = {'raw': response.text}

        if 200 <= response.status_code < 300:
            # Corvass tarafı 200 içinde de hata kodu döndürebilir
            status_val = str(resp_json.get('status') or resp_json.get('result') or '').lower()
            success = 'success' in status_val or resp_json.get('success') is True
            if success:
                print(f"Corvass SMS OK: tel={phone_number} resp={resp_json}")
                return True
            else:
                print(f"Corvass SMS 200 ama başarısız: resp={resp_json}")
                return False
        else:
            print(f"Corvass SMS HTTP hata: {response.status_code} resp={resp_json}")
            return False

    except Exception as e:
        print(f"Corvass SMS gönderim hatası: {e}")
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

                # SMS hatirlatmalarini da kontrol et
                pending_sms = db.session.query(RandevuSMSHatirlatma).join(Randevu).filter(
                    RandevuSMSHatirlatma.Gonderildi == False,
                    RandevuSMSHatirlatma.RecipientPhone != None,
                    RandevuSMSHatirlatma.RecipientPhone != '',
                    Randevu.RandevuTarihi >= now,
                    Randevu.RandevuTarihi <= future_limit
                ).all()

                # Eğer gönderilecek hiçbir hatırlatma yoksa, bekle
                if not pending and not pending_sms:
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

                # SMS hatirlatmalarini isleme
                for s in pending_sms:
                    r = s.randevu
                    if not r:
                        continue
                    target_send_time = r.RandevuTarihi - timedelta(minutes=s.MinutesBefore)
                    if target_send_time <= now and not s.Gonderildi:
                        # Firma SMS ayar metnini kullan
                        sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=s.FirmaID, Aktif=True).first()
                        sms_text = (sms_ayar.VarsayilanSMSMetni if sms_ayar and sms_ayar.VarsayilanSMSMetni else
                                    "Merhaba {MUSTERI_ADI}, {RANDEVU_TARIH} tarihindeki randevunuzu hatırlatırız.")
                        try:
                            defter_adi = r.defter.DefterAdi if r.defter else ''
                        except Exception:
                            defter_adi = ''
                        # Ad + Soyad birlestir
                        try:
                            if r.musteri and r.musteri.MusteriSoyadi:
                                full_name = f"{r.musteri.MusteriAdi} {r.musteri.MusteriSoyadi}".strip()
                            else:
                                full_name = (r.MusteriAdi or '').strip()
                        except Exception:
                            full_name = (r.MusteriAdi or '').strip()

                        sms_text = sms_text.replace('{MUSTERI_ADI}', full_name or '-')\
                                           .replace('{RANDEVU_TARIH}', r.RandevuTarihi.strftime('%d.%m.%Y %H:%M'))\
                                           .replace('{DEFTER_ADI}', defter_adi)

                        ok = send_sms_with_firma_settings(s.FirmaID, s.RecipientPhone, sms_text)
                        if ok:
                            s.Gonderildi = True
                            s.GonderimTarihi = datetime.utcnow()
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
    # Only return unread notifications
    unread_q = Bildirim.query.filter_by(KullaniciID=session['user_id'], Okundu=False)
    unread = unread_q.count()
    items = unread_q.order_by(Bildirim.OlusturmaTarihi.desc()).limit(50).all()

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

@app.route('/api/clear-session', methods=['POST'])
def api_clear_session():
    """Tarayıcı kapanma durumunda oturumu temizle"""
    try:
        if 'user_id' in session:
            user_id = session.get('user_id')
            token = session.get('session_token')
            kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
            if kayit and (not token or kayit.SessionToken == token):
                db.session.delete(kayit)
                db.session.commit()
    except Exception:
        db.session.rollback()
    return '', 204  # No content response

@app.route('/api/update-last-seen', methods=['POST'])
def api_update_last_seen():
    """Son görülme zamanını güncelle"""
    try:
        if 'user_id' in session:
            user_id = session.get('user_id')
            token = session.get('session_token')
            kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
            if kayit and (not token or kayit.SessionToken == token):
                kayit.SonGorulmeZamani = datetime.utcnow()
                db.session.commit()
    except Exception:
        db.session.rollback()
    return '', 204  # No content response

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
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Kullanici kontrolu
        user = Kullanici.query.filter_by(KullaniciAdi=username, Aktif=True).first()
        
        if user and user.Sifre == password:  # Geçici olarak düz metin karşılaştırma
            # Eski oturumları temizle (24 saatten eski)
            eski_oturumlar = AktifOturum.query.filter(
                AktifOturum.SonGorulmeZamani < datetime.utcnow() - timedelta(hours=24)
            ).all()
            for oturum in eski_oturumlar:
                db.session.delete(oturum)
            db.session.commit()
            
            # Tek-oturum kontrolü
            mevcut = AktifOturum.query.filter_by(KullaniciID=user.KullaniciID).first()
            if mevcut:
                # Mevcut oturum varsa, kullanıcıya seçenek sun
                session['pending_user_id'] = user.KullaniciID
                session['pending_username'] = user.KullaniciAdi
                session['pending_user_name'] = f"{user.Ad} {user.Soyad}"
                session['pending_firma_id'] = user.FirmaID
                session['pending_is_admin'] = user.Admin
                session['pending_raporlar_modulu'] = user.RaporlarModulu
                session['pending_ayarlar_modulu'] = user.AyarlarModulu
                
                # Firma bilgisini al
                firma = Firma.query.filter_by(FirmaID=user.FirmaID).first()
                session['pending_firma_adi'] = firma.FirmaAdi if firma else 'Bilinmeyen Firma'
                
                flash('Bu kullanıcı zaten giriş yapmış. Mevcut oturumu kapatıp yeni giriş yapmak istiyor musunuz?', 'warning')
                return render_template('login.html', show_force_logout=True)

            # Firma bilgisini al
            firma = Firma.query.filter_by(FirmaID=user.FirmaID).first()
            
            session['user_id'] = user.KullaniciID
            session['username'] = user.KullaniciAdi
            session['user_name'] = f"{user.Ad} {user.Soyad}"
            session['firma_id'] = user.FirmaID
            session['firma_adi'] = firma.FirmaAdi if firma else 'Bilinmeyen Firma'
            session['is_admin'] = user.Admin
            session['raporlar_modulu'] = user.RaporlarModulu
            session['ayarlar_modulu'] = user.AyarlarModulu

            # Oturum kaydı oluştur
            import secrets
            token = secrets.token_hex(16)
            session['session_token'] = token
            kayit = AktifOturum(
                KullaniciID=user.KullaniciID,
                SessionToken=token,
                ClientIP=request.remote_addr,
                UserAgent=request.headers.get('User-Agent', '')
            )
            db.session.add(kayit)
            db.session.commit()
            
            # Zorunlu parola değişimi: 123 ise yönlendir
            if user.Sifre == '123':
                session['must_change_password'] = True
                flash('Lütfen güvenlik için şifrenizi değiştirin.', 'warning')
                return redirect(url_for('sifre_degistir'))
            flash('Başarıyla giriş yaptınız!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'error')
    
    return render_template('login.html')

@app.route('/force-logout', methods=['POST'])
def force_logout():
    """Mevcut oturumu kapat ve yeni giriş yap"""
    if 'pending_user_id' not in session:
        flash('Geçersiz işlem', 'error')
        return redirect(url_for('login'))
    
    # Mevcut oturumu kapat
    user_id = session['pending_user_id']
    mevcut = AktifOturum.query.filter_by(KullaniciID=user_id).first()
    if mevcut:
        db.session.delete(mevcut)
        db.session.commit()
    
    # Yeni oturum oluştur
    session['user_id'] = session['pending_user_id']
    session['username'] = session['pending_username']
    session['user_name'] = session['pending_user_name']
    session['firma_id'] = session['pending_firma_id']
    session['firma_adi'] = session['pending_firma_adi']
    session['is_admin'] = session['pending_is_admin']
    session['raporlar_modulu'] = session['pending_raporlar_modulu']
    session['ayarlar_modulu'] = session['pending_ayarlar_modulu']
    
    # Pending session verilerini temizle
    for key in list(session.keys()):
        if key.startswith('pending_'):
            session.pop(key, None)
    
    # Oturum kaydı oluştur
    import secrets
    token = secrets.token_hex(16)
    session['session_token'] = token
    kayit = AktifOturum(
        KullaniciID=user_id,
        SessionToken=token,
        ClientIP=request.remote_addr,
        UserAgent=request.headers.get('User-Agent', '')
    )
    db.session.add(kayit)
    db.session.commit()
    
    # Zorunlu parola değişimi kontrolü
    user = Kullanici.query.get(user_id)
    if user and user.Sifre == '123':
        session['must_change_password'] = True
        flash('Lütfen güvenlik için şifrenizi değiştirin.', 'warning')
        return redirect(url_for('sifre_degistir'))
    
    flash('Başarıyla giriş yaptınız!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/sifre-degistir', methods=['GET', 'POST'])
def sifre_degistir():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        yeni = request.form.get('yeni')
        yeni2 = request.form.get('yeni2')
        if not yeni or not yeni2:
            flash('Lütfen şifre alanlarını doldurun', 'error')
        elif yeni != yeni2:
            flash('Şifreler eşleşmiyor', 'error')
        elif not is_password_strong(yeni):
            flash('Şifre en az 8 haneli olmalı ve büyük/küçük harf, sayı ve özel karakter içermeli', 'error')
        else:
            u = Kullanici.query.get(session['user_id'])
            if not u:
                flash('Kullanıcı bulunamadı', 'error')
                return redirect(url_for('logout'))
            u.Sifre = yeni
            db.session.commit()
            session.pop('must_change_password', None)
            flash('Şifreniz güncellendi', 'success')
            return redirect(url_for('dashboard'))
    return render_template('sifre_degistir.html')

@app.route('/logout')
def logout():
    # Aktif oturumu temizle
    try:
        if 'user_id' in session:
            from sqlalchemy import and_
            u_id = session.get('user_id')
            token = session.get('session_token')
            kayit = AktifOturum.query.filter_by(KullaniciID=u_id).first()
            if kayit and (not token or kayit.SessionToken == token):
                db.session.delete(kayit)
                db.session.commit()
    except Exception:
        db.session.rollback()
    session.clear()
    flash('Başarıyla çıkış yaptınız!', 'success')
    return redirect(url_for('index'))

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


@app.route('/profil')
@login_required
def profil():
    u = Kullanici.query.get(session['user_id'])
    if not u:
        flash('Kullanıcı bulunamadı', 'error')
        return redirect(url_for('logout'))
    unread_count = Bildirim.query.filter_by(KullaniciID=session['user_id'], Okundu=False).count()
    return render_template('profil.html', kullanici=u, unread_count=unread_count)

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
        sifre = request.form.get('sifre') or '123'
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        
        # Admin değilse sadece kendi firmasına kullanıcı ekleyebilir
        if not session.get('is_admin', False):
            firma_id = session.get('firma_id')
        
        if not all([kullanici_adi, email, firma_id, ad, soyad]):
            flash('Tüm alanlar zorunludur', 'error')
        elif Kullanici.query.filter((Kullanici.KullaniciAdi==kullanici_adi) | (Kullanici.Email==email)).first():
            flash('Kullanıcı adı veya e-posta mevcut', 'error')
        else:
            # Modül izinlerini al
            raporlar_modulu = 'raporlar_modulu' in request.form
            ayarlar_modulu = 'ayarlar_modulu' in request.form
            
            # Varsayılan şifre 123 ve ilk girişte değişim zorunlu olacak
            u = Kullanici(KullaniciAdi=kullanici_adi, Email=email, FirmaID=firma_id,
                          Sifre=sifre or '123', Ad=ad, Soyad=soyad, Aktif=True,
                          RaporlarModulu=raporlar_modulu, AyarlarModulu=ayarlar_modulu)
            db.session.add(u)
            db.session.commit()

            # Fotoğraf işle (opsiyonel)
            try:
                # Öncelik: kırpılmış Base64 data
                cropped_b64 = request.form.get('foto_cropped')
                if cropped_b64 and cropped_b64.startswith('data:image'):
                    import base64
                    header, b64data = cropped_b64.split(',', 1)
                    raw = base64.b64decode(b64data)
                    from PIL import Image
                    import io
                    img = Image.open(io.BytesIO(raw)).convert('RGB')
                    os.makedirs(os.path.join('static', 'uploads', 'users'), exist_ok=True)
                    out_path = os.path.join('static', 'uploads', 'users', f'user_{u.KullaniciID}.jpg')
                    img.save(out_path, format='JPEG', quality=85, optimize=True)
                else:
                    foto = request.files.get('foto')
                    if foto and foto.filename:
                        from PIL import Image
                        import io
                        # Boyut kontrolü (sunucu tarafı)
                        foto.seek(0, io.SEEK_END)
                        size = foto.tell()
                        foto.seek(0)
                        if size <= 512 * 1024:
                            img = Image.open(foto.stream).convert('RGB')
                            # Kare kırp ve küçült (maks 256x256)
                            w, h = img.size
                            side = min(w, h)
                            left = (w - side) // 2
                            top = (h - side) // 2
                            img = img.crop((left, top, left + side, top + side))
                            img.thumbnail((256, 256))
                            # Kaydet
                            os.makedirs(os.path.join('static', 'uploads', 'users'), exist_ok=True)
                            out_path = os.path.join('static', 'uploads', 'users', f'user_{u.KullaniciID}.jpg')
                            img.save(out_path, format='JPEG', quality=85, optimize=True)
                        else:
                            flash('Fotoğraf 512KB üzeri olduğu için yüklenmedi.', 'warning')
            except Exception:
                flash('Fotoğraf işlenemedi.', 'warning')
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
        sifre2 = request.form.get('sifre2')
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
                
                # Şifre güncelleme (sadece girilmişse) + doğrulama ve karmaşıklık
                if sifre or sifre2:
                    if sifre != sifre2:
                        flash('Şifreler eşleşmiyor', 'error')
                        return redirect(url_for('ayarlar_kullanici_duzenle', kullanici_id=kullanici_id))
                    if not is_password_strong(sifre):
                        flash('Şifre en az 8 haneli olmalı ve büyük/küçük harf, sayı ve özel karakter içermeli', 'error')
                        return redirect(url_for('ayarlar_kullanici_duzenle', kullanici_id=kullanici_id))
                    kullanici.Sifre = sifre
                
                db.session.commit()

                # Fotoğraf güncelle (opsiyonel)
                try:
                    cropped_b64 = request.form.get('foto_cropped')
                    if cropped_b64 and cropped_b64.startswith('data:image'):
                        import base64
                        header, b64data = cropped_b64.split(',', 1)
                        raw = base64.b64decode(b64data)
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(raw)).convert('RGB')
                        os.makedirs(os.path.join('static', 'uploads', 'users'), exist_ok=True)
                        out_path = os.path.join('static', 'uploads', 'users', f'user_{kullanici.KullaniciID}.jpg')
                        img.save(out_path, format='JPEG', quality=85, optimize=True)
                    else:
                        foto = request.files.get('foto')
                        if foto and foto.filename:
                            from PIL import Image
                            import io
                            foto.seek(0, io.SEEK_END)
                            size = foto.tell()
                            foto.seek(0)
                            if size <= 512 * 1024:
                                img = Image.open(foto.stream).convert('RGB')
                                w, h = img.size
                                side = min(w, h)
                                left = (w - side) // 2
                                top = (h - side) // 2
                                img = img.crop((left, top, left + side, top + side))
                                img.thumbnail((256, 256))
                                os.makedirs(os.path.join('static', 'uploads', 'users'), exist_ok=True)
                                out_path = os.path.join('static', 'uploads', 'users', f'user_{kullanici.KullaniciID}.jpg')
                                img.save(out_path, format='JPEG', quality=85, optimize=True)
                            else:
                                flash('Fotoğraf 512KB üzeri olduğu için yüklenmedi.', 'warning')
                except Exception:
                    flash('Fotoğraf işlenemedi.', 'warning')
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

# Kullanıcı şifre sıfırla (123)
@app.route('/ayarlar/kullanicilar/sifre-sifirla/<int:kullanici_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_kullanici_sifre_sifirla(kullanici_id):
    kullanici = Kullanici.query.get_or_404(kullanici_id)
    # Admin değilse sadece kendi firmasının kullanıcılarını sıfırlayabilir
    if not session.get('is_admin', False) and kullanici.FirmaID != session.get('firma_id'):
        flash('Bu kullanıcı için işlem yetkiniz yok', 'error')
        return redirect(url_for('ayarlar_kullanicilar'))
    kullanici.Sifre = '123'
    db.session.commit()
    flash('Şifre 123 olarak sıfırlandı. İlk girişte değişiklik istenecek.', 'success')
    return redirect(url_for('ayarlar_kullanici_duzenle', kullanici_id=kullanici_id))

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
    ).filter(MusteriKategori.Aktif == 1).order_by(MusteriKategori.KategoriID.asc()).all()
    
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
        flash(gettext('Category name is required'), 'error')
        return redirect(url_for('ayarlar_defter'))
    
    # Aynı isimde kategori var mı kontrol et
    existing = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id'],
        KategoriAdi=kategori_adi
    ).first()
    
    if existing:
        flash(gettext('A category with this name already exists'), 'error')
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
    
    flash(gettext('Category added successfully'), 'success')
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
        flash(gettext('A category with this name already exists'), 'error')
        return redirect(url_for('ayarlar_defter'))
    
    kategori.KategoriAdi = kategori_adi
    kategori.Renk = kategori_renk
    kategori.Aciklama = kategori_aciklama
    kategori.Aktif = kategori_aktif
    
    db.session.commit()
    
    flash(gettext('Category updated successfully'), 'success')
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
    
    flash(gettext('Category deleted successfully'), 'success')
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
            VarsayilanEmailKonu=request.form.get('varsayilan_email_konu', ''),
            VarsayilanEmailMetni=request.form.get('varsayilan_email_metni', ''),
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
        email_ayar.VarsayilanEmailKonu = request.form.get('varsayilan_email_konu', '')
        email_ayar.VarsayilanEmailMetni = request.form.get('varsayilan_email_metni', '')
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
        # Admin ise herhangi bir firmanın ayarını silebilir
        if session.get('is_admin', False):
            email_ayar = FirmaEmailAyar.query.get_or_404(ayar_id)
        else:
            email_ayar = FirmaEmailAyar.query.filter_by(EmailAyarID=ayar_id, FirmaID=session['firma_id']).first_or_404()
        
        db.session.delete(email_ayar)
        db.session.commit()
        flash('E-posta ayarları silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'E-posta ayarları silinirken hata: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_email', firma_id=request.form.get('firma_id')))
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
        # Admin ise formdan gelen firma_id'yi kullan
        hedef_firma_id = session['firma_id']
        try:
            if session.get('is_admin', False) and request.form.get('firma_id'):
                hedef_firma_id = int(request.form.get('firma_id'))
        except Exception:
            pass

        sms_ayar = FirmaSMSAyar(
            FirmaID=hedef_firma_id,
            SMSFirmasi=request.form['sms_firmasi'],
            API_Key=request.form.get('api_key', ''),
            API_Secret=request.form.get('api_secret', ''),
            KullaniciAdi=request.form.get('kullanici_adi', ''),
            Sifre=request.form.get('sifre', ''),
            GondericiAdi=request.form.get('gonderici_adi', ''),
            API_URL=request.form.get('api_url', ''),
            VarsayilanSMSMetni=request.form.get('varsayilan_sms_metni', ''),
            SMSGonderOnCreate=('sms_on_create' in request.form),
            SMSGonder24SaatOnce=('sms_24h' in request.form),
            Aktif='aktif' in request.form
        )
        db.session.add(sms_ayar)
        db.session.commit()
        flash('SMS ayarları eklendi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'SMS ayarları eklenirken hata: {str(e)}', 'error')
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_sms', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_sms'))

@app.route('/ayarlar/sms/guncelle/<int:ayar_id>', methods=['POST'])
@login_required
@admin_required
def ayarlar_sms_guncelle(ayar_id):
    try:
        # Admin kullanıcı başka firma için işlem yapıyorsa firma_id formdan gelebilir
        firma_id = session['firma_id']
        try:
            if session.get('is_admin', False) and request.form.get('firma_id'):
                firma_id = int(request.form.get('firma_id'))
        except Exception:
            pass

        sms_ayar = FirmaSMSAyar.query.filter_by(SMSAyarID=ayar_id, FirmaID=firma_id).first_or_404()
        sms_ayar.SMSFirmasi = request.form['sms_firmasi']
        sms_ayar.API_Key = request.form.get('api_key', '')
        sms_ayar.API_Secret = request.form.get('api_secret', '')
        sms_ayar.KullaniciAdi = request.form.get('kullanici_adi', '')
        sms_ayar.Sifre = request.form.get('sifre', '')
        sms_ayar.GondericiAdi = request.form.get('gonderici_adi', '')
        sms_ayar.API_URL = request.form.get('api_url', '')
        sms_ayar.VarsayilanSMSMetni = request.form.get('varsayilan_sms_metni', '')
        sms_ayar.SMSGonderOnCreate = ('sms_on_create' in request.form)
        sms_ayar.SMSGonder24SaatOnce = ('sms_24h' in request.form)
        sms_ayar.Aktif = 'aktif' in request.form
        db.session.commit()
        flash('SMS ayarları güncellendi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'SMS ayarları güncellenirken hata: {str(e)}', 'error')
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_sms', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_sms'))

@app.route('/ayarlar/sms/sil/<int:ayar_id>', methods=['POST', 'GET'])
@login_required
@admin_required
def ayarlar_sms_sil(ayar_id):
    try:
        # Admin kullanıcı başka firma için işlem yapıyorsa firma_id formdan gelebilir
        firma_id = session['firma_id']
        try:
            if session.get('is_admin', False):
                if request.method == 'POST' and request.form.get('firma_id'):
                    firma_id = int(request.form.get('firma_id'))
                elif request.method == 'GET' and request.args.get('firma_id'):
                    firma_id = int(request.args.get('firma_id'))
        except Exception:
            pass

        sms_ayar = FirmaSMSAyar.query.filter_by(SMSAyarID=ayar_id, FirmaID=firma_id).first_or_404()
        db.session.delete(sms_ayar)
        db.session.commit()
        flash('SMS ayarları silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'SMS ayarları silinirken hata: {str(e)}', 'error')
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False):
        hedef_firma_id = None
        if request.method == 'POST':
            hedef_firma_id = request.form.get('firma_id')
        else:
            hedef_firma_id = request.args.get('firma_id')
        if hedef_firma_id:
            return redirect(url_for('ayarlar_sms', firma_id=hedef_firma_id))
    return redirect(url_for('ayarlar_sms'))

# WhatsApp Ayarları
@app.route('/ayarlar/whatsapp')
@login_required
def ayarlar_whatsapp():
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
        
        whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=selected_firma_id).first()
        firmalar = Firma.query.filter_by(Aktif=True).all()
        return render_template('ayarlar/whatsapp.html', 
                             whatsapp_ayar=whatsapp_ayar, 
                             firma=firma,
                             firmalar=firmalar,
                             is_admin=True)
    else:
        # Normal kullanıcı sadece kendi firmasını görebilir
        firma = Firma.query.get(session['firma_id'])
        if not firma:
            flash('Firma bilgisi bulunamadı!', 'error')
            return redirect(url_for('ayarlar'))
        
        whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=session['firma_id']).first()
        return render_template('ayarlar/whatsapp.html', 
                             whatsapp_ayar=whatsapp_ayar, 
                             firma=firma,
                             is_admin=False)

@app.route('/ayarlar/whatsapp/ekle', methods=['POST'])
@login_required
def ayarlar_whatsapp_ekle():
    try:
        # Admin ise formdan gelen firma_id'yi kullan
        hedef_firma_id = session['firma_id']
        try:
            if session.get('is_admin', False) and request.form.get('firma_id'):
                hedef_firma_id = int(request.form.get('firma_id'))
        except (ValueError, TypeError):
            pass
        
        # Mevcut ayar var mı kontrol et
        mevcut_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=hedef_firma_id).first()
        if mevcut_ayar:
            flash('Bu firma için WhatsApp ayarı zaten mevcut!', 'error')
            return redirect(url_for('ayarlar_whatsapp'))
        
        # Yeni WhatsApp ayarı oluştur
        whatsapp_ayar = FirmaWhatsAppAyar(
            FirmaID=hedef_firma_id,
            AccessToken=request.form.get('access_token'),
            PhoneNumberID=request.form.get('phone_number_id'),
            BusinessAccountID=request.form.get('business_account_id'),
            WebhookVerifyToken=request.form.get('webhook_verify_token'),
            RandevuOlusturmaMesaji=request.form.get('randevu_olusturma_mesaji'),
            RandevuHatirlatmaMesaji=request.form.get('randevu_hatirlatma_mesaji'),
            RandevuIptalMesaji=request.form.get('randevu_iptal_mesaji'),
            MesajGonderOnCreate=bool(request.form.get('mesaj_gonder_on_create')),
            MesajGonder24SaatOnce=bool(request.form.get('mesaj_gonder_24_saat_once')),
            MesajGonder1SaatOnce=bool(request.form.get('mesaj_gonder_1_saat_once')),
            Aktif=True
        )
        
        db.session.add(whatsapp_ayar)
        db.session.commit()
        
        flash('WhatsApp ayarları başarıyla eklendi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'WhatsApp ayarları eklenirken hata oluştu: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_whatsapp', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_whatsapp'))

@app.route('/ayarlar/whatsapp/guncelle/<int:ayar_id>', methods=['POST'])
@login_required
def ayarlar_whatsapp_guncelle(ayar_id):
    try:
        whatsapp_ayar = FirmaWhatsAppAyar.query.get_or_404(ayar_id)
        
        # Kullanıcı yetkisi kontrolü
        if not session.get('is_admin', False) and whatsapp_ayar.FirmaID != session['firma_id']:
            flash('Bu ayarı düzenleme yetkiniz yok!', 'error')
            return redirect(url_for('ayarlar_whatsapp'))
        
        # Ayarları güncelle
        whatsapp_ayar.AccessToken = request.form.get('access_token')
        whatsapp_ayar.PhoneNumberID = request.form.get('phone_number_id')
        whatsapp_ayar.BusinessAccountID = request.form.get('business_account_id')
        whatsapp_ayar.WebhookVerifyToken = request.form.get('webhook_verify_token')
        whatsapp_ayar.RandevuOlusturmaMesaji = request.form.get('randevu_olusturma_mesaji')
        whatsapp_ayar.RandevuHatirlatmaMesaji = request.form.get('randevu_hatirlatma_mesaji')
        whatsapp_ayar.RandevuIptalMesaji = request.form.get('randevu_iptal_mesaji')
        whatsapp_ayar.MesajGonderOnCreate = bool(request.form.get('mesaj_gonder_on_create'))
        whatsapp_ayar.MesajGonder24SaatOnce = bool(request.form.get('mesaj_gonder_24_saat_once'))
        whatsapp_ayar.MesajGonder1SaatOnce = bool(request.form.get('mesaj_gonder_1_saat_once'))
        whatsapp_ayar.GuncellemeTarihi = datetime.utcnow()
        
        db.session.commit()
        flash('WhatsApp ayarları başarıyla güncellendi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'WhatsApp ayarları güncellenirken hata oluştu: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False) and request.form.get('firma_id'):
        return redirect(url_for('ayarlar_whatsapp', firma_id=request.form.get('firma_id')))
    return redirect(url_for('ayarlar_whatsapp'))

@app.route('/ayarlar/whatsapp/sil/<int:ayar_id>', methods=['POST', 'GET'])
@login_required
def ayarlar_whatsapp_sil(ayar_id):
    try:
        whatsapp_ayar = FirmaWhatsAppAyar.query.get_or_404(ayar_id)
        
        # Kullanıcı yetkisi kontrolü
        if not session.get('is_admin', False) and whatsapp_ayar.FirmaID != session['firma_id']:
            flash('Bu ayarı silme yetkiniz yok!', 'error')
            return redirect(url_for('ayarlar_whatsapp'))
        
        db.session.delete(whatsapp_ayar)
        db.session.commit()
        flash('WhatsApp ayarları başarıyla silindi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'WhatsApp ayarları silinirken hata oluştu: {str(e)}', 'error')
    
    # Admin ise seçilen firmaya yönlendir
    if session.get('is_admin', False):
        hedef_firma_id = request.args.get('firma_id')
        if hedef_firma_id:
            return redirect(url_for('ayarlar_whatsapp', firma_id=hedef_firma_id))
    return redirect(url_for('ayarlar_whatsapp'))

# WhatsApp Sohbet Ekranı
@app.route('/whatsapp')
@login_required
def whatsapp_chat():
    """WhatsApp Business API entegrasyonu ile sohbet ekranı"""
    # Firma WhatsApp ayarlarını kontrol et
    whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).first()
    
    if not whatsapp_ayar:
        flash('WhatsApp ayarları bulunamadı. Lütfen önce WhatsApp ayarlarını yapılandırın.', 'warning')
        return redirect(url_for('ayarlar_whatsapp'))
    
    # Müşteri listesini getir (mesaj gönderme için)
    from app import Musteri
    musteriler = Musteri.query.filter_by(FirmaID=session['firma_id']).all()
    
    return render_template('whatsapp/chat.html', 
                         whatsapp_ayar=whatsapp_ayar,
                         musteriler=musteriler)

# WhatsApp Mesaj Gönderme API
@app.route('/api/whatsapp/send', methods=['POST'])
@login_required
def whatsapp_send_message():
    """WhatsApp mesajı gönder"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        message = data.get('message')
        
        if not phone_number or not message:
            return jsonify({'success': False, 'error': 'Telefon numarası ve mesaj gerekli'}), 400
        
        # Telefon numarasını temizle
        phone_clean = ''.join(filter(str.isdigit, phone_number))
        if not phone_clean or len(phone_clean) < 10:
            return jsonify({'success': False, 'error': 'Geçersiz telefon numarası'}), 400
        
        # WhatsApp mesajını gönder
        success, result = send_whatsapp_message(phone_clean, message, session['firma_id'])
        
        if success:
            return jsonify({'success': True, 'message': 'Mesaj başarıyla gönderildi'})
        else:
            return jsonify({'success': False, 'error': result}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# WhatsApp mesaj gönderme fonksiyonu
def send_whatsapp_message(phone_number, message, firma_id):
    """WhatsApp mesajı gönder"""
    try:
        whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=firma_id, Aktif=True).first()
        if not whatsapp_ayar or not whatsapp_ayar.AccessToken or not whatsapp_ayar.PhoneNumberID:
            return False, "WhatsApp ayarları bulunamadı"
        
        import requests
        
        url = f"https://graph.facebook.com/v18.0/{whatsapp_ayar.PhoneNumberID}/messages"
        headers = {
            "Authorization": f"Bearer {whatsapp_ayar.AccessToken}",
            "Content-Type": "application/json"
        }
        
        data = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {"body": message}
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            return True, "Mesaj başarıyla gönderildi"
        else:
            return False, f"Mesaj gönderilemedi: {response.text}"
            
    except Exception as e:
        return False, f"Hata: {str(e)}"

@app.route('/randevular')
@login_required
def randevular():
    # Randevu listesi + referans, defter, durum, tarih ve oluşturan filtresi
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuReferans.Ad).all()
    defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuDefterAyar.DefterAdi).all()
    kullanicilar = Kullanici.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(Kullanici.Ad, Kullanici.Soyad).all()
    
    ref_id = request.args.get('referans_id', type=int)
    defter_id = request.args.get('defter_id', type=int)
    durum = request.args.get('durum', type=str)
    olusturan_id = request.args.get('olusturan_id', type=int)
    baslangic_str = request.args.get('baslangic', type=str)
    bitis_str = request.args.get('bitis', type=str)

    # Kullanıcının son seçtiği tarih aralığını hatırla
    if baslangic_str or bitis_str:
        if baslangic_str:
            session['randevular_baslangic'] = baslangic_str
        if bitis_str:
            session['randevular_bitis'] = bitis_str
    else:
        baslangic_str = session.get('randevular_baslangic')
        bitis_str = session.get('randevular_bitis')
    
    # Eğer hâlâ tarih filtresi yoksa bugünü varsayılan olarak ayarla
    if not baslangic_str and not bitis_str:
        today = datetime.now().date()
        baslangic_str = today.strftime('%Y-%m-%d')
        bitis_str = today.strftime('%Y-%m-%d')
    
    # Tarih filtrelerini datetime'a çevir
    baslangic = None
    bitis = None
    if baslangic_str:
        try:
            baslangic = datetime.strptime(baslangic_str, '%Y-%m-%d')
        except ValueError:
            baslangic = None
    if bitis_str:
        try:
            bitis = datetime.strptime(bitis_str, '%Y-%m-%d')
            # Bitiş tarihine 1 gün ekle (tarih aralığı dahil olsun)
            bitis = bitis + timedelta(days=1)
        except ValueError:
            bitis = None
    
    ref = None
    defter = None
    olusturan = None
    if ref_id:
        ref = RandevuReferans.query.filter_by(ReferansID=ref_id, FirmaID=session['firma_id']).first()
    if defter_id:
        defter = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=session['firma_id']).first()
    if olusturan_id:
        olusturan = Kullanici.query.filter_by(KullaniciID=olusturan_id, FirmaID=session['firma_id']).first()

    base_query = Randevu.query if session.get('is_admin', False) else db.session.query(Randevu).join(RandevuYetki).filter(
        RandevuYetki.KullaniciID == session['user_id'],
        RandevuYetki.GoruntulemeYetkisi == True
    )

    q = base_query.filter(Randevu.FirmaID == session['firma_id'])
    if ref is not None:
        q = q.filter(Randevu.RandevuBaslik == ref.Ad)
    if defter is not None:
        q = q.filter(Randevu.DefterID == defter.AyarID)
    if durum:
        q = q.filter(Randevu.Durum == durum)
    if olusturan is not None:
        q = q.filter(Randevu.OlusturanKullaniciID == olusturan.KullaniciID)
    if baslangic:
        q = q.filter(Randevu.RandevuTarihi >= baslangic)
    if bitis:
        q = q.filter(Randevu.RandevuTarihi < bitis)

    randevular = q.order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Bugünün tarihini string olarak hazırla
    today_str = datetime.now().date().strftime('%Y-%m-%d')
    
    return render_template('randevular.html', 
                         randevular=randevular, 
                         referanslar=referanslar, 
                         defterler=defterler,
                         kullanicilar=kullanicilar,
                         selected_referans_id=ref_id,
                         selected_defter_id=defter_id,
                         selected_durum=durum,
                         selected_olusturan_id=olusturan_id,
                         selected_baslangic=baslangic_str,
                         selected_bitis=bitis_str,
                         today_str=today_str)

@app.route('/api/musteri-arama')
@login_required
def musteri_arama():
    """Müşteri arama API'si"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return jsonify([])
    
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    # Müşteri arama sorgusu
    musteriler = Musteri.query.filter(
        Musteri.FirmaID == firma_id,
        or_(
            Musteri.MusteriAdi.ilike(f'%{query}%'),
            Musteri.MusteriSoyadi.ilike(f'%{query}%'),
            Musteri.Telefon.ilike(f'%{query}%'),
            Musteri.Email.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    # Plaka kodlarını şehir isimlerine dönüştür
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }
    
    results = []
    for m in musteriler:
        sehir_adi = plaka_to_sehir.get(m.Sehir, m.Sehir) if m.Sehir else None
        results.append({
            'id': m.MusteriID,
            'ad': m.MusteriAdi,
            'soyad': m.MusteriSoyadi,
            'telefon': m.Telefon,
            'email': m.Email,
            'sehir': sehir_adi
        })
    
    return jsonify(results)

@app.route('/rapor/musteri-detay/<int:musteri_id>')
@login_required
def musteri_detay_raporu(musteri_id):
    """Müşteri detay raporu"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        flash('Müşteri bulunamadı.', 'error')
        return redirect(url_for('rapor_musteriler'))
    
    # Plaka kodlarını şehir isimlerine dönüştür
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Randevu istatistikleri
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    # Son randevu tarihi
    son_randevu = randevular[0] if randevular else None
    
    # Aylık randevu dağılımı (son 12 ay)
    from collections import defaultdict
    
    aylik_randevu = defaultdict(int)
    for r in randevular:
        if r.RandevuTarihi:
            ay_key = r.RandevuTarihi.strftime('%Y-%m')
            aylik_randevu[ay_key] += 1
    
    # Randevu defteri dağılımı
    defter_dagilimi = defaultdict(int)
    for r in randevular:
        if r.DefterID:
            # DefterID'den defter adını al
            defter = RandevuDefterAyar.query.filter_by(AyarID=r.DefterID).first()
            if defter:
                defter_dagilimi[defter.DefterAdi] += 1
            else:
                defter_dagilimi['Bilinmeyen Defter'] += 1
    
    # Şehir bilgisini dönüştür
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    
    return render_template('musteri_detay_raporu.html',
                         musteri=musteri,
                         randevular=randevular,
                         toplam_randevu=toplam_randevu,
                         tamamlanan_randevu=tamamlanan_randevu,
                         iptal_randevu=iptal_randevu,
                         bekleyen_randevu=bekleyen_randevu,
                         son_randevu=son_randevu,
                         aylik_randevu=dict(aylik_randevu),
                         defter_dagilimi=dict(defter_dagilimi),
                         sehir_adi=sehir_adi)

@app.route('/rapor/musteri-detay-modal/<int:musteri_id>')
@login_required
def musteri_detay_modal(musteri_id):
    """Müşteri detay raporu modal içeriği"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        return '<div class="alert alert-danger">Müşteri bulunamadı.</div>'
    
    # Plaka kodlarını şehir isimlerine dönüştür
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Randevu istatistikleri
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    # Aylık randevu dağılımı
    aylik_randevu = defaultdict(int)
    for randevu in randevular:
        if randevu.RandevuTarihi:
            ay_key = randevu.RandevuTarihi.strftime('%Y-%m')
            aylik_randevu[ay_key] += 1
    
    # Defter dağılımı
    defter_dagilimi = defaultdict(int)
    for randevu in randevular:
        if randevu.DefterID:
            defter = RandevuDefterAyar.query.filter_by(AyarID=randevu.DefterID).first()
            if defter:
                defter_dagilimi[defter.DefterAdi] += 1
    
    # Şehir bilgisini dönüştür
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    
    return render_template('musteri_detay_modal.html',
                         musteri=musteri,
                         randevular=randevular,
                         toplam_randevu=toplam_randevu,
                         tamamlanan_randevu=tamamlanan_randevu,
                         iptal_randevu=iptal_randevu,
                         bekleyen_randevu=bekleyen_randevu,
                         aylik_randevu=dict(aylik_randevu),
                         defter_dagilimi=dict(defter_dagilimi),
                         sehir_adi=sehir_adi)

@app.route('/rapor/musteri-detay/<int:musteri_id>/pdf')
@login_required
def musteri_detay_pdf(musteri_id):
    """Müşteri detay raporu PDF"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        flash('Müşteri bulunamadı.', 'error')
        return redirect(url_for('rapor_musteriler'))
    
    # Plaka kodlarını şehir isimlerine dönüştür
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Randevu istatistikleri
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    # Şehir bilgisini dönüştür
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    
    # PDF oluştur
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Türkçe font desteği için DejaVu Sans fontunu kaydet
    try:
        # Windows sistem fontları
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/dejavu-sans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/dejavu-sans-bold.ttf'))
        turkish_font = 'DejaVuSans'
        turkish_font_bold = 'DejaVuSans-Bold'
    except:
        try:
            # Alternatif font yolları
            pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/arial.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
            turkish_font = 'DejaVuSans'
            turkish_font_bold = 'DejaVuSans-Bold'
        except:
            # Varsayılan font
            turkish_font = 'Helvetica'
            turkish_font_bold = 'Helvetica-Bold'
    
    # Stil tanımları
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=TA_CENTER, fontName=turkish_font_bold)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, spaceAfter=12, fontName=turkish_font_bold)
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontName=turkish_font)
    
    # İçerik oluştur
    story = []
    
    # Başlık
    story.append(Paragraph("Müşteri Detay Raporu", title_style))
    story.append(Spacer(1, 12))
    
    # Müşteri bilgileri
    story.append(Paragraph("Müşteri Bilgileri", heading_style))
    
    musteri_data = [
        ['Ad Soyad:', f"{musteri.MusteriAdi} {musteri.MusteriSoyadi}"],
        ['Telefon:', musteri.Telefon or 'Belirtilmemiş'],
        ['E-posta:', musteri.Email or 'Belirtilmemiş'],
        ['Yaş:', str(musteri.Yas) if musteri.Yas else 'Belirtilmemiş'],
        ['Cinsiyet:', musteri.Cinsiyet or 'Belirtilmemiş'],
        ['Şehir:', sehir_adi],
        ['İlçe:', musteri.Ilce or 'Belirtilmemiş'],
        ['Doğum Tarihi:', musteri.DogumTarihi.strftime('%d.%m.%Y') if musteri.DogumTarihi else 'Belirtilmemiş']
    ]
    
    if musteri.Adres:
        musteri_data.append(['Adres:', musteri.Adres])
    if musteri.Notlar:
        musteri_data.append(['Notlar:', musteri.Notlar])
    
    musteri_table = Table(musteri_data, colWidths=[2*inch, 4*inch])
    musteri_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), turkish_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(musteri_table)
    story.append(Spacer(1, 20))
    
    # Randevu istatistikleri
    story.append(Paragraph("Randevu İstatistikleri", heading_style))
    
    stats_data = [
        ['Toplam Randevu:', str(toplam_randevu)],
        ['Tamamlanan:', str(tamamlanan_randevu)],
        ['Beklemede:', str(bekleyen_randevu)],
        ['İptal:', str(iptal_randevu)]
    ]
    
    stats_table = Table(stats_data, colWidths=[2*inch, 1*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), turkish_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 20))
    
    # Randevu geçmişi
    if randevular:
        story.append(Paragraph("Randevu Geçmişi", heading_style))
        
        randevu_data = [['Tarih', 'Saat', 'Defter', 'Durum', 'Notlar']]
        
        for randevu in randevular:
            defter_adi = 'Bilinmeyen'
            if randevu.DefterID:
                defter = RandevuDefterAyar.query.filter_by(AyarID=randevu.DefterID).first()
                if defter:
                    defter_adi = defter.DefterAdi
            
            randevu_data.append([
                randevu.RandevuTarihi.strftime('%d.%m.%Y') if randevu.RandevuTarihi else '-',
                randevu.RandevuTarihi.strftime('%H:%M') if randevu.RandevuTarihi else '-',
                defter_adi,
                randevu.Durum,
                randevu.RandevuAciklamasi or '-'
            ])
        
        randevu_table = Table(randevu_data, colWidths=[1*inch, 0.8*inch, 1.2*inch, 1*inch, 2*inch])
        randevu_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), turkish_font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), turkish_font),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(randevu_table)
    else:
        story.append(Paragraph("Bu müşteri için randevu bulunamadı.", normal_style))
    
    # PDF'i oluştur
    doc.build(story)
    buffer.seek(0)
    
    # Dosya adı
    filename = f"musteri_detay_{musteri.MusteriAdi}_{musteri.MusteriSoyadi}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)

@app.route('/rapor/musteri-detay/<int:musteri_id>/excel')
@login_required
def musteri_detay_excel(musteri_id):
    """Müşteri detay raporu Excel"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        flash('Müşteri bulunamadı.', 'error')
        return redirect(url_for('rapor_musteriler'))
    
    # Plaka kodlarını şehir isimlerine dönüştür
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Excel dosyası oluştur
    wb = Workbook()
    
    # Müşteri bilgileri sayfası
    ws1 = wb.active
    ws1.title = "Müşteri Bilgileri"
    
    # Başlık
    ws1['A1'] = "Müşteri Detay Raporu"
    ws1['A1'].font = Font(size=16, bold=True)
    ws1.merge_cells('A1:D1')
    
    # Müşteri bilgileri
    row = 3
    ws1[f'A{row}'] = "Ad Soyad:"
    ws1[f'B{row}'] = f"{musteri.MusteriAdi} {musteri.MusteriSoyadi}"
    row += 1
    
    ws1[f'A{row}'] = "Telefon:"
    telefon_cell = ws1[f'B{row}']
    telefon_cell.value = musteri.Telefon or 'Belirtilmemiş'
    telefon_cell.number_format = '@'  # Metin formatı
    row += 1
    
    ws1[f'A{row}'] = "E-posta:"
    ws1[f'B{row}'] = musteri.Email or 'Belirtilmemiş'
    row += 1
    
    ws1[f'A{row}'] = "Yaş:"
    ws1[f'B{row}'] = musteri.Yas or 'Belirtilmemiş'
    row += 1
    
    ws1[f'A{row}'] = "Cinsiyet:"
    ws1[f'B{row}'] = musteri.Cinsiyet or 'Belirtilmemiş'
    row += 1
    
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    ws1[f'A{row}'] = "Şehir:"
    ws1[f'B{row}'] = sehir_adi
    row += 1
    
    ws1[f'A{row}'] = "İlçe:"
    ws1[f'B{row}'] = musteri.Ilce or 'Belirtilmemiş'
    row += 1
    
    ws1[f'A{row}'] = "Doğum Tarihi:"
    ws1[f'B{row}'] = musteri.DogumTarihi.strftime('%d.%m.%Y') if musteri.DogumTarihi else 'Belirtilmemiş'
    row += 1
    
    if musteri.Adres:
        ws1[f'A{row}'] = "Adres:"
        ws1[f'B{row}'] = musteri.Adres
        row += 1
    
    if musteri.Notlar:
        ws1[f'A{row}'] = "Notlar:"
        ws1[f'B{row}'] = musteri.Notlar
        row += 1
    
    # Randevu istatistikleri
    row += 2
    ws1[f'A{row}'] = "Randevu İstatistikleri"
    ws1[f'A{row}'].font = Font(size=14, bold=True)
    row += 1
    
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    ws1[f'A{row}'] = "Toplam Randevu:"
    ws1[f'B{row}'] = toplam_randevu
    row += 1
    
    ws1[f'A{row}'] = "Tamamlanan:"
    ws1[f'B{row}'] = tamamlanan_randevu
    row += 1
    
    ws1[f'A{row}'] = "Beklemede:"
    ws1[f'B{row}'] = bekleyen_randevu
    row += 1
    
    ws1[f'A{row}'] = "İptal:"
    ws1[f'B{row}'] = iptal_randevu
    
    # Randevu geçmişi sayfası
    ws2 = wb.create_sheet("Randevu Geçmişi")
    
    # Başlıklar
    headers = ['Tarih', 'Saat', 'Defter', 'Durum', 'Notlar']
    for col, header in enumerate(headers, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
    
    # Randevu verileri
    for row_idx, randevu in enumerate(randevular, 2):
        defter_adi = 'Bilinmeyen'
        if randevu.DefterID:
            defter = RandevuDefterAyar.query.filter_by(AyarID=randevu.DefterID).first()
            if defter:
                defter_adi = defter.DefterAdi
        
        ws2.cell(row=row_idx, column=1, value=randevu.RandevuTarihi.strftime('%d.%m.%Y') if randevu.RandevuTarihi else '-')
        ws2.cell(row=row_idx, column=2, value=randevu.RandevuTarihi.strftime('%H:%M') if randevu.RandevuTarihi else '-')
        ws2.cell(row=row_idx, column=3, value=defter_adi)
        ws2.cell(row=row_idx, column=4, value=randevu.Durum)
        ws2.cell(row=row_idx, column=5, value=randevu.RandevuAciklamasi or '-')
    
    # Sütun genişliklerini ayarla
    for ws in [ws1, ws2]:
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
    
    # Excel dosyasını kaydet
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    # Dosya adı
    filename = f"musteri_detay_{musteri.MusteriAdi}_{musteri.MusteriSoyadi}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                    as_attachment=True, download_name=filename)

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
    kategori_id = request.args.get('kategori_id', type=int)
    sadece_aktif = request.args.get('aktif', default='1')  # '1' aktif, '' hepsi
    iletisim_var = request.args.get('iletisim_var')  # 'telefon', 'email', 'herikisi'
    
    # Yeni filtreler
    yas_min = request.args.get('yas_min', type=int)
    yas_max = request.args.get('yas_max', type=int)
    cinsiyet = request.args.get('cinsiyet')
    dogum_tarihi = request.args.get('dogum_tarihi')
    sehir = request.args.get('sehir')
    ilce = request.args.get('ilce')
    
    format_tip = request.args.get('format')  # 'csv' ise CSV döndür

    # Plaka kodları - şehir isimleri dönüşüm tablosu
    plaka_to_sehir = {
        '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
        '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
        '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
        '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
        '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
        '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
        '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
        '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
        '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
        '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
        '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
        '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
        '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
        '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
        '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
        '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
    }

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
    
    # Yeni filtreler
    if yas_min is not None:
        musteri_query = musteri_query.filter(Musteri.Yas >= yas_min)
    if yas_max is not None:
        musteri_query = musteri_query.filter(Musteri.Yas <= yas_max)
    if cinsiyet:
        musteri_query = musteri_query.filter(Musteri.Cinsiyet == cinsiyet)
    if dogum_tarihi:
        try:
            dogum_tarihi_obj = datetime.strptime(dogum_tarihi, '%Y-%m-%d').date()
            musteri_query = musteri_query.filter(Musteri.DogumTarihi == dogum_tarihi_obj)
        except:
            pass
    if sehir:
        # Seçilen şehir ismini plaka koduna dönüştür
        sehir_to_plaka = {v: k for k, v in plaka_to_sehir.items()}
        plaka_kodu = sehir_to_plaka.get(sehir, sehir)  # Eğer şehir ismi plaka kodunda yoksa orijinal değeri kullan
        musteri_query = musteri_query.filter(Musteri.Sehir == plaka_kodu)
    if ilce:
        musteri_query = musteri_query.filter(Musteri.Ilce == ilce)

    musteriler = musteri_query.order_by(Musteri.MusteriAdi, Musteri.MusteriSoyadi).all()

    # KPI'lar
    toplam_musteri = Musteri.query.filter_by(FirmaID=firma_id).count()
    aktif_musteri = Musteri.query.filter_by(FirmaID=firma_id, Aktif=True).count()
    yeni_musteri = 0

    # Randevu istatistikleri (müşteri başına randevu sayısı)
    randevu_q = db.session.query(Randevu.MusteriID, db.func.count(Randevu.RandevuID).label('adet')) 
    randevu_q = randevu_q.filter(Randevu.FirmaID == firma_id, Randevu.MusteriID.isnot(None))
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
    # Müşterileri birleştir (ad+soyad+telefon)
    def _norm_name(v):
        return (v or '').strip().lower()
    def _norm_phone(v):
        v = ''.join(ch for ch in (v or '') if ch.isdigit())
        return v[-10:] if len(v) >= 10 else v

    merged = {}
    for m in musteriler:
        k = (_norm_name(m.MusteriAdi), _norm_name(m.MusteriSoyadi), _norm_phone(m.Telefon))
        if k not in merged:
            merged[k] = {
                'id': m.MusteriID,
                'ad': m.MusteriAdi,
                'soyad': m.MusteriSoyadi,
                'telefon': m.Telefon or '',
                'email': m.Email or '',
                'aktif': bool(m.Aktif),
                'kategori': m.kategori.KategoriAdi if m.kategori else None,
                'olusturma': m.OlusturmaTarihi,
                'randevu_sayisi': musteri_id_to_randevu_adet.get(m.MusteriID, 0)
            }
        else:
            it = merged[k]
            it['randevu_sayisi'] += musteri_id_to_randevu_adet.get(m.MusteriID, 0)
            if not it['email'] and m.Email:
                it['email'] = m.Email
            if not it['kategori'] and m.kategori:
                it['kategori'] = m.kategori.KategoriAdi
            it['aktif'] = it['aktif'] or bool(m.Aktif)
            if it['olusturma'] is None or (m.OlusturmaTarihi and m.OlusturmaTarihi < it['olusturma']):
                it['olusturma'] = m.OlusturmaTarihi

    merged_rows = list(merged.values())

    # En çok randevusu olan 10 müşteri (birleştirilmiş verilerden)
    top_musteriler = sorted(merged_rows, key=lambda x: x['randevu_sayisi'], reverse=True)[:10]

    # CSV dışa aktarım (birleştirilmiş)
    if format_tip == 'csv':
        output = StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['MusteriID', 'Ad', 'Soyad', 'Telefon', 'Email', 'Aktif', 'Kategori', 'OlusturmaTarihi', 'RandevuSayisi'])
        for r in merged_rows:
            # Telefon numarasını Excel'de metin olarak tanıması için +90'dan sonra boşluk ekle
            telefon = r['telefon'] or ''
            if telefon and telefon.startswith('+90'):
                telefon = telefon.replace('+90', '+90 ')  # +90'dan sonra boşluk ekle
            writer.writerow([
                r['id'], r['ad'], r['soyad'], telefon, r['email'], 'Evet' if r['aktif'] else 'Hayır', r['kategori'] or '', (r['olusturma'].strftime('%Y-%m-%d %H:%M') if r['olusturma'] else ''), r['randevu_sayisi']
            ])
        output.seek(0)
        filename = f"musteri_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        data = output.getvalue().encode('utf-8-sig')
        return send_file(BytesIO(data), mimetype='text/csv; charset=utf-8', as_attachment=True, download_name=filename)

    # Kategoriler dropdown için
    kategoriler = MusteriKategori.query.filter_by(FirmaID=firma_id).order_by(MusteriKategori.KategoriAdi).all()
    
    # Şehir ve ilçe seçenekleri
    sehirler = db.session.query(Musteri.Sehir).filter(
        Musteri.FirmaID == firma_id,
        Musteri.Sehir.isnot(None),
        Musteri.Sehir != ''
    ).distinct().order_by(Musteri.Sehir).all()
    
    
    # Plaka kodlarını şehir isimlerine dönüştür ve benzersiz hale getir
    sehir_listesi = []
    for s in sehirler:
        plaka = s[0]
        sehir_adi = plaka_to_sehir.get(plaka, plaka)  # Eğer plaka kodunda yoksa orijinal değeri kullan
        if sehir_adi not in sehir_listesi:
            sehir_listesi.append(sehir_adi)
    
    sehir_listesi.sort()  # Alfabetik sırala
    
    ilceler = db.session.query(Musteri.Ilce).filter(
        Musteri.FirmaID == firma_id,
        Musteri.Ilce.isnot(None),
        Musteri.Ilce != ''
    ).distinct().order_by(Musteri.Ilce).all()
    ilce_listesi = [i[0] for i in ilceler]
    
    # Grafik verileri
    # Cinsiyet dağılımı
    gender_stats = db.session.query(Musteri.Cinsiyet, db.func.count(Musteri.MusteriID)).filter(
        Musteri.FirmaID == firma_id
    ).group_by(Musteri.Cinsiyet).all()
    gender_data = {gender: count for gender, count in gender_stats if gender}
    
    # Yaş dağılımı (yaş grupları)
    age_groups = {
        '0-18': 0, '19-25': 0, '26-35': 0, '36-45': 0, '46-55': 0, '56-65': 0, '65+': 0
    }
    age_stats = db.session.query(Musteri.Yas).filter(
        Musteri.FirmaID == firma_id, Musteri.Yas.isnot(None)
    ).all()
    for (yas,) in age_stats:
        if yas <= 18:
            age_groups['0-18'] += 1
        elif yas <= 25:
            age_groups['19-25'] += 1
        elif yas <= 35:
            age_groups['26-35'] += 1
        elif yas <= 45:
            age_groups['36-45'] += 1
        elif yas <= 55:
            age_groups['46-55'] += 1
        elif yas <= 65:
            age_groups['56-65'] += 1
        else:
            age_groups['65+'] += 1
    
    # Kategori dağılımı
    category_stats = db.session.query(
        MusteriKategori.KategoriAdi, db.func.count(Musteri.MusteriID)
    ).join(Musteri, Musteri.KategoriID == MusteriKategori.KategoriID).filter(
        Musteri.FirmaID == firma_id
    ).group_by(MusteriKategori.KategoriAdi).all()
    category_data = {kategori: count for kategori, count in category_stats}
    
    # Şehir dağılımı (top 10)
    city_stats = db.session.query(
        Musteri.Sehir, db.func.count(Musteri.MusteriID)
    ).filter(
        Musteri.FirmaID == firma_id, Musteri.Sehir.isnot(None), Musteri.Sehir != ''
    ).group_by(Musteri.Sehir).order_by(db.func.count(Musteri.MusteriID).desc()).limit(10).all()
    city_data = {sehir: count for sehir, count in city_stats}

    # Görüntülenecek satırlar için zenginleştirme
    rows = []
    for r in merged_rows:
        rows.append({
            'id': r['id'],
            'ad': r['ad'],
            'soyad': r['soyad'],
            'tam_ad': f"{r['ad']} {r['soyad']}".strip(),
            'telefon': r['telefon'],
            'email': r['email'],
            'aktif': r['aktif'],
            'kategori': r['kategori'],
            'olusturma': r['olusturma'],
            'randevu_sayisi': r['randevu_sayisi']
        })

    # Zaman serisi analizi - Aylık müşteri artışı
    monthly_data = {}
    for m in musteriler:
        if m.OlusturmaTarihi:
            month_key = m.OlusturmaTarihi.strftime('%Y-%m')
            monthly_data[month_key] = monthly_data.get(month_key, 0) + 1
    
    # Zaman serisi analizi - Haftalık müşteri artışı (son 12 hafta)
    weekly_data = {}
    today = datetime.now().date()
    
    # Son 12 hafta için haftalık veriler
    for i in range(12):
        week_start = today - timedelta(weeks=i+1)
        week_end = today - timedelta(weeks=i)
        week_key = f"{week_start.strftime('%Y-%m-%d')} - {week_end.strftime('%Y-%m-%d')}"
        weekly_data[week_key] = 0
    
    for m in musteriler:
        if m.OlusturmaTarihi:
            m_date = m.OlusturmaTarihi.date()
            for i in range(12):
                week_start = today - timedelta(weeks=i+1)
                week_end = today - timedelta(weeks=i)
                if week_start <= m_date < week_end:
                    week_key = f"{week_start.strftime('%Y-%m-%d')} - {week_end.strftime('%Y-%m-%d')}"
                    weekly_data[week_key] = weekly_data.get(week_key, 0) + 1
                    break
    
    # Randevu trendleri - Müşteri başına randevu sayısı analizi
    from collections import defaultdict
    
    # Müşteri başına randevu sayısı dağılımı
    randevu_sayisi_dagilimi = defaultdict(int)
    for m in musteriler:
        randevu_sayisi = musteri_id_to_randevu_adet.get(m.MusteriID, 0)
        randevu_sayisi_dagilimi[randevu_sayisi] += 1
    
    # En çok randevu alan müşteriler (top 10)
    en_cok_randevu_alan = []
    for m in musteriler:
        randevu_sayisi = musteri_id_to_randevu_adet.get(m.MusteriID, 0)
        if randevu_sayisi > 0:
            en_cok_randevu_alan.append({
                'musteri_adi': f"{m.MusteriAdi} {m.MusteriSoyadi}",
                'randevu_sayisi': randevu_sayisi
            })
    
    # Randevu sayısına göre sırala (azalan)
    en_cok_randevu_alan.sort(key=lambda x: x['randevu_sayisi'], reverse=True)
    en_cok_randevu_alan = en_cok_randevu_alan[:10]
    
    # Randevu sıklığı analizi (0, 1, 2-5, 6-10, 10+ randevu)
    randevu_siklik_dagilimi = {
        '0 Randevu': 0,
        '1 Randevu': 0,
        '2-5 Randevu': 0,
        '6-10 Randevu': 0,
        '10+ Randevu': 0
    }
    
    for m in musteriler:
        randevu_sayisi = musteri_id_to_randevu_adet.get(m.MusteriID, 0)
        if randevu_sayisi == 0:
            randevu_siklik_dagilimi['0 Randevu'] += 1
        elif randevu_sayisi == 1:
            randevu_siklik_dagilimi['1 Randevu'] += 1
        elif 2 <= randevu_sayisi <= 5:
            randevu_siklik_dagilimi['2-5 Randevu'] += 1
        elif 6 <= randevu_sayisi <= 10:
            randevu_siklik_dagilimi['6-10 Randevu'] += 1
        else:
            randevu_siklik_dagilimi['10+ Randevu'] += 1
    
    return render_template(
        'rapor_musteriler.html',
        rows=rows,
        toplam_musteri=toplam_musteri,
        aktif_musteri=aktif_musteri,
        yeni_musteri=yeni_musteri,
        top_musteriler=top_musteriler,
        kategoriler=kategoriler,
        sehir_listesi=sehir_listesi,
        ilce_listesi=ilce_listesi,
        gender_data=gender_data,
        age_groups=age_groups,
        category_data=category_data,
        city_data=city_data,
        monthly_data=monthly_data,
        weekly_data=weekly_data,
        randevu_sayisi_dagilimi=dict(randevu_sayisi_dagilimi),
        en_cok_randevu_alan=en_cok_randevu_alan,
        randevu_siklik_dagilimi=randevu_siklik_dagilimi,
        filtreler={
            'kategori_id': kategori_id or '',
            'aktif': sadece_aktif,
            'iletisim_var': iletisim_var or '',
            'yas_min': yas_min or '',
            'yas_max': yas_max or '',
            'cinsiyet': cinsiyet or '',
            'dogum_tarihi': dogum_tarihi or '',
            'sehir': sehir or '',
            'ilce': ilce or ''
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
                musteri_cinsiyet = request.form.get('musteri_cinsiyet', '').strip()
                
                # Doğum tarihi ve yaş güncelleme
                dogum_tarihi = request.form.get('musteri_dogum_tarihi')
                if dogum_tarihi:
                    randevu.musteri.DogumTarihi = datetime.strptime(dogum_tarihi, '%Y-%m-%d').date()
                    # Yaşı hesapla
                    bugun = datetime.now().date()
                    yas = bugun.year - randevu.musteri.DogumTarihi.year
                    if (bugun.month, bugun.day) < (randevu.musteri.DogumTarihi.month, randevu.musteri.DogumTarihi.day):
                        yas -= 1
                    randevu.musteri.Yas = yas
                elif request.form.get('musteri_yas'):
                    randevu.musteri.Yas = request.form.get('musteri_yas', type=int)
                
                if tam_telefon:
                    randevu.musteri.Telefon = tam_telefon
                if musteri_email:
                    randevu.musteri.Email = musteri_email
                if musteri_cinsiyet:
                    randevu.musteri.Cinsiyet = musteri_cinsiyet
                
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

        # Çakışan randevu ve blok kontrolü - Optimistic Locking ile güçlendirilmiş
        randevu_bas = randevu_dt
        randevu_bit = randevu_dt + timedelta(minutes=randevu_suresi)

        # 1) Mevcut randevularla çakışma kontrolü (Optimistic Locking)
        day_start_chk = datetime(randevu_dt.year, randevu_dt.month, randevu_dt.day, 0, 0)
        day_end_chk = day_start_chk + timedelta(days=1)
        
        # İlk kontrol - genel çakışma
        existing_for_defter = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID == defter_id,
            Randevu.RandevuTarihi >= day_start_chk,
            Randevu.RandevuTarihi < day_end_chk,
            Randevu.Durum != 'Iptal'  # İptal edilen randevuları hariç tut
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
            
            # Müşteri bilgilerini güncelle
            musteri.Sehir = request.form.get('musteri_sehir', '') or musteri.Sehir
            musteri.Ilce = request.form.get('musteri_ilce', '') or musteri.Ilce
            musteri.Adres = request.form.get('musteri_adres', '') or musteri.Adres
            musteri.Cinsiyet = request.form.get('musteri_cinsiyet', '') or musteri.Cinsiyet
            musteri.KategoriID = request.form.get('musteri_kategori', type=int) or musteri.KategoriID
            musteri.Notlar = request.form.get('musteri_notlar', '') or musteri.Notlar
            
            # Doğum tarihi ve yaş güncelleme
            dogum_tarihi = request.form.get('musteri_dogum_tarihi')
            if dogum_tarihi:
                musteri.DogumTarihi = datetime.strptime(dogum_tarihi, '%Y-%m-%d').date()
                # Yaşı hesapla
                bugun = datetime.now().date()
                yas = bugun.year - musteri.DogumTarihi.year
                if (bugun.month, bugun.day) < (musteri.DogumTarihi.month, musteri.DogumTarihi.day):
                    yas -= 1
                musteri.Yas = yas
            elif request.form.get('musteri_yas'):
                musteri.Yas = request.form.get('musteri_yas', type=int)
            
            db.session.commit()
        else:
            # Telefon numarasını ülke kodu ile birleştir
            telefon_ulke_kodu = request.form.get('telefon_ulke_kodu', '+90')
            telefon_numara = request.form.get('musteri_telefon', '').replace(' ', '')
            tam_telefon = f"{telefon_ulke_kodu}{telefon_numara}" if telefon_numara else ''
            
            # Doğum tarihi ve yaş hesaplama
            dogum_tarihi = request.form.get('musteri_dogum_tarihi')
            yas = None
            if dogum_tarihi:
                dogum_tarihi_obj = datetime.strptime(dogum_tarihi, '%Y-%m-%d').date()
                # Yaşı hesapla
                bugun = datetime.now().date()
                yas = bugun.year - dogum_tarihi_obj.year
                if (bugun.month, bugun.day) < (dogum_tarihi_obj.month, dogum_tarihi_obj.day):
                    yas -= 1
            elif request.form.get('musteri_yas'):
                yas = request.form.get('musteri_yas', type=int)
            
            # Yeni müşteri oluştur
            musteri = Musteri(
                FirmaID=session['firma_id'],
                MusteriAdi=request.form['musteri_adi'],
                MusteriSoyadi=request.form.get('musteri_soyadi', 'Müşteri'),
                Telefon=tam_telefon,
                Email=request.form.get('musteri_email', ''),
                # Yeni adres alanları
                Ulke=request.form.get('musteri_ulke', 'Türkiye'),
                Sehir=request.form.get('musteri_sehir', ''),
                Ilce=request.form.get('musteri_ilce', ''),
                Adres=request.form.get('musteri_adres', ''),
                Cinsiyet=request.form.get('musteri_cinsiyet', ''),
                KategoriID=request.form.get('musteri_kategori', type=int) or None,
                Notlar=request.form.get('musteri_notlar', ''),
                DogumTarihi=dogum_tarihi_obj if dogum_tarihi else None,
                Yas=yas
            )
            db.session.add(musteri)
            db.session.flush()  # ID'yi almak için
            musteri_id = musteri.MusteriID

        # OPTIMISTIC LOCKING: Randevu oluşturmadan hemen önce son kontrol
        # Bu, eş zamanlı randevu oluşturma girişimlerini engeller
        final_check = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID == defter_id,
            Randevu.RandevuTarihi >= day_start_chk,
            Randevu.RandevuTarihi < day_end_chk,
            Randevu.Durum != 'Iptal'
        ).all()
        
        for r in final_check:
            r_start = r.RandevuTarihi
            r_dur = r.RandevuSuresi or 60
            r_end = r_start + timedelta(minutes=int(r_dur))
            if r_start < randevu_bit and randevu_bas < r_end:
                flash('Bu slot başka bir kullanıcı tarafından rezerve edildi. Lütfen başka bir saat seçin.', 'error')
                return redirect(url_for('randevu_ekle'))

        randevu = Randevu(
            RandevuBaslik=(ref.Ad if ref else 'Yok'),
            RandevuAciklamasi=request.form['aciklama'],
            RandevuTarihi=randevu_dt,
            RandevuSuresi=randevu_suresi,
            MusteriAdi=request.form['musteri_adi'],
            MusteriSoyadi=request.form.get('musteri_soyadi', 'Müşteri'),
            MusteriTelefon=request.form.get('musteri_telefon', ''),
            MusteriEmail=request.form.get('musteri_email', ''),
            MusteriID=musteri_id,  # Müşteri ID'sini ekle
            IslemID=islem_id,  # İşlem ID'sini ekle
            OlusturanKullaniciID=session['user_id'],
            FirmaID=session['firma_id'],
            DefterID=defter_id  # Defter ID'sini ekle
        )
        
        try:
            db.session.add(randevu)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Randevu oluşturulurken bir hata oluştu. Lütfen tekrar deneyin.', 'error')
            return redirect(url_for('randevu_ekle'))

        # SMS: randevu olusturuldugunda gonder
        try:
            sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).first()
            if sms_ayar and sms_ayar.SMSGonderOnCreate and randevu.MusteriTelefon:
                sms_text = (sms_ayar.VarsayilanSMSMetni or "Merhaba {MUSTERI_ADI}, {RANDEVU_TARIH} tarihindeki randevunuzu hatırlatırız.")
                # Ad + Soyad birlestir
                try:
                    if randevu.musteri and randevu.musteri.MusteriSoyadi:
                        full_name = f"{randevu.musteri.MusteriAdi} {randevu.musteri.MusteriSoyadi}".strip()
                    else:
                        full_name = (randevu.MusteriAdi or '').strip()
                except Exception:
                    full_name = (randevu.MusteriAdi or '').strip()

                sms_text = sms_text.replace('{MUSTERI_ADI}', full_name or '-')\
                                   .replace('{RANDEVU_TARIH}', randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M'))
                # Defter adi
                try:
                    defter_adi = randevu.defter.DefterAdi if randevu.defter else ''
                except Exception:
                    defter_adi = ''
                sms_text = sms_text.replace('{DEFTER_ADI}', defter_adi)
                send_sms_with_firma_settings(session['firma_id'], randevu.MusteriTelefon, sms_text)
        except Exception as e:
            print(f"Randevu olusturuldu SMS gonderim hatasi: {e}")

        # SMS: 24 saat once hatirlatma kaydi
        try:
            sms_ayar = sms_ayar or FirmaSMSAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).first()
            if sms_ayar and sms_ayar.SMSGonder24SaatOnce and randevu.MusteriTelefon:
                s = RandevuSMSHatirlatma(
                    RandevuID=randevu.RandevuID,
                    FirmaID=session['firma_id'],
                    RecipientPhone=randevu.MusteriTelefon,
                    MinutesBefore=1440
                )
                db.session.add(s)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"SMS hatirlatma kaydi olusurken hata: {e}")

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
        
        # WhatsApp mesajı gönder (eğer ayar aktifse)
        try:
            whatsapp_ayar = FirmaWhatsAppAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).first()
            if whatsapp_ayar and whatsapp_ayar.MesajGonderOnCreate and whatsapp_ayar.RandevuOlusturmaMesaji:
                # Telefon numarasını temizle (sadece rakamlar)
                phone_clean = ''.join(filter(str.isdigit, randevu.MusteriTelefon))
                if phone_clean and len(phone_clean) >= 10:
                    # Mesaj şablonunu değişkenlerle doldur
                    message = whatsapp_ayar.RandevuOlusturmaMesaji
                    message = message.replace('{musteri_adi}', randevu.MusteriAdi or 'Müşteri')
                    message = message.replace('{tarih}', randevu_dt.strftime('%d.%m.%Y'))
                    message = message.replace('{saat}', randevu_dt.strftime('%H:%M'))
                    message = message.replace('{defter}', defter_ayar.DefterAdi)
                    message = message.replace('{referans}', randevu.Referans.Ad if randevu.Referans else 'Yok')
                    
                    # WhatsApp mesajı gönder
                    success, result = send_whatsapp_message(phone_clean, message, session['firma_id'])
                    if not success:
                        print(f"WhatsApp mesajı gönderilemedi: {result}")
        except Exception as e:
            print(f"WhatsApp mesajı gönderme hatası: {str(e)}")
        
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
    
    # Eğer randevu iptal edildiyse, slot'u açık hale getir
    if yeni_durum == 'Iptal':
        # Randevu iptal edildiğinde slot artık kullanılabilir
        # Bu durumda slot API'si otomatik olarak bu slot'u açık gösterecek
        pass
    
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
    defter_id = request.args.get('defter_id', type=int)
    week_start_param = request.args.get('week_start')  # YYYY-MM-DD (Pazartesi)
    
    # Tarih aralığı hesapla
    if view_type == 'month':
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
    else:  # week
        # Haftanın başlangıcı parametreden ya da bugüne göre Pazartesi
        if week_start_param:
            try:
                ws = datetime.strptime(week_start_param, '%Y-%m-%d')
            except ValueError:
                ws = datetime.now()
        else:
            ws = datetime.now()
        days_since_monday = ws.weekday()
        start_date = ws - timedelta(days=days_since_monday)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)
    
    # Kullanıcının yetkili olduğu defterleri getir
    if session.get('is_admin', False):
        # Admin kullanıcılar tüm defterleri görebilir
        defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
    else:
        # Normal kullanıcılar sadece yetkili oldukları randevuların defterlerini görebilir
        from sqlalchemy import distinct
        yetkili_defter_ids = db.session.query(distinct(Randevu.DefterID)).join(RandevuYetki).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id']
        ).all()
        
        # Yetkili defter ID'lerini liste olarak al
        defter_id_list = [defter_id[0] for defter_id in yetkili_defter_ids if defter_id[0] is not None]
        
        if defter_id_list:
            defterler = RandevuDefterAyar.query.filter(
                RandevuDefterAyar.AyarID.in_(defter_id_list),
                RandevuDefterAyar.FirmaID == session['firma_id'],
                RandevuDefterAyar.Aktif == True
            ).all()
        else:
            # Eğer hiç yetkili defter yoksa boş liste
            defterler = []
    
    # Eğer defter seçilmemişse:
    # - Aylık görünümde: tüm defterler gösterilir
    # - Haftalık görünümde: ilk defter seçili gelir
    if not defter_id and view_type == 'week' and defterler:
        defter_id = defterler[0].AyarID
    
    # Randevuları getir (iptal edilen randevular hariç) - işlem bilgisi ile birlikte
    if session.get('is_admin', False):
        query = db.session.query(Randevu, RandevuIslem).outerjoin(RandevuIslem, Randevu.IslemID == RandevuIslem.IslemID).filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_date,
            Randevu.RandevuTarihi < end_date,
            Randevu.Durum != 'Iptal'  # İptal edilen randevuları hariç tut
        )
        if defter_id:
            query = query.filter(Randevu.DefterID == defter_id)
        results = query.order_by(Randevu.RandevuTarihi).all()
        # Randevu ve işlem bilgilerini birleştir
        randevular = []
        for randevu, islem in results:
            randevu.islem_adi = islem.IslemAdi if islem else None
            randevular.append(randevu)
    else:
        query = db.session.query(Randevu, RandevuIslem).join(RandevuYetki).outerjoin(RandevuIslem, Randevu.IslemID == RandevuIslem.IslemID).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_date,
            Randevu.RandevuTarihi < end_date,
            Randevu.Durum != 'Iptal'  # İptal edilen randevuları hariç tut
        )
        if defter_id:
            query = query.filter(Randevu.DefterID == defter_id)
        results = query.order_by(Randevu.RandevuTarihi).all()
        # Randevu ve işlem bilgilerini birleştir
        randevular = []
        for randevu, islem in results:
            randevu.islem_adi = islem.IslemAdi if islem else None
            randevular.append(randevu)
    
    # Haftalık görünüm için başlık ve gezinme verileri
    week_start_str = start_date.strftime('%Y-%m-%d') if view_type == 'week' else None
    prev_week_start = (start_date - timedelta(days=7)).strftime('%Y-%m-%d') if view_type == 'week' else None
    next_week_start = (start_date + timedelta(days=7)).strftime('%Y-%m-%d') if view_type == 'week' else None
    if view_type == 'week':
        week_end_display = (end_date - timedelta(days=1))
        # Dil kontrolü
        current_lang = session.get('language', 'tr')
        if current_lang == 'en':
            # İngilizce ay isimleri
            english_months = {
                1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
            }
            start_month = english_months[start_date.month]
            end_month = english_months[week_end_display.month]
        else:
            # Türkçe ay isimleri
            turkish_months = {
                1: 'Oca', 2: 'Şub', 3: 'Mar', 4: 'Nis', 5: 'May', 6: 'Haz',
                7: 'Tem', 8: 'Ağu', 9: 'Eyl', 10: 'Eki', 11: 'Kas', 12: 'Ara'
            }
            start_month = turkish_months[start_date.month]
            end_month = turkish_months[week_end_display.month]
        
        week_range_title = f"{start_date.day} {start_month} {start_date.year} - {week_end_display.day} {end_month} {week_end_display.year}"
    else:
        week_range_title = None

    return render_template('takvim.html', 
                         randevular=randevular, 
                         year=year, 
                         month=month, 
                         view_type=view_type,
                         start_date=start_date,
                         end_date=end_date,
                         datetime=datetime,
                         timedelta=timedelta,
                         defterler=defterler,
                         selected_defter_id=defter_id,
                         week_start_str=week_start_str,
                         prev_week_start=prev_week_start,
                         next_week_start=next_week_start,
                         week_range_title=week_range_title)

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
    
    # Hedef defter bilgisine göre slot'a yapıştır
    try:
        defter_ayar = RandevuDefterAyar.query.get(randevu.DefterID)
        slot_dk = (defter_ayar.SlotDakika if defter_ayar and defter_ayar.SlotDakika else 30)
        # minute'i slot basamağına yuvarla (aşağı)
        yeni_dt = yeni_dt.replace(minute=(yeni_dt.minute // slot_dk) * slot_dk, second=0, microsecond=0)
    except Exception as e:
        print(f"Slot yuvarlama hatası: {e}")

    # Çakışma kontrolü (aynı defter için) - Optimistic Locking ile güçlendirilmiş
    randevu_suresi = randevu.RandevuSuresi or 60
    bitis_tarihi = yeni_dt + timedelta(minutes=randevu_suresi)
    
    # Mevcut randevuları kontrol et (iptal edilenleri hariç tut)
    mevcut_randevular = Randevu.query.filter(
        Randevu.FirmaID == session['firma_id'],
        Randevu.DefterID == randevu.DefterID,
        Randevu.RandevuID != randevu_id,
        Randevu.Durum != 'Iptal'  # İptal edilen randevuları hariç tut
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
    
    # Tarihi güncelle - Optimistic Locking ile korumalı
    try:
        eski_tarih = randevu.RandevuTarihi
        randevu.RandevuTarihi = yeni_dt
        db.session.commit()
        print(f"Randevu {randevu_id} başarıyla taşındı")
    except Exception as e:
        db.session.rollback()
        print(f"Randevu taşıma hatası: {e}")
        return jsonify({"success": False, "message": "Randevu taşınırken bir hata oluştu"}), 500

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
        Randevu.RandevuTarihi < day_end,
        Randevu.Durum != 'iptal'  # İptal edilen randevuları hariç tut
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

# API: Slot müsaitlik kontrolü (Real-time UI feedback için)
@app.route('/api/slot/check', methods=['POST'])
@login_required
def api_slot_check():
    """Belirli bir slot'un müsait olup olmadığını kontrol eder"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Geçersiz veri"}), 400
        
        tarih_str = data.get('tarih')
        saat_str = data.get('saat')
        defter_id = int(data.get('defter_id', 0))
        randevu_suresi = int(data.get('sure', 60))
        exclude_randevu_id = int(data.get('exclude_randevu_id', 0)) if data.get('exclude_randevu_id') else None  # Düzenleme sırasında kendi randevusunu hariç tut
        
        if not tarih_str or not saat_str or not defter_id:
            return jsonify({"success": False, "message": "Eksik parametreler"}), 400
        
        # Tarih/saat parse et
        try:
            randevu_dt = datetime.strptime(f"{tarih_str} {saat_str}", '%Y-%m-%d %H:%M')
        except ValueError:
            return jsonify({"success": False, "message": "Geçersiz tarih/saat formatı"}), 400
        
        # Geçmiş tarih kontrolü
        if randevu_dt < datetime.now():
            return jsonify({"success": False, "available": False, "message": "Geçmiş tarih/saat"}), 200
        
        # Defter kontrolü
        defter_ayar = RandevuDefterAyar.query.filter_by(
            AyarID=defter_id, 
            FirmaID=session['firma_id'], 
            Aktif=True
        ).first()
        if not defter_ayar:
            return jsonify({"success": False, "message": "Defter bulunamadı"}), 400
        
        # Süre validation
        if randevu_suresi % defter_ayar.SlotDakika != 0:
            return jsonify({"success": False, "available": False, "message": f"Süre {defter_ayar.SlotDakika} dakikanın katları olmalı"}), 200
        
        # Çakışma kontrolü
        randevu_bas = randevu_dt
        randevu_bit = randevu_dt + timedelta(minutes=randevu_suresi)
        
        day_start = datetime(randevu_dt.year, randevu_dt.month, randevu_dt.day, 0, 0)
        day_end = day_start + timedelta(days=1)
        
        # Mevcut randevuları kontrol et
        query = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID == defter_id,
            Randevu.RandevuTarihi >= day_start,
            Randevu.RandevuTarihi < day_end,
            Randevu.Durum != 'Iptal'
        )
        
        if exclude_randevu_id:
            query = query.filter(Randevu.RandevuID != exclude_randevu_id)
        
        existing_randevular = query.all()
        
        for r in existing_randevular:
            r_start = r.RandevuTarihi
            r_dur = r.RandevuSuresi or 60
            r_end = r_start + timedelta(minutes=int(r_dur))
            if r_start < randevu_bit and randevu_bas < r_end:
                return jsonify({
                    "success": True, 
                    "available": False, 
                    "message": "Bu saatte mevcut randevu var",
                    "conflicting_appointment": {
                        "id": r.RandevuID,
                        "title": r.RandevuBaslik,
                        "start": r_start.strftime('%H:%M'),
                        "end": r_end.strftime('%H:%M'),
                        "customer": f"{r.MusteriAdi} {r.MusteriSoyadi or ''}".strip()
                    }
                }), 200
        
        # Blok kontrolü
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
                if not b.SaatBaslangic or not b.SaatBitis:
                    return True
                try:
                    bh, bm = map(int, b.SaatBaslangic.split(':'))
                    ehh, emm = map(int, b.SaatBitis.split(':'))
                except:
                    continue
                b_start = datetime(gun.year, gun.month, gun.day, bh, bm)
                b_end = datetime(gun.year, gun.month, gun.day, ehh, emm)
                if b_start < bit and bas < b_end:
                    return True
            return False
        
        if is_blocked_interval(randevu_bas, randevu_bit):
            return jsonify({
                "success": True, 
                "available": False, 
                "message": "Bu saat aralığı bloklu"
            }), 200
        
        return jsonify({
            "success": True, 
            "available": True, 
            "message": "Slot müsait"
        }), 200
        
    except Exception as e:
        import traceback
        print(f"Slot kontrol hatası: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "message": f"Sunucu hatası: {str(e)}"}), 500

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

    # Kapasite ve defter parametrelerini al
    kapasite = request.args.get('kapasite', '8')
    defter_id = request.args.get('defter_id', '')
    print(f"Form parametreleri - defter_id: '{defter_id}', kapasite: '{kapasite}'")
    
    # Defter listesini al
    defterler = RandevuDefterAyar.query.filter(
        RandevuDefterAyar.FirmaID == session['firma_id'],
        RandevuDefterAyar.Aktif == True
    ).all()
    print(f"Bulunan defter sayısı: {len(defterler)}")
    for defter in defterler:
        print(f"Defter: {defter.DefterAdi} (ID: {defter.AyarID})")
    
    return render_template('raporlar.html', 
                         baslangic=start_date.strftime('%Y-%m-%d'), 
                         bitis=end_date.strftime('%Y-%m-%d'),
                         kapasite=kapasite,
                         defter_id=defter_id,
                         defterler=defterler)


# Raporlar API - Ozet
@app.route('/api/raporlar/ozet')
@login_required
def api_raporlar_ozet():
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    defter_id = request.args.get('defter_id', '')
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
    
    # Defter filtresi ekle (Randevu.DefterID üzerinden)
    if defter_id:
        print(f"API Ozet - Defter filtresi uygulanıyor: {defter_id}")
        
        # Debug: Mevcut randevuları kontrol et
        all_randevular = q.all()
        print(f"DEBUG: Filtre öncesi toplam randevu: {len(all_randevular)}")
        
        # Debug: İlk randevunun DefterID'sini kontrol et
        if all_randevular:
            first_randevu = all_randevular[0]
            print(f"DEBUG: İlk randevu DefterID: {first_randevu.DefterID}")
        
        # Debug: DefterID=5 olan randevuları kontrol et
        defter_randevular = q.filter(Randevu.DefterID == defter_id).all()
        print(f"DEBUG: DefterID={defter_id} olan randevu sayısı: {len(defter_randevular)}")
        
        q = q.filter(Randevu.DefterID == defter_id)
    else:
        print("API Ozet - Defter filtresi uygulanmıyor")

    items = q.all()
    print(f"API Ozet - Toplam {len(items)} randevu bulundu")

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

# Yoğun Saatler Raporu API
@app.route('/api/raporlar/yoğun-saatler')
@login_required
def api_raporlar_yogun_saatler():
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    kapasite = int(request.args.get('kapasite', 8))  # Varsayılan günlük kapasite 8
    defter_id = request.args.get('defter_id', '')
    
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
    
    # Defter filtresi ekle (Randevu.DefterID üzerinden)
    if defter_id:
        print(f"API Yogun Saatler - Defter filtresi uygulanıyor: {defter_id}")
        q = q.filter(Randevu.DefterID == defter_id)
    else:
        print("API Yogun Saatler - Defter filtresi uygulanmıyor")

    items = q.all()

    # Saatlik dağılım
    saat_counter = defaultdict(int)
    for r in items:
        saat_counter[r.RandevuTarihi.hour] += 1
    
    # 0-23 saat arası tüm saatler
    saatler = list(range(0, 24))
    saat_deger = [saat_counter.get(h, 0) for h in saatler]
    
    # En yoğun saat
    max_appointments = max(saat_deger) if saat_deger else 0
    peak_hour = saatler[saat_deger.index(max_appointments)] if max_appointments > 0 else 0
    
    # Ortalama kapasite kullanımı
    total_days = (end_date - start_date).days + 1
    total_possible_appointments = total_days * kapasite
    total_actual_appointments = len(items)
    avg_capacity_usage = (total_actual_appointments / total_possible_appointments * 100) if total_possible_appointments > 0 else 0
    
    # Verimlilik oranı (yoğun saatlerdeki verimlilik)
    peak_hours = [h for h in saatler if saat_counter.get(h, 0) >= max_appointments * 0.8]
    peak_hours_appointments = sum(saat_counter.get(h, 0) for h in peak_hours)
    efficiency_rate = (peak_hours_appointments / total_actual_appointments * 100) if total_actual_appointments > 0 else 0
    
    # Haftalık dağılım
    weekly_counter = defaultdict(int)
    for r in items:
        week_start = r.RandevuTarihi.date() - timedelta(days=r.RandevuTarihi.weekday())
        weekly_counter[week_start] += 1
    
    # Son 12 hafta
    weekly_labels = []
    weekly_values = []
    for i in range(12):
        week_start = end_date - timedelta(weeks=i)
        week_start = week_start - timedelta(days=week_start.weekday())
        weekly_labels.insert(0, week_start.strftime('%d/%m'))
        weekly_values.insert(0, weekly_counter.get(week_start, 0))
    
    # Saatlik verimlilik
    hourly_efficiency = []
    for h in saatler:
        hour_appointments = saat_counter.get(h, 0)
        hour_efficiency = (hour_appointments / max_appointments * 100) if max_appointments > 0 else 0
        hourly_efficiency.append(round(hour_efficiency, 1))

    return jsonify({
        "success": True,
        "peakHour": peak_hour,
        "avgCapacityUsage": round(avg_capacity_usage, 1),
        "efficiencyRate": round(efficiency_rate, 1),
        "hourlyData": {
            "labels": [f"{h:02d}" for h in saatler],
            "values": saat_deger
        },
        "weeklyData": {
            "labels": weekly_labels,
            "values": weekly_values
        },
        "hourlyEfficiency": hourly_efficiency
    })

@app.route('/api/raporlar/heatmap')
@login_required
def api_raporlar_heatmap():
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    defter_id = request.args.get('defter_id', '')
    
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
    
    # Defter filtresi ekle (Randevu.DefterID üzerinden)
    if defter_id:
        print(f"API Heatmap - Defter filtresi uygulanıyor: {defter_id}")
        q = q.filter(Randevu.DefterID == defter_id)
    else:
        print("API Heatmap - Defter filtresi uygulanmıyor")

    items = q.all()

    # Günlük ve saatlik dağılım
    heatmap_data = {
        'Monday': {},
        'Tuesday': {},
        'Wednesday': {},
        'Thursday': {},
        'Friday': {},
        'Saturday': {},
        'Sunday': {}
    }
    
    # Gün isimleri
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for r in items:
        # Gün adını al (0=Monday, 6=Sunday)
        day_name = day_names[r.RandevuTarihi.weekday()]
        hour = r.RandevuTarihi.hour
        
        # Sadece çalışma saatleri (9-18)
        if 9 <= hour <= 18:
            if hour not in heatmap_data[day_name]:
                heatmap_data[day_name][hour] = 0
            heatmap_data[day_name][hour] += 1
    
    return jsonify({
        "success": True,
        "heatmapData": heatmap_data
    })

# Personel Performans Raporu API
@app.route('/api/raporlar/personel-performans')
@login_required
def api_raporlar_personel_performans():
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    defter_id = request.args.get('defter_id', '')

    try:
        start_date = datetime.strptime(baslangic, '%Y-%m-%d').date() if baslangic else (datetime.now().date() - timedelta(days=30))
        end_date = datetime.strptime(bitis, '%Y-%m-%d').date() if bitis else datetime.now().date()
    except ValueError:
        return jsonify({"success": False, "message": "Tarih formatı YYYY-MM-DD olmalı"}), 400

    start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    # İzin farkındalığı
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

    if defter_id:
        q = q.filter(Randevu.DefterID == defter_id)

    items = q.all()

    # Personel bazında grupla
    performance = {}
    for r in items:
        user_id = r.OlusturanKullaniciID
        if user_id not in performance:
            performance[user_id] = {
                'kullaniciId': user_id,
                'adSoyad': f"{r.olusturan_kullanici.Ad} {r.olusturan_kullanici.Soyad}" if r.olusturan_kullanici else 'Bilinmiyor',
                'toplam': 0,
                'durumlar': defaultdict(int)
            }
        performance[user_id]['toplam'] += 1
        durum = r.Durum or 'Bilinmiyor'
        performance[user_id]['durumlar'][durum] += 1

    # Sonuçları listeye çevir ve toplam sayıya göre sırala
    rows = []
    for _, info in performance.items():
        rows.append({
            'kullaniciId': info['kullaniciId'],
            'adSoyad': info['adSoyad'],
            'toplam': info['toplam'],
            'beklemede': info['durumlar'].get('Beklemede', 0),
            'tamamlandi': info['durumlar'].get('Tamamlandı', 0),
            'iptal': info['durumlar'].get('İptal', 0) + info['durumlar'].get('Iptal', 0)
        })
    rows.sort(key=lambda x: x['toplam'], reverse=True)

    labels = [r['adSoyad'] for r in rows]
    counts = [r['toplam'] for r in rows]

    return jsonify({
        'success': True,
        'labels': labels,
        'counts': counts,
        'rows': rows
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
            'cinsiyet': musteri.Cinsiyet or '',
            'ulke': musteri.Ulke or 'TR',
            'sehir': musteri.Sehir or '',
            'ilce': musteri.Ilce or '',
            'adres': musteri.Adres or '',
            'notlar': musteri.Notlar or '',
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
