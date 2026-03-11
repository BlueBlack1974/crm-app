from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_babel import gettext as _
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db, csrf
from app.models import Kullanici, AktifOturum, Firma, SistemAyar
from app.utils.helpers import get_client_ip
from sqlalchemy import text
from datetime import datetime, timedelta
import secrets

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Her giriş ekranı açılışında olası bekleyen durumları temizle
    if request.method == 'GET':
        for key in list(session.keys()):
            if key.startswith('pending_'):
                session.pop(key, None)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Kullanıcı adı ve şifre gereklidir!', 'error')
            return render_template('login.html')
        
        # Kullanici kontrolu - önce ORM ile dene
        user = None
        try:
            user = Kullanici.query.filter_by(KullaniciAdi=username, Aktif=True).first()
            if user:
                print(f"[DEBUG] Kullanici ORM ile bulundu: {username}")
        except Exception as orm_err:
            print(f"[DEBUG] ORM sorgusu basarisiz: {orm_err}")
            import traceback
            traceback.print_exc()
        
        # ORM başarısız olursa direkt SQL ile dene (tablo ismi küçük harf olabilir)
        if not user:
            try:
                # Dialect kontrolü - sadece MySQL/MSSQL için SQL fallback
                dialect_name = db.engine.dialect.name if hasattr(db.engine, 'dialect') else None
                if dialect_name in ('mysql', 'mssql'):
                    with db.engine.connect() as conn:
                        # Veritabanı bilgilerini göster (sadece MySQL için)
                        if dialect_name == 'mysql':
                            try:
                                current_db = conn.execute(text("SELECT DATABASE()")).scalar()
                                print(f"[DEBUG] Aktif veritabani: {current_db}")
                            except:
                                pass
                        
                        # Tablo ismini bul (küçük/büyük harf farkı olabilir)
                        from sqlalchemy import inspect
                        inspector = inspect(db.engine)
                        tables = inspector.get_table_names()
                        print(f"[DEBUG] Veritabanindaki tablolar ({len(tables)} adet): {sorted(tables)[:10]}...")
                        
                        kullanicilar_table = None
                        for table in tables:
                            if table.lower() == 'kullanicilar':
                                kullanicilar_table = table
                                break
                        
                        print(f"[DEBUG] Kullanicilar tablosu bulundu: {kullanicilar_table}")
                        
                        if kullanicilar_table:
                            # Önce kayıt sayısını kontrol et
                            count = conn.execute(text(f"SELECT COUNT(*) FROM `{kullanicilar_table}`")).scalar()
                            print(f"[DEBUG] Kullanicilar tablosundaki toplam kayit sayisi: {count}")
                            
                            result = conn.execute(text(f"""
                                SELECT KullaniciID, KullaniciAdi, Sifre, Ad, Soyad, Email, FirmaID, Admin, Aktif,
                                       COALESCE(RaporlarModulu, 1) as RaporlarModulu,
                                       COALESCE(AyarlarModulu, 0) as AyarlarModulu,
                                       COALESCE(LogModulu, 0) as LogModulu,
                                       COALESCE(WhatsAppModulu, 0) as WhatsAppModulu,
                                       COALESCE(InstagramModulu, 0) as InstagramModulu
                                FROM `{kullanicilar_table}`
                                WHERE KullaniciAdi = :username AND Aktif = 1
                            """), {"username": username})
                            user_data = result.fetchone()
                            
                            if user_data:
                                print(f"[DEBUG] Kullanici SQL ile bulundu: {username}")
                                # SQLAlchemy Row objesini Kullanici modeline benzer bir objeye dönüştür
                                class UserProxy:
                                    def __init__(self, row_data):
                                        self.KullaniciID = row_data[0]
                                        self.KullaniciAdi = row_data[1]
                                        self.Sifre = row_data[2]
                                        self.Ad = row_data[3]
                                        self.Soyad = row_data[4]
                                        self.Email = row_data[5]
                                        self.FirmaID = row_data[6]
                                        self.Admin = bool(row_data[7])
                                        self.Aktif = bool(row_data[8])
                                        self.RaporlarModulu = bool(row_data[9]) if len(row_data) > 9 else True
                                        self.AyarlarModulu = bool(row_data[10]) if len(row_data) > 10 else False
                                        self.LogModulu = bool(row_data[11]) if len(row_data) > 11 else False
                                        self.WhatsAppModulu = bool(row_data[12]) if len(row_data) > 12 else False
                                        self.InstagramModulu = bool(row_data[13]) if len(row_data) > 13 else False
                                
                                user = UserProxy(user_data)
                            else:
                                print(f"[DEBUG] Kullanici SQL ile bulunamadi: {username}")
                                # Tüm kullanıcıları listele (Aktif filtresi olmadan)
                                all_users = conn.execute(text(f"SELECT KullaniciAdi, Aktif FROM `{kullanicilar_table}`")).fetchall()
                                print(f"[DEBUG] Veritabanindaki tum kullanicilar (Aktif filtresi olmadan): {[u[0] for u in all_users]}")
                                
                                # Aktif olmayan kullanıcıları da kontrol et
                                inactive_user = conn.execute(text(f"""
                                    SELECT KullaniciAdi, Aktif FROM `{kullanicilar_table}` 
                                    WHERE KullaniciAdi = :username
                                """), {"username": username}).fetchone()
                                if inactive_user:
                                    print(f"[DEBUG] Kullanici bulundu ama Aktif={inactive_user[1]}: {username}")
                        else:
                            print(f"[DEBUG] Kullanicilar tablosu bulunamadi!")
                else:
                    print(f"[DEBUG] SQL fallback atlandi - dialect: {dialect_name} (sadece MySQL/MSSQL destekleniyor)")
            except Exception as sql_err:
                print(f"[DEBUG] SQL sorgusu basarisiz: {sql_err}")
                import traceback
                traceback.print_exc()
        
        # Kullanıcı bulunamadıysa hata ver
        if not user:
            print(f"[DEBUG] Kullanici bulunamadi: {username}")
            flash('Kullanıcı adı veya şifre hatalı!', 'error')
            return render_template('login.html')
        
        # Şifre kontrolü - hash'lenmiş şifreyi kontrol et
        print(f"[DEBUG] Sifre kontrolu baslatiliyor...")
        print(f"[DEBUG] Kullanici sifre hash'i var mi: {bool(user.Sifre)}")
        if user.Sifre:
            print(f"[DEBUG] Hash uzunlugu: {len(user.Sifre)}")
            print(f"[DEBUG] Hash baslangici: {user.Sifre[:20]}...")
        
        if user.Sifre and check_password_hash(user.Sifre, password):
            print(f"[DEBUG] Sifre kontrolu basarili - giris onaylandi")
            # Eski oturumları temizle (24 saatten eski)
            eski_oturumlar = AktifOturum.query.filter(
                AktifOturum.SonGorulmeZamani < datetime.now() - timedelta(hours=24)
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
                session['pending_log_modulu'] = user.LogModulu
                # Admin kullanıcılar için otomatik WhatsApp yetkisi
                if user.Admin:
                    session['pending_whatsapp_modulu'] = True
                else:
                    whatsapp_modulu_value = getattr(user, 'WhatsAppModulu', False)
                    session['pending_whatsapp_modulu'] = bool(whatsapp_modulu_value) if whatsapp_modulu_value is not None else False
                # Admin kullanıcılar için otomatik Instagram yetkisi
                if user.Admin:
                    session['pending_instagram_modulu'] = True
                else:
                    instagram_modulu_value = getattr(user, 'InstagramModulu', False)
                    session['pending_instagram_modulu'] = bool(instagram_modulu_value) if instagram_modulu_value is not None else False
                
                # Firma bilgisini al
                firma = Firma.query.filter_by(FirmaID=user.FirmaID).first()
                session['pending_firma_adi'] = firma.FirmaAdi if firma else 'Bilinmeyen Firma'
                
                # Session'ı kaydet
                session.permanent = True
                
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
            session['log_modulu'] = user.LogModulu
            # WhatsAppModulu kontrolü - Admin ise otomatik True
            whatsapp_modulu_value = getattr(user, 'WhatsAppModulu', False)
            # Admin kullanıcılar için otomatik WhatsApp yetkisi
            if user.Admin:
                session['whatsapp_modulu'] = True
            else:
                session['whatsapp_modulu'] = bool(whatsapp_modulu_value) if whatsapp_modulu_value is not None else False
            # InstagramModulu kontrolü - Admin ise otomatik True
            instagram_modulu_value = getattr(user, 'InstagramModulu', False)
            if user.Admin:
                session['instagram_modulu'] = True
            else:
                session['instagram_modulu'] = bool(instagram_modulu_value) if instagram_modulu_value is not None else False

            # Oturum kaydı oluştur - önce mevcut kaydı kontrol et
            token = secrets.token_hex(16)
            session['session_token'] = token
            
            # Mevcut kaydı kontrol et
            mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user.KullaniciID).first()
            if mevcut_kayit:
                # Mevcut kaydı güncelle
                mevcut_kayit.SessionToken = token
                mevcut_kayit.ClientIP = get_client_ip()
                mevcut_kayit.UserAgent = request.headers.get('User-Agent', '')
                mevcut_kayit.SonGorulmeZamani = datetime.now()
                mevcut_kayit.GirisZamani = datetime.now()  # Yeni giriş zamanı
            else:
                # Yeni kayıt oluştur
                kayit = AktifOturum(
                    KullaniciID=user.KullaniciID,
                    SessionToken=token,
                    ClientIP=get_client_ip(),
                    UserAgent=request.headers.get('User-Agent', '')
                )
                db.session.add(kayit)
            db.session.commit()
            
            # Zorunlu parola değişimi: 123 ise yönlendir
            if user.Sifre and check_password_hash(user.Sifre, '123'):
                session['must_change_password'] = True
                flash('Lütfen güvenlik için şifrenizi değiştirin.', 'warning')
                return redirect(url_for('auth.sifre_degistir'))
            flash('Başarıyla giriş yaptınız!', 'success')
            
            # Giriş işlemi loglanmıyor
            
            return redirect(url_for('main.dashboard'))
        else:
            print(f"[DEBUG] Sifre kontrolu BASARISIZ!")
            print(f"[DEBUG] Girilen sifre uzunlugu: {len(password)}")
            flash('Kullanıcı adı veya şifre hatalı!', 'error')
    
    return render_template('login.html')

