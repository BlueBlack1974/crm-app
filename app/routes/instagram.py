from flask import Blueprint, request, jsonify, render_template, current_app, session, flash, redirect, url_for
from app.extensions import db
from app.models import FirmaInstagramAyar, InstagramMesaj, Kullanici, Firma, Musteri
from app.utils.decorators import login_required
from sqlalchemy import or_
import requests
from datetime import datetime

instagram_bp = Blueprint('instagram', __name__, url_prefix='/instagram')

@instagram_bp.route('/ayarlar', methods=['GET', 'POST'])
@login_required
def ayarlar():
    """Firma Instagram ayarlarını yönetir."""
    # Session bazlı yetki kontrolü
    if not session.get('is_admin', False) and not session.get('instagram_modulu', False):
        flash('Instagram ayarlarına erişim yetkiniz yok!', 'error')
        return redirect(url_for('ayarlar'))

    firma_id = session.get('firma_id')
    ayar = FirmaInstagramAyar.query.filter_by(FirmaID=firma_id).first()

    if request.method == 'POST':
        try:
            data = request.form
            
            if not ayar:
                ayar = FirmaInstagramAyar(FirmaID=firma_id)
                db.session.add(ayar)
            
            ayar.FacebookPageID = data.get('facebook_page_id')
            ayar.InstagramBusinessAccountID = data.get('instagram_account_id')
            ayar.AccessToken = data.get('access_token')
            ayar.WebhookSecret = data.get('webhook_secret')
            ayar.Aktif = 'aktif' in data
            
            db.session.commit()
            flash('Instagram ayarları başarıyla güncellendi.', 'success')
            return redirect(url_for('instagram.ayarlar'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Instagram ayar hatası: {str(e)}")
            flash('Ayarlar kaydedilirken bir hata oluştu.', 'error')

    return render_template('instagram_ayarlar.html', ayar=ayar)

@instagram_bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Meta'dan gelen webhook isteklerini karşılar."""
    
    # 1. Doğrulama (Verification Request)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        # Tüm aktif firma ayarlarını çekip token eşleşmesi ara
        # Not: Gerçek hayatta bu kadar basit olmayabilir, usually global bir verify token kullanılır
        # Ancak burada her firma için ayrı webhook tanımlanacaksa mantık değişir.
        # Basitlik için: İlk eşleşen tokenı kabul edelim.
        
        ayarlar = FirmaInstagramAyar.query.filter_by(Aktif=True).all()
        for ayar in ayarlar:
            if ayar.WebhookSecret and token == ayar.WebhookSecret:
                return challenge, 200
                
        return 'Forbidden', 403

    # 2. Olay Bildirimi (Event Notification)
    if request.method == 'POST':
        try:
            data = request.json
            current_app.logger.info(f"Instagram Webhook Data: {data}")
            
            if data.get('object') == 'instagram':
                for entry in data.get('entry', []):
                    # messaging events
                    if 'messaging' in entry:
                         for messaging_event in entry['messaging']:
                             handle_messaging_event(messaging_event)
                             
            return 'EVENT_RECEIVED', 200
            
        except Exception as e:
            current_app.logger.error(f"Webhook error: {str(e)}")
            return 'Error', 500

def handle_messaging_event(event):
    """Gelen mesajı veritabanına kaydeder."""
    try:
        sender_id = event.get('sender', {}).get('id')
        recipient_id = event.get('recipient', {}).get('id')
        message = event.get('message', {})
        text = message.get('text')
        mid = message.get('mid')
        
        if not text:
            return # Sadece metin mesajlarını işliyoruz şimdilik

        # İlgili firmayı bul (Recipient ID = Instagram Business ID)
        ayar = FirmaInstagramAyar.query.filter_by(InstagramBusinessAccountID=recipient_id).first()
        if not ayar:
            current_app.logger.warning(f"Bilinmeyen alıcı ID: {recipient_id}")
            return

        # Mesajı kaydet
        yeni_mesaj = InstagramMesaj(
            InstagramMessageID=mid,
            FirmaID=ayar.FirmaID,
            GonderenID=sender_id,
            AliciID=recipient_id,
            MesajMetni=text,
            Yyon='GELEN'
        )
        db.session.add(yeni_mesaj)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Mesaj işleme hatası: {str(e)}")

@instagram_bp.route('/mesajlar')
@login_required
def mesajlar():
    """Instagram Mesajlaşma Arayüzü"""
    # Session bazlı yetki kontrolü
    if not session.get('is_admin', False) and not session.get('instagram_modulu', False):
        flash('Instagram modülüne erişim yetkiniz yok!', 'error')
        return redirect(url_for('main.dashboard'))
    
    firma_id = session.get('firma_id')
    
    # Ayar kontrolü - Eğer ayar yoksa veya aktif değilse ayarlara yönlendir
    ayar = FirmaInstagramAyar.query.filter_by(FirmaID=firma_id).first()
    if not ayar or not ayar.Aktif:
        flash('Instagram modülünü kullanabilmek için önce ayarları yapmalısınız.', 'warning')
        return redirect(url_for('instagram.ayarlar'))

    # Sol menüde son konuşulanları listele
    # Sol menüde müşterileri listele (Instagram adresi olanlar)
    # Her müşteri için son mesajı ve okunmamış sayısını da alabiliriz
    
    musteriler = Musteri.query.filter(
        Musteri.FirmaID == firma_id,
        Musteri.InstagramKullaniciAdi != None,
        Musteri.InstagramKullaniciAdi != ''
    ).all()
    
    conversations = []
    
    # Her müşteri için son mesajı bul
    # (Performans için tek bir complex query daha iyi olurdu ama şimdilik döngü ile basit tutalım)
    for musteri in musteriler:
        # Bu müşteriyle ilgili son mesajı bul (GonderenID veya AliciID eşleşmesi)
        # Not: Musteri modelinde Instagram ID'si (PSID) tutulmuyor, sadece kullanıcı adı var.
        # Bu yüzden veritabanındaki mesajlarla eşleştirmek zor olabilir.
        # İdeal çözüm: Musteri tablosuna InstagramUserId (PSID) eklemek.
        # Şimdilik varsayım: InstagramMesaj tablosunda MusteriID varsa oradan, yoksa eşleştirme yok.
        
        last_msg = InstagramMesaj.query.filter(
            InstagramMesaj.FirmaID == firma_id,
            or_(
                InstagramMesaj.MusteriID == musteri.MusteriID,
                # Eğer MusteriID yoksa, belki ilerde PSID eşleşmesi yapılabilir
            )
        ).order_by(InstagramMesaj.Tarih.desc()).first()
        
        # Gönderen ID (API için gerekli)
        # Eğer mesaj varsa ondan al, yoksa boş (bu durumda sohbet başlatılamayabilir)
        if last_msg:
             api_target_id = last_msg.GonderenID if last_msg.Yyon == 'Gelen' else last_msg.AliciID
        else:
             api_target_id = None 
             
        conversations.append({
            'musteri': musteri,
            'son_mesaj': last_msg,
            'api_target_id': api_target_id, # Sohbet yüklemek için kullanılacak ID
            'okunmamis': 0 # Şimdilik 0
        })
        
    # Son mesaj tarihine göre sırala (mesajı olmayanlar en sona)
    conversations.sort(key=lambda x: x['son_mesaj'].Tarih if x['son_mesaj'] else datetime.min, reverse=True)
    
    return render_template('instagram_mesajlar.html', conversations=conversations)

@instagram_bp.route('/api/mesajlar/<gonderen_id>')
@login_required
def api_mesajlar(gonderen_id):
    """Belirli bir kişiyle olan mesajlaşma geçmişi"""
    # Session bazlı yetki kontrolü
    if not session.get('is_admin', False) and not session.get('instagram_modulu', False):
        return jsonify({'error': 'Yetkisiz erişim'}), 403
    
    firma_id = session.get('firma_id')
    mesajlar = InstagramMesaj.query.filter(
        InstagramMesaj.FirmaID == firma_id
    ).filter(
        or_(
            InstagramMesaj.GonderenID == gonderen_id,
            InstagramMesaj.AliciID == gonderen_id
        )
    ).order_by(InstagramMesaj.Tarih.asc()).all()
    
    return jsonify([{
        'id': m.MesajID,
        'metin': m.MesajMetni,
        'yon': m.Yyon, # 'Gelen' veya 'Giden'
        'tarih': m.Tarih.strftime('%d.%m.%Y %H:%M')
    } for m in mesajlar])

@instagram_bp.route('/api/mesaj-gonder', methods=['POST'])
@login_required
def api_mesaj_gonder():
    """Instagram mesajı gönder"""
    # Session bazlı yetki kontrolü
    if not session.get('is_admin', False) and not session.get('instagram_modulu', False):
        return jsonify({'error': 'Yetkisiz erişim'}), 403
    
    try:
        data = request.get_json()
        recipient_id = data.get('recipient_id')
        message_text = data.get('message_text')
        
        if not recipient_id or not message_text:
            return jsonify({'success': False, 'message': 'Eksik parametre'}), 400
            
        success = True # Mock success
        
        if success:
             # Veritabanına kaydet
            yeni_mesaj = InstagramMesaj(
                FirmaID=session['firma_id'],
                InstagramMessageID='mock_id_' + datetime.now().strftime('%Y%m%d%H%M%S'),
                GonderenID=session.get('firma_instagram_page_id', 'me'),
                AliciID=recipient_id,
                MesajMetni=message_text,
                Yyon='Giden',
                Tarih=datetime.now()
            )
            db.session.add(yeni_mesaj)
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'API Hatası'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
