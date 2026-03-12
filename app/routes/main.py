from flask import Blueprint, render_template, redirect, url_for, session, send_file, abort
import os
from datetime import datetime, timedelta
from app.extensions import db
from app.models import Randevu, RandevuYetki, Todo, TodoDurum, Bildirim, Kullanici, Firma
from app.utils.decorators import login_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return render_template('home.html')

@main_bp.route('/home-new')
def home_new():
    return render_template('home_new.html')

@main_bp.route('/dashboard')
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
    
    # Yapılacaklar (Kişisel) verilerini getir - Durum bilgisi ile birlikte
    user_todos = db.session.query(Todo).outerjoin(TodoDurum, Todo.DurumID == TodoDurum.DurumID).filter(
        Todo.KullaniciID == session['user_id'], 
        Todo.Tip == 'Kisisel'
    ).order_by(Todo.Oncelik.desc(), Todo.OlusturmaTarihi.desc()).limit(5).all()
    
    # Görevler (Randevu) verilerini getir
    user_gorevler = Todo.query.filter_by(KullaniciID=session['user_id'], Tip='Randevu').order_by(
        Todo.Oncelik.desc(), Todo.OlusturmaTarihi.desc()
    ).limit(5).all()
    
    # Yapılacaklar (Kişisel) istatistikleri
    toplam_todo = Todo.query.filter_by(KullaniciID=session['user_id'], Tip='Kisisel').count()
    
    # Yapılacaklar durum istatistikleri için join kullan
    tamamlanan_todo = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Kisisel',
        TodoDurum.DurumAdi == 'Tamamlandı'
    ).count()
    
    beklemede_todo = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Kisisel',
        TodoDurum.DurumAdi == 'Beklemede'
    ).count()
    
    devam_eden_todo = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Kisisel',
        TodoDurum.DurumAdi == 'Devam Ediyor'
    ).count()
    
    # Görevler (Randevu) istatistikleri - Durumlara göre
    toplam_gorev = Todo.query.filter_by(KullaniciID=session['user_id'], Tip='Randevu').count()
    
    # Firma bazlı tüm durumları getir
    gorev_durumlar = TodoDurum.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(TodoDurum.Sira).all()
    
    # Her durum için kullanıcının görev sayısını hesapla
    gorev_durum_istatistikleri = []
    for durum in gorev_durumlar:
        sayi = db.session.query(Todo).join(TodoDurum).filter(
            Todo.KullaniciID == session['user_id'],
            Todo.Tip == 'Randevu',
            TodoDurum.DurumID == durum.DurumID
        ).count()
        gorev_durum_istatistikleri.append({
            'durum': durum,
            'sayi': sayi
        })
    
    # Eski istatistikler (geriye dönük uyumluluk için)
    tamamlanan_gorev = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Randevu',
        TodoDurum.DurumAdi == 'Tamamlandı'
    ).count()
    
    beklemede_gorev = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Randevu',
        TodoDurum.DurumAdi == 'Beklemede'
    ).count()
    
    devam_eden_gorev = db.session.query(Todo).join(TodoDurum).filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Randevu',
        TodoDurum.DurumAdi == 'Devam Ediyor'
    ).count()
    
    # Okunmamiş bildirim sayısı
    unread_count = Bildirim.query.filter_by(KullaniciID=session['user_id'], Okundu=False).count()

    # İptal edilmeyenleri sayarak firma geneli toplam randevu
    toplam_randevu_sayisi = Randevu.query.filter(
        Randevu.FirmaID == session['firma_id'],
        Randevu.Durum != 'İptal'
    ).count()

    # Bu haftanın randevu sayısı (Pazartesi - Pazar, iptaller hariç)
    bugun = datetime.now().date()
    hafta_basi = bugun - timedelta(days=bugun.weekday())  # Pazartesi
    hafta_sonu = hafta_basi + timedelta(days=6)           # Pazar
    bu_hafta_randevu_sayisi = Randevu.query.filter(
        Randevu.FirmaID == session['firma_id'],
        Randevu.Durum != 'İptal',
        Randevu.RandevuTarihi >= hafta_basi,
        Randevu.RandevuTarihi <= hafta_sonu
    ).count()

    # Firma geneli beklemede olan randevular
    beklemede_sayisi = Randevu.query.filter(
        Randevu.FirmaID == session['firma_id'],
        Randevu.Durum == 'Beklemede'
    ).count()

    # Firma geneli onaylanan randevular
    onaylandi_sayisi = Randevu.query.filter(
        Randevu.FirmaID == session['firma_id'],
        Randevu.Durum == 'Onaylandi'
    ).count()

    # AI Asistan - firma bilgisi ve Kullanıcı yetkisi
    from datetime import date
    firma_obj = Firma.query.get(session.get('firma_id'))
    aktif_kul = Kullanici.query.get(session.get('user_id'))
    ay_str = date.today().strftime('%Y-%m')
    firma_ai_aktif = bool(firma_obj.AIAktif) if firma_obj else False
    kullanici_ai_aktif = bool(aktif_kul.AIModulu) if aktif_kul else False
    firma_ai_limit = firma_obj.AIAylikLimit if firma_obj else 0
    firma_ai_kullanilan = firma_obj.AIKullanilanSayi if firma_obj and firma_obj.AIKullanimAy == ay_str else 0

    return render_template('dashboard.html', 
                         randevular=randevular,
                         toplam_randevu_sayisi=toplam_randevu_sayisi,
                         bu_hafta_randevu_sayisi=bu_hafta_randevu_sayisi,
                         beklemede_sayisi=beklemede_sayisi,
                         onaylandi_sayisi=onaylandi_sayisi,
                         unread_count=unread_count,
                         user_todos=user_todos,
                         user_gorevler=user_gorevler,
                         toplam_todo=toplam_todo,
                         tamamlanan_todo=tamamlanan_todo,
                         beklemede_todo=beklemede_todo,
                         devam_eden_todo=devam_eden_todo,
                         toplam_gorev=toplam_gorev,
                         tamamlanan_gorev=tamamlanan_gorev,
                         beklemede_gorev=beklemede_gorev,
                         devam_eden_gorev=devam_eden_gorev,
                         gorev_durum_istatistikleri=gorev_durum_istatistikleri,
                         firma_ai_aktif=firma_ai_aktif,
                         kullanici_ai_aktif=kullanici_ai_aktif,
                         firma_ai_limit=firma_ai_limit,
                         firma_ai_kullanilan=firma_ai_kullanilan)