@auth_bp.route('/force-logout', methods=['POST'])
def force_logout():
    """Mevcut oturumu kapat ve yeni giriş yap"""
    # Form verilerinden veya session'dan al
    user_id = request.form.get('pending_user_id') or session.get('pending_user_id')
    
    if not user_id:
        flash('Geçersiz işlem - Pending user ID bulunamadı', 'error')
        return redirect(url_for('auth.login'))
    
    # Tüm aktif oturumları kapat (güvenlik için)
    mevcut_oturumlar = AktifOturum.query.filter_by(KullaniciID=user_id).all()
    
    for oturum in mevcut_oturumlar:
        db.session.delete(oturum)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('Oturum kapatma hatası', 'error')
        return redirect(url_for('auth.login'))
    
    # Pending verileri form'dan veya session'dan al
    pending_user_id = request.form.get('pending_user_id') or session.get('pending_user_id')
    pending_username = request.form.get('pending_username') or session.get('pending_username')
    pending_user_name = request.form.get('pending_user_name') or session.get('pending_user_name')
    pending_firma_id = request.form.get('pending_firma_id') or session.get('pending_firma_id')
    pending_firma_adi = request.form.get('pending_firma_adi') or session.get('pending_firma_adi')
    pending_is_admin = request.form.get('pending_is_admin') or session.get('pending_is_admin')
    pending_raporlar_modulu = request.form.get('pending_raporlar_modulu') or session.get('pending_raporlar_modulu')
    pending_ayarlar_modulu = request.form.get('pending_ayarlar_modulu') or session.get('pending_ayarlar_modulu')
    pending_log_modulu = request.form.get('pending_log_modulu') or session.get('pending_log_modulu')
    pending_whatsapp_modulu = request.form.get('pending_whatsapp_modulu') or session.get('pending_whatsapp_modulu')
    pending_instagram_modulu = request.form.get('pending_instagram_modulu') or session.get('pending_instagram_modulu')
    
    # Admin kontrolü - Admin ise otomatik True
    pending_is_admin_bool = pending_is_admin in [True, 'True', 'true', '1', 1]
    if pending_is_admin_bool:
        pending_whatsapp_modulu = True
        pending_instagram_modulu = True
    
    # Session'ı tamamen temizle
    session.clear()
    
    # Yeni oturum oluştur
    session['user_id'] = pending_user_id
    session['username'] = pending_username
    session['user_name'] = pending_user_name
    session['firma_id'] = pending_firma_id
    session['firma_adi'] = pending_firma_adi
    session['is_admin'] = pending_is_admin_bool
    session['raporlar_modulu'] = pending_raporlar_modulu
    session['ayarlar_modulu'] = pending_ayarlar_modulu
    session['log_modulu'] = pending_log_modulu
    session['whatsapp_modulu'] = pending_whatsapp_modulu if pending_whatsapp_modulu is not None else False
    session['instagram_modulu'] = pending_instagram_modulu if pending_instagram_modulu is not None else False
    
    # Oturum kaydı oluştur - önce mevcut kaydı kontrol et
    token = secrets.token_hex(16)
    session['session_token'] = token
    
    # Yeni kayıt oluştur
    kayit = AktifOturum(
        KullaniciID=pending_user_id,
        SessionToken=token,
        ClientIP=get_client_ip(),
        UserAgent=request.headers.get('User-Agent', '')
    )
    db.session.add(kayit)
    db.session.commit()
    
    flash('Başarıyla giriş yaptınız!', 'success')
    return redirect(url_for('main.dashboard'))

