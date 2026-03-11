from functools import wraps
from flask import session, request, redirect, url_for, jsonify, flash
from app.models import AktifOturum
from app.utils.helpers import get_client_ip
from app.extensions import db
from datetime import datetime

# Yardımcı: İstek JSON/AJAX mi?
def _wants_json_response():
    """Return True only for AJAX/JSON API requests.
    - Prefer explicit XHR header
    - Or when content-type/body is JSON
    - Or when client clearly prefers JSON over HTML
    """
    try:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return True
        if request.is_json:
            return True
        accepts = request.accept_mimetypes or {}
        # Only treat as JSON if JSON is strictly preferred over HTML
        json_q = accepts['application/json'] if 'application/json' in accepts else 0
        html_q = accepts['text/html'] if 'text/html' in accepts else 0
        return json_q > html_q
    except Exception:
        return False

# Login gerekli decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if _wants_json_response():
                return jsonify({"success": False, "message": "Oturum gerekli"}), 401
            return redirect(url_for('auth.login'))
        
        # Aktif oturum kontrolü (tek oturum) - tüm isteklerde kontrol et
        if True:
            user_id = session.get('user_id')
            session_token = session.get('session_token')
            if user_id and session_token:
                try:
                    # 1) Kaydı bu token ile bulmaya çalış
                    aktif_oturum = AktifOturum.query.filter_by(
                        KullaniciID=user_id,
                        SessionToken=session_token
                    ).first()
                    if not aktif_oturum:
                        # 2) Bu kullanıcı için herhangi bir aktif kayıt var mı?
                        mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
                        if mevcut_kayit is None:
                            # Kayıt yoksa otomatik yeniden oluştur (tarayıcı çerezi duruyor ama DB kaydı silinmiş olabilir)
                            # Önce mevcut kaydı kontrol et - UNIQUE constraint hatasını önle
                            mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
                            if mevcut_kayit:
                                # Mevcut kaydı güncelle
                                mevcut_kayit.SessionToken = session_token
                                mevcut_kayit.ClientIP = get_client_ip()
                                mevcut_kayit.UserAgent = request.headers.get('User-Agent', '')
                                mevcut_kayit.SonGorulmeZamani = datetime.now()
                                try:
                                    db.session.commit()
                                except Exception as commit_error:
                                    print(f"Oturum güncelleme hatası: {commit_error}")
                                    db.session.rollback()
                            else:
                                # Yeni kayıt oluştur
                                try:
                                    yeni = AktifOturum(
                                        KullaniciID=user_id,
                                        SessionToken=session_token,
                                        ClientIP=get_client_ip(),
                                        UserAgent=request.headers.get('User-Agent', '')
                                    )
                                    db.session.add(yeni)
                                    db.session.commit()
                                except Exception as db_error:
                                    # UNIQUE constraint hatası - race condition olabilir
                                    db.session.rollback()
                                    # Tekrar kontrol et ve güncelle
                                    mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
                                    if mevcut_kayit:
                                        mevcut_kayit.SessionToken = session_token
                                        mevcut_kayit.ClientIP = get_client_ip()
                                        mevcut_kayit.UserAgent = request.headers.get('User-Agent', '')
                                        mevcut_kayit.SonGorulmeZamani = datetime.now()
                                        try:
                                            db.session.commit()
                                        except Exception as commit_error:
                                            print(f"Oturum güncelleme hatası (2. deneme): {commit_error}")
                                            db.session.rollback()
                                    else:
                                        print(f"Oturum kaydı oluşturma hatası: {db_error}")
                        else:
                            # Mevcut kayıt var ama token farklı
                            # Token'ı güncelle (aynı kullanıcı, farklı sekme/yenileme olabilir)
                            mevcut_kayit.SessionToken = session_token
                            mevcut_kayit.SonGorulmeZamani = datetime.now()
                            try:
                                db.session.commit()
                            except:
                                db.session.rollback()
                except Exception as e:
                    print(f"Oturum kontrolü hatası: {e}")
                    session.clear()
                    if _wants_json_response():
                        return jsonify({"success": False, "message": "Oturum kontrol hatası"}), 401
                    flash('Oturum kontrolünde hata oluştu. Lütfen tekrar giriş yapın.', 'error')
                    return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function

# Admin gerekli decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if _wants_json_response():
                return jsonify({"success": False, "message": "Oturum gerekli"}), 401
            return redirect(url_for('auth.login'))
        
        # Aktif oturum kontrolü - basitleştirildi
        user_id = session.get('user_id')
        session_token = session.get('session_token')
        if user_id and session_token:
            try:
                aktif_oturum = AktifOturum.query.filter_by(
                    KullaniciID=user_id,
                    SessionToken=session_token
                ).first()
                if not aktif_oturum:
                    # Token yoksa, mevcut kaydı güncelle veya yeni oluştur
                    mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
                    if mevcut_kayit:
                        mevcut_kayit.SessionToken = session_token
                        mevcut_kayit.SonGorulmeZamani = datetime.now()
                    else:
                        yeni = AktifOturum(
                            KullaniciID=user_id,
                            SessionToken=session_token,
                            ClientIP=get_client_ip(),
                            UserAgent=request.headers.get('User-Agent', '')
                        )
                        db.session.add(yeni)
                    try:
                        db.session.commit()
                    except:
                        db.session.rollback()
            except Exception as e:
                print(f"Admin oturum kontrolü hatası: {e}")
        
        if not session.get('is_admin', False) and not session.get('ayarlar_modulu', False):
            flash('Bu sayfaya erişim yetkiniz yok!', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Sadece admin gerekli decorator (ayarlar modülü yetkisi yeterli değil)
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if _wants_json_response():
                return jsonify({"success": False, "message": "Oturum gerekli"}), 401
            return redirect(url_for('auth.login'))
        
        # Aktif oturum kontrolü - basitleştirildi
        user_id = session.get('user_id')
        session_token = session.get('session_token')
        if user_id and session_token:
            try:
                aktif_oturum = AktifOturum.query.filter_by(
                    KullaniciID=user_id,
                    SessionToken=session_token
                ).first()
                if not aktif_oturum:
                    # Token yoksa, mevcut kaydı güncelle veya yeni oluştur
                    mevcut_kayit = AktifOturum.query.filter_by(KullaniciID=user_id).first()
                    if mevcut_kayit:
                        mevcut_kayit.SessionToken = session_token
                        mevcut_kayit.SonGorulmeZamani = datetime.now()
                    else:
                        yeni = AktifOturum(
                            KullaniciID=user_id,
                            SessionToken=session_token,
                            ClientIP=get_client_ip(),
                            UserAgent=request.headers.get('User-Agent', '')
                        )
                        db.session.add(yeni)
                    try:
                        db.session.commit()
                    except:
                        db.session.rollback()
            except Exception as e:
                print(f"Super admin oturum kontrolü hatası: {e}")
        
        if not session.get('is_admin', False):
            flash('Bu sayfaya erişim yetkiniz yok!', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function