@main_bp.route('/profil')
@login_required
def profil():
    u = Kullanici.query.get(session['user_id'])
    if not u:
        flash('Kullanıcı bulunamadı', 'error')
        return redirect(url_for('auth.logout'))
    unread_count = Bildirim.query.filter_by(KullaniciID=session['user_id'], Okundu=False).count()
    return render_template('profil.html', kullanici=u, unread_count=unread_count)

# Avatar resimleri için özel route - 404'ü önlemek için
@main_bp.route('/avatar/<int:user_id>')
def serve_user_avatar(user_id):
    """Kullanıcı avatar resmini gönder, yoksa varsayılan avatar'ı gönder"""
    # Önce veritabanından dosya yolunu kontrol et
    kullanici = Kullanici.query.get(user_id)
    if kullanici and kullanici.ProfilFotografi:
        # Veritabanından gelen dosya yolunu kullan
        avatar_path = os.path.join('app', 'static', kullanici.ProfilFotografi)
        if os.path.exists(avatar_path) and os.path.isfile(avatar_path):
            return send_file(avatar_path, mimetype='image/jpeg')
    
    # Veritabanında yol yoksa, eski yöntemle kontrol et (geriye dönük uyumluluk)
    avatar_path = os.path.join('app', 'static', 'uploads', 'users', f'user_{user_id}.jpg')
    if os.path.exists(avatar_path) and os.path.isfile(avatar_path):
        # Dosya varsa ama veritabanında yoksa, veritabanına kaydet
        if kullanici:
            relative_path = f'uploads/users/user_{user_id}.jpg'
            kullanici.ProfilFotografi = relative_path
            db.session.commit()
        return send_file(avatar_path, mimetype='image/jpeg')
    
    # Varsayılan avatar'ı gönder
    default_avatar = os.path.join('app', 'static', 'img', 'avatar-default.svg')
    if os.path.exists(default_avatar):
        return send_file(default_avatar, mimetype='image/svg+xml')
    else:
        # Varsayılan avatar da yoksa 404 döndür
        abort(404)