@auth_bp.route('/logout')
def logout():
    # Aktif oturum kaydını sil
    if 'user_id' in session:
        try:
            user_id = session.get('user_id')
            token = session.get('session_token')
            if user_id and token:
                AktifOturum.query.filter_by(
                    KullaniciID=user_id,
                    SessionToken=token
                ).delete()
                db.session.commit()
        except:
            pass
            
    session.clear()
    flash('Başarıyla çıkış yaptınız.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/sifre-degistir', methods=['GET', 'POST'])
def sifre_degistir():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        eski_sifre = request.form.get('eski_sifre')
        yeni_sifre = request.form.get('yeni_sifre')
        yeni_sifre_tekrar = request.form.get('yeni_sifre_tekrar')
        
        user = Kullanici.query.get(session['user_id'])
        
        if not user:
            flash('Kullanıcı bulunamadı, lütfen tekrar giriş yapın.', 'error')
            session.clear()
            return redirect(url_for('auth.login'))

        # Şifre null ise eski şifre kontrolünü atla
        if user.Sifre and not check_password_hash(user.Sifre, eski_sifre):
            flash('Eski şifreniz hatalı!', 'error')
            return render_template('sifre_degistir.html')
            
        if yeni_sifre != yeni_sifre_tekrar:
            flash('Yeni şifreler eşleşmiyor!', 'error')
            return render_template('sifre_degistir.html')
            
        if len(yeni_sifre) < 6:
            flash('Şifre en az 6 karakter olmalıdır!', 'error')
            return render_template('sifre_degistir.html')
            
        user.Sifre = generate_password_hash(yeni_sifre)
        db.session.commit()
        
        # Zorunlu şifre değişimi bayrağını kaldır
        session.pop('must_change_password', None)
        
        flash('Şifreniz başarıyla değiştirildi.', 'success')
        return redirect(url_for('main.dashboard'))
        
    return render_template('sifre_degistir.html')

