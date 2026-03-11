from flask import Blueprint, request, jsonify, render_template, current_app, session, flash, redirect, url_for
from app.extensions import db
from app.models import KullaniciMesaj, Kullanici
from app.utils.decorators import login_required
from sqlalchemy import or_, and_, func
from datetime import datetime

kullanici_mesaj_bp = Blueprint('kullanici_mesaj', __name__, url_prefix='/kullanici-mesaj')


@kullanici_mesaj_bp.route('/mesajlar')
@login_required
def mesajlar():
    """Kullanıcılar Arası Mesajlaşma Arayüzü"""
    kullanici_id = int(session.get('user_id')) if session.get('user_id') else None
    firma_id = session.get('firma_id')
    
    if not kullanici_id or not firma_id:
        flash('Oturum bilgisi bulunamadı!', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Aynı firmadaki diğer kullanıcıları listele
    diger_kullanicilar = Kullanici.query.filter(
        and_(
            Kullanici.FirmaID == firma_id,
            Kullanici.KullaniciID != kullanici_id,
            Kullanici.Aktif == True
        )
    ).order_by(Kullanici.Ad, Kullanici.Soyad).all()
    
    # Son mesajları al
    conversations = []
    for kullanici in diger_kullanicilar:
        # Bu kullanıcıyla son mesajı bul
        son_mesaj = KullaniciMesaj.query.filter(
            or_(
                and_(KullaniciMesaj.GonderenID == kullanici_id, KullaniciMesaj.AliciID == kullanici.KullaniciID, KullaniciMesaj.GonderenSilindi == False),
                and_(KullaniciMesaj.GonderenID == kullanici.KullaniciID, KullaniciMesaj.AliciID == kullanici_id, KullaniciMesaj.AliciSilindi == False)
            )
        ).order_by(KullaniciMesaj.OlusturmaTarihi.desc()).first()
        
        # Okunmamış mesaj sayısı
        okunmamis_sayisi = KullaniciMesaj.query.filter(
            and_(
                KullaniciMesaj.GonderenID == kullanici.KullaniciID,
                KullaniciMesaj.AliciID == kullanici_id,
                KullaniciMesaj.Okundu == False,
                KullaniciMesaj.AliciSilindi == False
            )
        ).count()
        
        conversations.append({
            'kullanici': kullanici,
            'son_mesaj': son_mesaj,
            'okunmamis_sayisi': okunmamis_sayisi
        })
    
    # Son mesajı olanları önce göster
    conversations.sort(key=lambda x: x['son_mesaj'].OlusturmaTarihi if x['son_mesaj'] else datetime.min, reverse=True)
    
    # Online durumunu kontrol et (Son 5 dakika içinde aktif olanlar)
    simdi = datetime.now()
    for conv in conversations:
        kullanici = conv['kullanici']
        is_online = False
        if kullanici.aktif_oturum:
            # Error fix: kullanici.aktif_oturum is a list (InstrumentedList), check all sessions
            sessions = kullanici.aktif_oturum
            try:
                for oturum in sessions:
                    if oturum.SonGorulmeZamani:
                        fark = simdi - oturum.SonGorulmeZamani
                        if fark.total_seconds() < 300: # 5 dakika
                            is_online = True
                            break
            except TypeError:
                # Fallback if it is not iterable (single object)
                if sessions.SonGorulmeZamani:
                    fark = simdi - sessions.SonGorulmeZamani
                    if fark.total_seconds() < 300:
                        is_online = True
        conv['is_online'] = is_online

    return render_template('kullanici_mesajlar.html', conversations=conversations, diger_kullanicilar=diger_kullanicilar)


@kullanici_mesaj_bp.route('/api/mesajlar/<int:alici_id>')
@login_required
def api_mesajlar(alici_id):
    """Belirli bir kullanıcıyla olan mesajlaşma geçmişi"""
    kullanici_id = int(session.get('user_id')) if session.get('user_id') else None
    firma_id = session.get('firma_id')
    
    if not kullanici_id:
        return jsonify({'error': 'Oturum bilgisi bulunamadı'}), 403
    
    # Firma kontrolü - alıcı aynı firmada mı?
    alici = Kullanici.query.filter_by(KullaniciID=alici_id, FirmaID=firma_id).first()
    if not alici:
        return jsonify({'error': 'Kullanıcı bulunamadı veya yetkisiz erişim'}), 403
    
    # Mesajları getir (silinmemiş olanlar)
    mesajlar = KullaniciMesaj.query.filter(
        or_(
            and_(KullaniciMesaj.GonderenID == kullanici_id, KullaniciMesaj.AliciID == alici_id, KullaniciMesaj.GonderenSilindi == False),
            and_(KullaniciMesaj.GonderenID == alici_id, KullaniciMesaj.AliciID == kullanici_id, KullaniciMesaj.AliciSilindi == False)
        )
    ).order_by(KullaniciMesaj.OlusturmaTarihi.asc()).all()
    
    # Okunmamış mesajları okundu olarak işaretle
    okunmamis_mesajlar = [m for m in mesajlar if m.AliciID == kullanici_id and not m.Okundu]
    if okunmamis_mesajlar:
        for mesaj in okunmamis_mesajlar:
            mesaj.Okundu = True
            mesaj.OkunmaTarihi = datetime.now()
        db.session.commit()
    
    return jsonify({
        'success': True,
        'mesajlar': [m.to_dict() for m in mesajlar]
    })


@kullanici_mesaj_bp.route('/api/mesaj-gonder', methods=['POST'])
@login_required
def api_mesaj_gonder():
    """Kullanıcılar arası mesaj gönder"""
    kullanici_id = int(session.get('user_id')) if session.get('user_id') else None
    firma_id = session.get('firma_id')
    
    if not kullanici_id:
        return jsonify({'success': False, 'error': 'Oturum bilgisi bulunamadı'}), 403
    
    try:
        data = request.get_json()
        alici_id = data.get('alici_id')
        mesaj = data.get('mesaj', '').strip()
        
        if not alici_id:
            return jsonify({'success': False, 'error': 'Alıcı belirtilmedi'}), 400
        
        if not mesaj:
            return jsonify({'success': False, 'error': 'Mesaj boş olamaz'}), 400
        
        # Firma kontrolü - alıcı aynı firmada mı?
        alici = Kullanici.query.filter_by(KullaniciID=alici_id, FirmaID=firma_id).first()
        if not alici:
            return jsonify({'success': False, 'error': 'Kullanıcı bulunamadı veya yetkisiz erişim'}), 403
        
        # Mesajı kaydet
        yeni_mesaj = KullaniciMesaj(
            GonderenID=kullanici_id,
            AliciID=alici_id,
            Mesaj=mesaj,
            Okundu=False
        )
        db.session.add(yeni_mesaj)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mesaj': yeni_mesaj.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Mesaj gönderme hatası: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@kullanici_mesaj_bp.route('/api/okunmamis-sayisi')
@login_required
def api_okunmamis_sayisi():
    """Okunmamış mesaj sayısını döndür"""
    kullanici_id = int(session.get('user_id')) if session.get('user_id') else None
    
    if not kullanici_id:
        return jsonify({'okunmamis_sayisi': 0})
    
    sayi = KullaniciMesaj.query.filter(
        and_(
            KullaniciMesaj.AliciID == kullanici_id,
            KullaniciMesaj.Okundu == False,
            KullaniciMesaj.AliciSilindi == False
        )
    ).count()
    
    return jsonify({'okunmamis_sayisi': sayi})


@kullanici_mesaj_bp.route('/api/okunmamis-mesajlar-ozet')
@login_required
def api_okunmamis_mesajlar_ozet():
    """Tüm gönderenlerden gelen okunmamış mesaj sayılarını döndür"""
    kullanici_id = int(session.get('user_id')) if session.get('user_id') else None
    
    if not kullanici_id:
        return jsonify({'ozet': []})
    
    # Group by GonderenID
    okunmamis_ozet = db.session.query(
        KullaniciMesaj.GonderenID, 
        func.count(KullaniciMesaj.MesajID)
    ).filter(
        KullaniciMesaj.AliciID == kullanici_id,
        KullaniciMesaj.Okundu == False,
        KullaniciMesaj.AliciSilindi == False
    ).group_by(KullaniciMesaj.GonderenID).all()
    
    ozet_list = [{'gonderen_id': row[0], 'sayi': row[1]} for row in okunmamis_ozet]
    
    return jsonify({'ozet': ozet_list})


@kullanici_mesaj_bp.route('/api/mesaj-sil/<int:mesaj_id>', methods=['POST'])
@login_required
def api_mesaj_sil(mesaj_id):
    """Mesajı sil (soft delete)"""
    kullanici_id = int(session.get('user_id')) if session.get('user_id') else None
    
    if not kullanici_id:
        return jsonify({'success': False, 'error': 'Oturum bilgisi bulunamadı'}), 403
    
    try:
        mesaj = KullaniciMesaj.query.get_or_404(mesaj_id)
        
        # Sadece kendi mesajlarını silebilir
        if mesaj.GonderenID == kullanici_id:
            mesaj.GonderenSilindi = True
        elif mesaj.AliciID == kullanici_id:
            mesaj.AliciSilindi = True
        else:
            return jsonify({'success': False, 'error': 'Yetkisiz erişim'}), 403
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Mesaj silme hatası: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
@kullanici_mesaj_bp.route('/api/online-kullanicilar')
@login_required
def api_online_kullanicilar():
    """Aynı firmadaki kullanıcıların online durumunu döndür"""
    kullanici_id = int(session.get('user_id')) if session.get('user_id') else None
    firma_id = session.get('firma_id')
    
    if not kullanici_id or not firma_id:
        return jsonify({'online_users': {}})
    
    # Aynı firmadaki diğer kullanıcıları bul
    diger_kullanicilar = Kullanici.query.filter(
        and_(
            Kullanici.FirmaID == firma_id,
            Kullanici.KullaniciID != kullanici_id,
            Kullanici.Aktif == True
        )
    ).all()
    
    online_status = {}
    simdi = datetime.now()
    
    for k in diger_kullanicilar:
        is_online = False
        if k.aktif_oturum:
            # Handle list vs single object for backref
            sessions = k.aktif_oturum
            try:
                # If iterable
                for oturum in sessions:
                    if oturum.SonGorulmeZamani:
                        fark = simdi - oturum.SonGorulmeZamani
                        if fark.total_seconds() < 300: # 5 dakika
                            is_online = True
                            break
            except TypeError:
                # If single object
                if sessions.SonGorulmeZamani:
                    fark = simdi - sessions.SonGorulmeZamani
                    if fark.total_seconds() < 300:
                        is_online = True
        
        online_status[k.KullaniciID] = is_online
        
    return jsonify({'online_users': online_status})
