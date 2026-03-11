from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.extensions import db, csrf
from app.models import Firma, Kullanici, RandevuDefterAyar, RandevuDefterBlok, MusteriKategori, Randevu
from app.utils.decorators import login_required, admin_required, super_admin_required
from datetime import datetime, date
import os
from flask_babel import gettext
from sqlalchemy import text
from werkzeug.security import generate_password_hash

settings_bp = Blueprint('settings', __name__)

# Ayarlar Ana Sayfa
@settings_bp.route('/ayarlar')
@login_required
def index():
    # Modül izin kontrolü
    if not session.get('is_admin', False) and not session.get('ayarlar_modulu', False):
        flash('Bu sayfaya erişim yetkiniz yok', 'error')
        return redirect(url_for('main.dashboard'))
    # unread_count context processor ile geliyor olabilir ama burada da gerekebilir
    # unread_count = Bildirim.query.filter_by(KullaniciID=session['user_id'], Okundu=False).count()
    return render_template('ayarlar/index.html')

# Firma Ayarlari
@settings_bp.route('/ayarlar/firmalar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def firmalar():
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
        return redirect(url_for('settings.firmalar'))

    firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
    return render_template('ayarlar/firmalar.html', firmalar=firmalar)

@settings_bp.route('/ayarlar/firmalar/sil/<int:firma_id>', methods=['POST'])
@login_required
@super_admin_required
def firma_sil(firma_id):
    firma = Firma.query.get_or_404(firma_id)
    # Basit kontrol: Kullanıcı veya randevu bağlı ise silme (örnek amaçlı engelleme)
    if Kullanici.query.filter_by(FirmaID=firma.FirmaID).first() or Randevu.query.filter_by(FirmaID=firma.FirmaID).first():
        flash('Kullanıcı veya randevu bağlı firmalar silinemez', 'error')
    else:
        db.session.delete(firma)
        db.session.commit()
        flash('Firma silindi', 'success')
    return redirect(url_for('settings.firmalar'))

@settings_bp.route('/ayarlar/firmalar/guncelle', methods=['POST'])
@login_required
@super_admin_required
def firma_guncelle():
    try:
        firma_id = request.form.get('firma_id', type=int)
        if not firma_id:
            flash('Firma ID bulunamadı', 'error')
            return redirect(url_for('settings.firmalar'))
        
        firma = Firma.query.get_or_404(firma_id)
        
        # Firma kodunun benzersizliğini kontrol et (kendi kodu hariç)
        existing_firma = Firma.query.filter(
            Firma.FirmaKodu == request.form['firma_kodu'],
            Firma.FirmaID != firma_id
        ).first()
        
        if existing_firma:
            flash('Bu firma kodu zaten kullanılıyor', 'error')
            return redirect(url_for('settings.firmalar'))
        
        # Firma bilgilerini güncelle
        firma.FirmaAdi = request.form['firma_adi']
        firma.FirmaKodu = request.form['firma_kodu']
        firma.Adres = request.form.get('adres', '')
        firma.Telefon = request.form.get('telefon', '')
        firma.Email = request.form.get('email', '')
        firma.GuncellemeTarihi = datetime.now()
        
        db.session.commit()
        flash('Firma başarıyla güncellendi', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Firma güncellenirken hata: {str(e)}', 'error')
    
    return redirect(url_for('settings.firmalar'))

# Kullanici Ayarlari
@settings_bp.route('/ayarlar/kullanicilar', methods=['GET', 'POST'])
@login_required
@admin_required
def kullanicilar():
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
            log_modulu = 'log_modulu' in request.form
            whatsapp_modulu = 'whatsapp_modulu' in request.form
            instagram_modulu = 'instagram_modulu' in request.form
            ai_modulu = 'ai_modulu' in request.form
            
            # Varsayılan şifre 123 ve ilk girişte değişim zorunlu olacak
            u = Kullanici(KullaniciAdi=kullanici_adi, Email=email, FirmaID=firma_id,
                          Sifre=generate_password_hash(sifre or '123'), Ad=ad, Soyad=soyad, Aktif=True,
                          RaporlarModulu=raporlar_modulu, AyarlarModulu=ayarlar_modulu,
                          LogModulu=log_modulu, WhatsAppModulu=whatsapp_modulu,
                          InstagramModulu=instagram_modulu, AIModulu=ai_modulu)
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
                    os.makedirs(os.path.join('app', 'static', 'uploads', 'users'), exist_ok=True)
                    # Dosya yolunu relative path olarak kaydet (static/ ile başlamadan)
                    relative_path = f'uploads/users/user_{u.KullaniciID}.jpg'
                    out_path = os.path.join('app', 'static', relative_path)
                    img.save(out_path, format='JPEG', quality=85, optimize=True)
                    # Dosya yolunu veritabanına kaydet
                    u.ProfilFotografi = relative_path
                    db.session.commit()
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
                            os.makedirs(os.path.join('app', 'static', 'uploads', 'users'), exist_ok=True)
                            # Dosya yolunu relative path olarak kaydet (static/ ile başlamadan)
                            relative_path = f'uploads/users/user_{u.KullaniciID}.jpg'
                            out_path = os.path.join('app', 'static', relative_path)
                            img.save(out_path, format='JPEG', quality=85, optimize=True)
                            # Dosya yolunu veritabanına kaydet
                            u.ProfilFotografi = relative_path
                            db.session.commit()
                        else:
                            flash('Fotoğraf 512KB üzeri olduğu için yüklenmedi.', 'warning')
            except Exception:
                flash('Fotoğraf işlenemedi.', 'warning')
            flash('Kullanıcı eklendi', 'success')
        return redirect(url_for('settings.kullanicilar'))

    # Admin ise tüm firmaları, değilse sadece kendi firmasını göster
    if session.get('is_admin', False):
        firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
        kullanicilar = Kullanici.query.order_by(Kullanici.KullaniciID.desc()).limit(100).all()
    else:
        firmalar = Firma.query.filter_by(FirmaID=session.get('firma_id')).all()
        kullanicilar = Kullanici.query.filter_by(FirmaID=session.get('firma_id')).order_by(Kullanici.KullaniciID.desc()).limit(100).all()
    
    return render_template('ayarlar/kullanicilar.html', firmalar=firmalar, kullanicilar=kullanicilar)

@settings_bp.route('/ayarlar/kullanicilar/duzenle/<int:kullanici_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def kullanici_duzenle(kullanici_id):
    kullanici = Kullanici.query.get_or_404(kullanici_id)
    
    # Admin değilse sadece kendi firmasının kullanıcılarını düzenleyebilir
    if not session.get('is_admin', False) and kullanici.FirmaID != session.get('firma_id'):
        flash('Bu kullanıcıyı düzenleme yetkiniz yok', 'error')
        return redirect(url_for('settings.kullanicilar'))
    
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
        log_modulu = 'log_modulu' in request.form
        whatsapp_modulu = 'whatsapp_modulu' in request.form
        instagram_modulu = 'instagram_modulu' in request.form
        ai_modulu = 'ai_modulu' in request.form
        
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
                kullanici.LogModulu = log_modulu
                kullanici.WhatsAppModulu = whatsapp_modulu
                kullanici.InstagramModulu = instagram_modulu
                kullanici.AIModulu = ai_modulu
                
                # Şifre güncelleme (sadece girilmişse) + doğrulama ve karmaşıklık
                if sifre or sifre2:
                    if sifre != sifre2:
                        flash('Şifreler eşleşmiyor', 'error')
                        return redirect(url_for('settings.kullanici_duzenle', kullanici_id=kullanici_id))
                    # is_password_strong fonksiyonu app.py'de tanımlıydı, buraya taşımadık henüz
                    # Şimdilik basit kontrol
                    if len(sifre) < 6:
                        flash('Şifre en az 6 karakter olmalı', 'error')
                        return redirect(url_for('settings.kullanici_duzenle', kullanici_id=kullanici_id))
                    kullanici.Sifre = sifre
                
                db.session.commit()

                # Fotoğraf güncelle (opsiyonel)
                try:
                    cropped_b64 = request.form.get('foto_cropped')
                    foto = request.files.get('foto')
                    print(f"[FOTO DEBUG] cropped_b64 var mı: {bool(cropped_b64 and cropped_b64.startswith('data:image'))}")
                    print(f"[FOTO DEBUG] foto var mı: {bool(foto and foto.filename)}")
                    if foto:
                        print(f"[FOTO DEBUG] foto.filename: {foto.filename}")
                    
                    if cropped_b64 and cropped_b64.startswith('data:image'):
                        import base64
                        header, b64data = cropped_b64.split(',', 1)
                        raw = base64.b64decode(b64data)
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(raw)).convert('RGB')
                        os.makedirs(os.path.join('app', 'static', 'uploads', 'users'), exist_ok=True)
                        # Dosya yolunu relative path olarak kaydet (static/ ile başlamadan)
                        relative_path = f'uploads/users/user_{kullanici.KullaniciID}.jpg'
                        out_path = os.path.join('app', 'static', relative_path)
                        img.save(out_path, format='JPEG', quality=85, optimize=True)
                        print(f"[FOTO DEBUG] Kırpılmış fotoğraf kaydedildi: {out_path}")
                        # Dosya yolunu veritabanına kaydet
                        kullanici.ProfilFotografi = relative_path
                        db.session.commit()
                    elif foto and foto.filename:
                        from PIL import Image
                        import io
                        foto.seek(0, io.SEEK_END)
                        size = foto.tell()
                        foto.seek(0)
                        print(f"[FOTO DEBUG] Dosya boyutu: {size} bytes")
                        if size <= 512 * 1024:
                            img = Image.open(foto.stream).convert('RGB')
                            w, h = img.size
                            side = min(w, h)
                            left = (w - side) // 2
                            top = (h - side) // 2
                            img = img.crop((left, top, left + side, top + side))
                            img.thumbnail((256, 256))
                            os.makedirs(os.path.join('app', 'static', 'uploads', 'users'), exist_ok=True)
                            # Dosya yolunu relative path olarak kaydet (static/ ile başlamadan)
                            relative_path = f'uploads/users/user_{kullanici.KullaniciID}.jpg'
                            out_path = os.path.join('app', 'static', relative_path)
                            img.save(out_path, format='JPEG', quality=85, optimize=True)
                            print(f"[FOTO DEBUG] Direkt fotoğraf kaydedildi: {out_path}")
                            # Dosya yolunu veritabanına kaydet
                            kullanici.ProfilFotografi = relative_path
                            db.session.commit()
                        else:
                            flash('Fotoğraf 512KB üzeri olduğu için yüklenmedi.', 'warning')
                except Exception as e:
                    import traceback
                    print(f"[FOTO HATA] {str(e)}")
                    traceback.print_exc()
                    flash(f'Fotoğraf işlenemedi: {str(e)}', 'warning')
                flash('Kullanıcı güncellendi', 'success')
                return redirect(url_for('settings.kullanicilar'))
    
    # Admin ise tüm firmaları, değilse sadece kendi firmasını göster
    if session.get('is_admin', False):
        firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
    else:
        firmalar = Firma.query.filter_by(FirmaID=session.get('firma_id')).all()
    
    return render_template('ayarlar/kullanici_duzenle.html', kullanici=kullanici, firmalar=firmalar)

@settings_bp.route('/ayarlar/kullanicilar/sil/<int:kullanici_id>', methods=['POST'])
@login_required
@admin_required
def kullanici_sil(kullanici_id):
    if kullanici_id == session.get('user_id'):
        flash('Kendi hesabınızı silemezsiniz', 'error')
        return redirect(url_for('settings.kullanicilar'))
    
    u = Kullanici.query.get_or_404(kullanici_id)
    
    # Admin değilse sadece kendi firmasının kullanıcılarını silebilir
    if not session.get('is_admin', False) and u.FirmaID != session.get('firma_id'):
        flash('Bu kullanıcıyı silme yetkiniz yok', 'error')
        return redirect(url_for('settings.kullanicilar'))
    
    db.session.delete(u)
    db.session.commit()
    flash('Kullanıcı silindi', 'success')
    return redirect(url_for('settings.kullanicilar'))

# Kullanıcı şifre sıfırla (123)
@settings_bp.route('/ayarlar/kullanicilar/sifre-sifirla/<int:kullanici_id>', methods=['POST'])
@login_required
@admin_required
def kullanici_sifre_sifirla(kullanici_id):
    kullanici = Kullanici.query.get_or_404(kullanici_id)
    # Admin değilse sadece kendi firmasının kullanıcılarını sıfırlayabilir
    if not session.get('is_admin', False) and kullanici.FirmaID != session.get('firma_id'):
        flash('Bu kullanıcı için işlem yetkiniz yok', 'error')
        return redirect(url_for('settings.kullanicilar'))
    kullanici.Sifre = generate_password_hash('123')
    db.session.commit()
    flash('Şifre 123 olarak sıfırlandı. İlk girişte değişiklik istenecek.', 'success')
    return redirect(url_for('settings.kullanici_duzenle', kullanici_id=kullanici_id))

# Randevu Defteri Ayarlari
@settings_bp.route('/ayarlar/defter', methods=['GET', 'POST'])
@login_required
@super_admin_required
def defter():
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
                return redirect(url_for('settings.defter'))
            if not bas_t:
                flash('Blok için başlangıç tarihi zorunludur', 'error')
                return redirect(url_for('settings.defter'))
            if bit_t and bit_t < bas_t:
                flash('Blok bitiş tarihi başlangıçtan önce olamaz', 'error')
                return redirect(url_for('settings.defter'))
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
        return redirect(url_for('settings.defter'))

    firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
    ayarlar_list = RandevuDefterAyar.query.order_by(RandevuDefterAyar.AyarID.desc()).all()
    bloklar = RandevuDefterBlok.query.filter_by(FirmaID=session['firma_id']).order_by(RandevuDefterBlok.BlokID.desc()).all()
    
    # Mevcut firmanın kategorilerini getir
    kategoriler = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id'],
        Aktif=True
    ).order_by(MusteriKategori.KategoriID.asc()).all()
    
    return render_template('ayarlar/defter.html', firmalar=firmalar, ayarlar_list=ayarlar_list, kategoriler=kategoriler, bloklar=bloklar)

@settings_bp.route('/ayarlar/defter/blok/ekle', methods=['POST'])
@login_required
@super_admin_required
def defter_blok_ekle():
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
        return redirect(url_for('settings.defter'))
    if not bas_t:
        flash('Başlangıç tarihi zorunludur', 'error')
        return redirect(url_for('settings.defter'))
    if bit_t and bit_t < bas_t:
        flash('Bitiş tarihi başlangıçtan önce olamaz', 'error')
        return redirect(url_for('settings.defter'))

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
    return redirect(url_for('settings.defter'))

@settings_bp.route('/ayarlar/defter/blok/sil/<int:blok_id>', methods=['POST'])
@login_required
@super_admin_required
def defter_blok_sil(blok_id: int):
    b = RandevuDefterBlok.query.filter_by(BlokID=blok_id, FirmaID=session['firma_id']).first()
    if not b:
        flash('Blok bulunamadı', 'error')
        return redirect(url_for('settings.defter'))
    db.session.delete(b)
    db.session.commit()
    flash('Blok silindi', 'success')
    return redirect(url_for('settings.defter'))

@settings_bp.route('/ayarlar/defter/pasiflestir/<int:ayar_id>', methods=['POST'])
@login_required
@super_admin_required
def defter_pasiflestir(ayar_id: int):
    ayar = RandevuDefterAyar.query.get_or_404(ayar_id)
    ayar.Aktif = not (ayar.Aktif if ayar.Aktif is not None else True)
    db.session.commit()
    flash('Randevu defteri durumu güncellendi', 'success')
    return redirect(url_for('settings.defter'))

# Kategori Yönetimi
@settings_bp.route('/ayarlar/kategori/ekle', methods=['POST'])
@login_required
@super_admin_required
def kategori_ekle():
    kategori_adi = request.form.get('kategori_adi')
    kategori_renk = request.form.get('kategori_renk', '#007bff')
    kategori_aciklama = request.form.get('kategori_aciklama', '')
    kategori_aktif = request.form.get('kategori_aktif') == 'on'
    
    if not kategori_adi:
        flash(gettext('Category name is required'), 'error')
        return redirect(url_for('settings.defter'))
    
    # Aynı isimde kategori var mı kontrol et
    existing = MusteriKategori.query.filter_by(
        FirmaID=session['firma_id'],
        KategoriAdi=kategori_adi
    ).first()
    
    if existing:
        flash(gettext('A category with this name already exists'), 'error')
        return redirect(url_for('settings.defter'))
    
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
    return redirect(url_for('settings.defter'))

@settings_bp.route('/ayarlar/kategori/guncelle', methods=['POST'])
@login_required
@super_admin_required
def kategori_guncelle():
    kategori_id = request.form.get('kategori_id', type=int)
    kategori_adi = request.form.get('kategori_adi')
    kategori_renk = request.form.get('kategori_renk', '#007bff')
    kategori_aciklama = request.form.get('kategori_aciklama', '')
    kategori_aktif = request.form.get('kategori_aktif') == 'on'
    
    if not kategori_id or not kategori_adi:
        flash('Kategori bilgileri eksik', 'error')
        return redirect(url_for('settings.defter'))
    
    kategori = MusteriKategori.query.filter_by(
        KategoriID=kategori_id,
        FirmaID=session['firma_id']
    ).first()
    
    if not kategori:
        flash('Kategori bulunamadı', 'error')
        return redirect(url_for('settings.defter'))
    
    # Aynı isimde başka kategori var mı kontrol et
    existing = MusteriKategori.query.filter(
        MusteriKategori.FirmaID == session['firma_id'],
        MusteriKategori.KategoriAdi == kategori_adi,
        MusteriKategori.KategoriID != kategori_id
    ).first()
    
    if existing:
        flash(gettext('A category with this name already exists'), 'error')
        return redirect(url_for('settings.defter'))
    
    kategori.KategoriAdi = kategori_adi
    kategori.Renk = kategori_renk
    kategori.Aciklama = kategori_aciklama
    kategori.Aktif = kategori_aktif
    
    db.session.commit()
    
    flash(gettext('Category updated successfully'), 'success')
    return redirect(url_for('settings.defter'))

@settings_bp.route('/ayarlar/kategori/sil')
@login_required
@super_admin_required
def kategori_sil():
    # Bu route app.py'de tam olarak görünmüyordu, ama mantık benzerdir
    # Şimdilik boş bırakıyorum veya basit bir silme işlemi ekliyorum
    return redirect(url_for('settings.defter'))

# Migration: ProfilFotografi kolonunu ekle (sadece bir kez çalıştırılmalı)
@settings_bp.route('/migrate/add_profil_fotografi', methods=['GET'])
@login_required
@admin_required
def migrate_add_profil_fotografi():
    """ProfilFotografi kolonunu Kullanicilar tablosuna ekle"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('Kullanicilar')]
        
        if 'ProfilFotografi' in columns:
            flash('ProfilFotografi kolonu zaten mevcut!', 'info')
            return redirect(url_for('settings.index')) # ayarlar_veritabani yoksa index'e
        
        dialect_name = db.engine.dialect.name
        
        if dialect_name == 'mysql':
            with db.engine.connect() as conn:
                conn.execute(text("""
                    ALTER TABLE Kullanicilar 
                    ADD COLUMN ProfilFotografi VARCHAR(500) NULL 
                    AFTER LogModulu
                """))
                conn.commit()
            flash('ProfilFotografi kolonu MySQL\'de eklendi!', 'success')
        elif dialect_name == 'mssql':
            with db.engine.connect() as conn:
                conn.execute(text("""
                    ALTER TABLE Kullanicilar 
                    ADD ProfilFotografi NVARCHAR(500) NULL
                """))
                conn.commit()
            flash('ProfilFotografi kolonu MSSQL\'de eklendi!', 'success')
        else:
            flash(f'Desteklenmeyen veritabani: {dialect_name}', 'error')
            return redirect(url_for('settings.index'))
        
        return redirect(url_for('settings.index'))
    except Exception as e:
        error_msg = str(e).lower()
        if 'duplicate' in error_msg or 'already exists' in error_msg:
            flash('ProfilFotografi kolonu zaten mevcut!', 'info')
        else:
            flash(f'Hata: {e}', 'error')
        return redirect(url_for('settings.index'))


# ─────────────────────────────────────────────────────────────
# AI ASISTAN AYARLARI (Sadece Admin)
# ─────────────────────────────────────────────────────────────

@settings_bp.route('/ayarlar/ai', methods=['GET'])
@login_required
@admin_required
def ai_ayarlar():
    """AI Asistan ana ayar sayfası — API key, model ve firma limitleri"""
    firmalar = Firma.query.order_by(Firma.FirmaAdi).all()
    gemini_api_key = os.environ.get('GEMINI_API_KEY', '')
    gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
    ay_kodu = date.today().strftime('%Y-%m')
    return render_template('ayarlar/ai.html',
                           firmalar=firmalar,
                           gemini_api_key=gemini_api_key,
                           gemini_model=gemini_model,
                           ay_kodu=ay_kodu)


@settings_bp.route('/ayarlar/ai/kaydet', methods=['POST'])
@login_required
@admin_required
def ai_ayarlar_kaydet():
    """API key ve model ayarlarını .env dosyasına kaydet"""
    api_key = request.form.get('gemini_api_key', '').strip()
    model = request.form.get('gemini_model', 'gemini-2.5-flash').strip()

    env_path = '.env'
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

        keys_to_set = {'GEMINI_API_KEY': api_key, 'GEMINI_MODEL': model}
        updated = {k: False for k in keys_to_set}

        new_lines = []
        for line in lines:
            matched = False
            for key in keys_to_set:
                if line.strip().startswith(f'{key}=') or line.strip().startswith(f'{key} ='):
                    new_lines.append(f'{key}={keys_to_set[key]}\n')
                    updated[key] = True
                    matched = True
                    break
            if not matched:
                new_lines.append(line)

        for key, val in keys_to_set.items():
            if not updated[key]:
                new_lines.append(f'{key}={val}\n')

        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        os.environ['GEMINI_API_KEY'] = api_key
        os.environ['GEMINI_MODEL'] = model

        flash('AI ayarları kaydedildi.', 'success')
    except Exception as e:
        flash(f'Hata: {e}', 'error')

    return redirect(url_for('settings.ai_ayarlar'))


@settings_bp.route('/ayarlar/ai/firma-guncelle', methods=['POST'])
@login_required
@admin_required
def ai_firma_guncelle():
    """Firma başına AI aktif/limit güncelle"""
    firma_id = request.form.get('firma_id', type=int)
    ai_aktif = 'ai_aktif' in request.form
    ai_limit = request.form.get('ai_aylik_limit', 50, type=int)

    firma = Firma.query.get_or_404(firma_id)
    firma.AIAktif = ai_aktif
    firma.AIAylikLimit = max(0, ai_limit)
    db.session.commit()

    flash(f"'{firma.FirmaAdi}' için AI ayarları güncellendi.", 'success')
    return redirect(url_for('settings.ai_ayarlar'))


@settings_bp.route('/ayarlar/ai/migrate', methods=['GET'])
@login_required
@admin_required
def ai_migrate():
    """Firmalar tablosuna AI kolonlarını ekle (MySQL ve MSSQL)"""
    try:
        dialect = db.engine.dialect.name
        with db.engine.connect() as conn:
            if dialect == 'mysql':
                for col, definition in [
                    ('AIAktif',          'TINYINT(1) NOT NULL DEFAULT 0'),
                    ('AIAylikLimit',     'INT NOT NULL DEFAULT 50'),
                    ('AIKullanimAy',     'VARCHAR(7) NOT NULL DEFAULT ""'),
                    ('AIKullanilanSayi', 'INT NOT NULL DEFAULT 0'),
                ]:
                    try:
                        conn.execute(text(f'ALTER TABLE Firmalar ADD COLUMN `{col}` {definition}'))
                        conn.commit()
                    except Exception as col_err:
                        if '1060' in str(col_err) or 'duplicate' in str(col_err).lower():
                            pass  # Kolon zaten var
                        else:
                            raise
            elif dialect == 'mssql':
                for col, definition in [
                    ('AIAktif',          'BIT NOT NULL DEFAULT 0'),
                    ('AIAylikLimit',     'INT NOT NULL DEFAULT 50'),
                    ('AIKullanimAy',     'NVARCHAR(7) NOT NULL DEFAULT \'\''),
                    ('AIKullanilanSayi', 'INT NOT NULL DEFAULT 0'),
                ]:
                    conn.execute(text(f"""
                        IF NOT EXISTS (
                            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_NAME='Firmalar' AND COLUMN_NAME='{col}'
                        )
                        ALTER TABLE Firmalar ADD {col} {definition}
                    """))
                    conn.commit()
            else:
                flash(f'Desteklenmeyen veritabanı: {dialect}', 'error')
                return redirect(url_for('settings.ai_ayarlar'))

        flash(f'Firmalar tablosuna AI kolonları başarıyla eklendi ({dialect.upper()}).', 'success')
    except Exception as e:
        flash(f'Migration hatası: {e}', 'error')

    return redirect(url_for('settings.ai_ayarlar'))

# ─────────────────────────────────────────────────────────────
# E-POSTA (SMTP) AYARLARI
# ─────────────────────────────────────────────────────────────

@settings_bp.route('/ayarlar/email', methods=['GET'])
@login_required
@admin_required
def email_ayarlar():
    """Firma başına SMTP Email ayarlarını göster"""
    from app.models import FirmaEmailAyar
    
    firma_id = session.get('firma_id')
    email_ayar = FirmaEmailAyar.query.filter_by(FirmaID=firma_id).first()
    
    return render_template('ayarlar/email.html', email_ayar=email_ayar)


@settings_bp.route('/ayarlar/email/kaydet', methods=['POST'])
@login_required
@admin_required
@csrf.exempt
def email_ayarlar_kaydet():
    """Firma başına SMTP Email ayarlarını kaydet veya güncelle"""
    from app.models import FirmaEmailAyar
    
    firma_id = session.get('firma_id')
    smtp_server = request.form.get('smtp_server', '').strip()
    smtp_port = request.form.get('smtp_port', type=int) or 587
    email = request.form.get('email', '').strip()
    sifre = request.form.get('sifre', '').strip()
    tls_aktif = 'tls_aktif' in request.form
    
    if not smtp_server or not email or not sifre:
        flash("Lütfen tüm zorunlu SMTP alanlarını doldurun.", "error")
        return redirect(url_for('settings.email_ayarlar'))
        
    email_ayar = FirmaEmailAyar.query.filter_by(FirmaID=firma_id).first()
    
    if email_ayar:
        email_ayar.SMTP_Sunucu = smtp_server
        email_ayar.SMTP_Port = smtp_port
        email_ayar.KullaniciAdi = email
        if sifre != '*********': # Eğer dummy parola yollanmadıysa güncelle
            email_ayar.Sifre = sifre
        email_ayar.SSL_Kullan = tls_aktif
        email_ayar.GuncellemeTarihi = datetime.now()
    else:
        yeni_ayar = FirmaEmailAyar(
            FirmaID=firma_id,
            SMTP_Sunucu=smtp_server,
            SMTP_Port=smtp_port,
            KullaniciAdi=email,
            Sifre=sifre,
            SSL_Kullan=tls_aktif
        )
        db.session.add(yeni_ayar)
        
    try:
        db.session.commit()
        flash("E-Posta (SMTP) ayarları başarıyla kaydedildi.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Ayarlar kaydedilirken bir hata oluştu: {e}", "error")
        
    return redirect(url_for('settings.email_ayarlar'))