from app.models import SifreSifirlamaToken
from app.utils.helpers import send_password_reset_email

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@csrf.exempt
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username')
        
        # Kullanıcı kontrolü (Sadece username ile ara, e-postayi profil verisinden kullan)
        user = Kullanici.query.filter_by(KullaniciAdi=username, Aktif=True).first()
        
        if user and user.Email:
            # Önceki kullanılmamış tokenları iptal et (isteğe bağlı güvenlik önlemi)
            eski_tokenlar = SifreSifirlamaToken.query.filter_by(KullaniciID=user.KullaniciID, Kullanildi=False).all()
            for t in eski_tokenlar:
                t.Kullanildi = True
            
            # Reset token oluştur
            reset_token = secrets.token_urlsafe(32)
            
            # Token'ı veritabanına kaydet
            yeni_token = SifreSifirlamaToken(
                KullaniciID=user.KullaniciID,
                Token=reset_token,
                GecerlilikSuresi=datetime.now() + timedelta(hours=1)
            )
            db.session.add(yeni_token)
            db.session.commit()
            
            # Reset link'i oluştur
            reset_link = url_for('auth.reset_password', token=reset_token, _external=True)
            
            # Gerçek E-posta Gönderimi
            email_sent, error_message = send_password_reset_email(user.Email, reset_link, user.FirmaID)
            
            if email_sent:
                flash(_('Password reset link has been sent to your email address.'), 'success')
            else:
                flash(f'E-Posta Gönderim Hatası: {error_message}', 'warning')
            
            return redirect(url_for('auth.login'))
        else:
            flash(_('User not found or email address is not registered.'), 'error')
    
    return redirect(url_for('auth.login'))

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
@csrf.exempt
def reset_password(token):
    # Token'ı veritabanında bul
    db_token = SifreSifirlamaToken.query.filter_by(Token=token, Kullanildi=False).first()
    
    if not db_token or db_token.GecerlilikSuresi < datetime.now():
        flash(_('Invalid or expired reset token.'), 'error')
        return redirect(url_for('auth.login'))
        
    if request.method == 'GET':
        return render_template('reset_password.html', token=token)
    
    elif request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash(_('Passwords do not match.'), 'error')
            return render_template('reset_password.html', token=token)
        
        import re
        if len(new_password) < 8 or not re.search(r'[A-Z]', new_password) or not re.search(r'[a-z]', new_password) or not re.search(r'[*!#$&]', new_password):
            flash(_('Şifre en az 8 karakter uzunluğunda olmalı, 1 büyük harf, 1 küçük harf ve 1 özel karakter (*, !, #, $, &) içermelidir.'), 'error')
            return render_template('reset_password.html', token=token)
        
        # Şifreyi güncelle
        user = Kullanici.query.get(db_token.KullaniciID)
        if user:
            user.Sifre = generate_password_hash(new_password)
            user.GuncellemeTarihi = datetime.now()
            
            # Token'ı kullanıldı olarak işaretle
            db_token.Kullanildi = True
            
            db.session.commit()
            
            flash(_('Password has been reset successfully. You can now login with your new password.'), 'success')
            return redirect(url_for('auth.login'))
            flash(_('User not found.'), 'error')
            return redirect(url_for('auth.login'))

@auth_bp.route('/debug/email')
def debug_email_settings():
    from app.models import FirmaEmailAyar, Kullanici
    try:
        user = Kullanici.query.first()
        ayarlar = FirmaEmailAyar.query.all()
        ret = f"Current User: {user.KullaniciAdi} (Firma: {user.FirmaID})<br>"
        if not ayarlar:
            ret += "No email settings found for ANY company!"
        else:
            for a in ayarlar:
                ret += f"Found Setting -> FirmaID: {a.FirmaID}, Server: {a.SMTP_Sunucu}, User: {a.KullaniciAdi}<br>"
        return ret
    except Exception as e:
        return f"Error querying: {e}"
