"""
Activity / İletişim Geçmişi Modülü
Müşteri iletişim geçmişi ve aktivite kayıtları için route'lar
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from app.extensions import db, csrf
from app.models import Aktivite, Musteri, Kullanici, Randevu, Todo
from app.utils.decorators import login_required
from datetime import datetime, timedelta
import json

aktivite_bp = Blueprint('aktivite', __name__)

# =====================================================
# API Endpoint'leri
# =====================================================

@aktivite_bp.route('/api/aktiviteler', methods=['GET'])
@login_required
def api_aktiviteler_liste():
    """
    Aktivite listesi API endpoint'i
    GET /api/aktiviteler?customer_id=123&limit=50&offset=0
    """
    try:
        firma_id = session.get('firma_id')
        if not firma_id:
            return jsonify({'success': False, 'error': 'Firma bilgisi bulunamadı'}), 401
        
        # Query parametreleri
        customer_id = request.args.get('customer_id', type=int)
        limit = request.args.get('limit', type=int, default=50)
        offset = request.args.get('offset', type=int, default=0)
        activity_type = request.args.get('activity_type')  # Filtreleme için
        
        # Base query - sadece kullanıcının firmasına ait aktiviteler
        query = Aktivite.query.filter_by(FirmaID=firma_id)
        
        # Müşteri filtresi
        if customer_id:
            query = query.filter_by(MusteriID=customer_id)
        
        # Aktivite tipi filtresi
        if activity_type:
            query = query.filter_by(AktiviteTipi=activity_type)
        
        # Sıralama: AktiviteTarihi'ne göre yeni -> eski (DESC)
        query = query.order_by(Aktivite.AktiviteTarihi.desc())
        
        # Toplam sayı (pagination için)
        total = query.count()
        
        # Limit ve offset uygula
        aktiviteler = query.limit(limit).offset(offset).all()
        
        # Sonuçları formatla
        results = [aktivite.to_dict() for aktivite in aktiviteler]
        
        return jsonify({
            'success': True,
            'data': results,
            'total': total,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@aktivite_bp.route('/api/aktiviteler', methods=['POST'])
@login_required
@csrf.exempt
def api_aktivite_olustur():
    """
    Yeni aktivite oluşturma API endpoint'i
    POST /api/aktiviteler
    Body: {
        "musteri_id": 123,
        "aktivite_tipi": "call",
        "baslik": "Telefon görüşmesi",
        "aciklama": "Müşteri ile görüşüldü...",
        "aktivite_tarihi": "2024-01-15T14:30:00",
        "ilgili_nesne_tipi": "appointment",
        "ilgili_nesne_id": 456,
        "ek_bilgiler": {"telefon": "5551234567", "sure": "15 dakika"}
    }
    """
    try:
        firma_id = session.get('firma_id')
        user_id = session.get('user_id')
        
        if not firma_id or not user_id:
            return jsonify({'success': False, 'error': 'Oturum bilgisi bulunamadı'}), 401
        
        data = request.get_json()
        
        # Validasyon
        if not data.get('musteri_id'):
            return jsonify({'success': False, 'error': 'Müşteri ID gerekli'}), 400
        
        if not data.get('aktivite_tipi'):
            return jsonify({'success': False, 'error': 'Aktivite tipi gerekli'}), 400
        
        if not data.get('baslik'):
            return jsonify({'success': False, 'error': 'Başlık gerekli'}), 400
        
        # Müşteri kontrolü
        musteri = Musteri.query.filter_by(
            MusteriID=data['musteri_id'],
            FirmaID=firma_id
        ).first()
        
        if not musteri:
            return jsonify({'success': False, 'error': 'Müşteri bulunamadı'}), 404
        
        # Aktivite tarihi
        aktivite_tarihi = datetime.now()
        if data.get('aktivite_tarihi'):
            try:
                aktivite_tarihi = datetime.fromisoformat(data['aktivite_tarihi'].replace('Z', '+00:00'))
            except:
                try:
                    aktivite_tarihi = datetime.strptime(data['aktivite_tarihi'], '%Y-%m-%d %H:%M:%S')
                except:
                    pass
        
        # Ek bilgileri JSON string'e çevir
        ek_bilgiler = None
        if data.get('ek_bilgiler'):
            if isinstance(data['ek_bilgiler'], dict):
                ek_bilgiler = json.dumps(data['ek_bilgiler'], ensure_ascii=False)
            else:
                ek_bilgiler = str(data['ek_bilgiler'])
        
        # Yeni aktivite oluştur
        yeni_aktivite = Aktivite(
            MusteriID=data['musteri_id'],
            FirmaID=firma_id,
            AktiviteTipi=data['aktivite_tipi'],
            Baslik=data['baslik'],
            Aciklama=data.get('aciklama'),
            IlgiliNesneTipi=data.get('ilgili_nesne_tipi'),
            IlgiliNesneID=data.get('ilgili_nesne_id'),
            AktiviteTarihi=aktivite_tarihi,
            EkBilgiler=ek_bilgiler,
            OlusturanKullaniciID=user_id
        )
        
        db.session.add(yeni_aktivite)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Aktivite başarıyla oluşturuldu',
            'data': yeni_aktivite.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@aktivite_bp.route('/api/aktiviteler/<int:aktivite_id>', methods=['GET'])
@login_required
def api_aktivite_detay(aktivite_id):
    """
    Aktivite detayı API endpoint'i
    GET /api/aktiviteler/123
    """
    try:
        firma_id = session.get('firma_id')
        
        aktivite = Aktivite.query.filter_by(
            AktiviteID=aktivite_id,
            FirmaID=firma_id
        ).first()
        
        if not aktivite:
            return jsonify({'success': False, 'error': 'Aktivite bulunamadı'}), 404
        
        return jsonify({
            'success': True,
            'data': aktivite.to_dict()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@aktivite_bp.route('/api/aktiviteler/<int:aktivite_id>', methods=['PUT'])
@login_required
def api_aktivite_guncelle(aktivite_id):
    """
    Aktivite güncelleme API endpoint'i
    PUT /api/aktiviteler/123
    """
    try:
        firma_id = session.get('firma_id')
        
        aktivite = Aktivite.query.filter_by(
            AktiviteID=aktivite_id,
            FirmaID=firma_id
        ).first()
        
        if not aktivite:
            return jsonify({'success': False, 'error': 'Aktivite bulunamadı'}), 404
        
        data = request.get_json()
        
        # Güncelleme
        if 'baslik' in data:
            aktivite.Baslik = data['baslik']
        if 'aciklama' in data:
            aktivite.Aciklama = data.get('aciklama')
        if 'aktivite_tipi' in data:
            aktivite.AktiviteTipi = data['aktivite_tipi']
        if 'aktivite_tarihi' in data:
            try:
                aktivite.AktiviteTarihi = datetime.fromisoformat(data['aktivite_tarihi'].replace('Z', '+00:00'))
            except:
                try:
                    aktivite.AktiviteTarihi = datetime.strptime(data['aktivite_tarihi'], '%Y-%m-%d %H:%M:%S')
                except:
                    pass
        if 'ilgili_nesne_tipi' in data:
            aktivite.IlgiliNesneTipi = data.get('ilgili_nesne_tipi')
        if 'ilgili_nesne_id' in data:
            aktivite.IlgiliNesneID = data.get('ilgili_nesne_id')
        if 'ek_bilgiler' in data:
            if isinstance(data['ek_bilgiler'], dict):
                aktivite.EkBilgiler = json.dumps(data['ek_bilgiler'], ensure_ascii=False)
            else:
                aktivite.EkBilgiler = str(data['ek_bilgiler']) if data['ek_bilgiler'] else None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Aktivite başarıyla güncellendi',
            'data': aktivite.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@aktivite_bp.route('/api/aktiviteler/<int:aktivite_id>', methods=['DELETE'])
@login_required
def api_aktivite_sil(aktivite_id):
    """
    Aktivite silme API endpoint'i
    DELETE /api/aktiviteler/123
    """
    try:
        firma_id = session.get('firma_id')
        
        aktivite = Aktivite.query.filter_by(
            AktiviteID=aktivite_id,
            FirmaID=firma_id
        ).first()
        
        if not aktivite:
            return jsonify({'success': False, 'error': 'Aktivite bulunamadı'}), 404
        
        db.session.delete(aktivite)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Aktivite başarıyla silindi'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# =====================================================
# Yardımcı Fonksiyonlar (Mevcut Modüllerle Entegrasyon)
# =====================================================

def create_activity_for_appointment(randevu, aktivite_tipi='appointment'):
    """
    Randevu için otomatik aktivite oluştur
    """
    try:
        # Zaten bu randevu için aktivite var mı kontrol et
        existing = Aktivite.query.filter_by(
            IlgiliNesneTipi='appointment',
            IlgiliNesneID=randevu.RandevuID,
            FirmaID=randevu.FirmaID
        ).first()
        
        if existing:
            # Mevcut aktiviteyi güncelle
            existing.Baslik = f"Randevu: {randevu.RandevuBaslik}"
            existing.Aciklama = randevu.RandevuAciklamasi
            existing.AktiviteTarihi = randevu.RandevuTarihi
            if randevu.MusteriID:
                existing.MusteriID = randevu.MusteriID
            db.session.commit()
            return existing
        else:
            # Yeni aktivite oluştur
            aktivite = Aktivite(
                MusteriID=randevu.MusteriID or 0,  # MusteriID yoksa 0 (manuel randevu)
                FirmaID=randevu.FirmaID,
                AktiviteTipi=aktivite_tipi,
                Baslik=f"Randevu: {randevu.RandevuBaslik}",
                Aciklama=randevu.RandevuAciklamasi,
                IlgiliNesneTipi='appointment',
                IlgiliNesneID=randevu.RandevuID,
                AktiviteTarihi=randevu.RandevuTarihi,
                OlusturanKullaniciID=randevu.OlusturanKullaniciID
            )
            db.session.add(aktivite)
            db.session.commit()
            return aktivite
    except Exception as e:
        db.session.rollback()
        print(f"Aktivite oluşturma hatası (randevu): {e}")
        return None

def create_activity_for_task(todo, aktivite_tipi='task'):
    """
    Görev için otomatik aktivite oluştur
    """
    try:
        # Görev müşteri ile ilişkili mi kontrol et
        if not todo.MusteriAdi and not todo.MusteriSoyadi:
            # Müşteri bilgisi yoksa aktivite oluşturma
            return None
        
        # Müşteriyi bul
        musteri = None
        if todo.MusteriAdi and todo.MusteriSoyadi:
            musteri = Musteri.query.filter_by(
                MusteriAdi=todo.MusteriAdi,
                MusteriSoyadi=todo.MusteriSoyadi,
                FirmaID=todo.kullanici.FirmaID
            ).first()
        
        if not musteri:
            return None
        
        # Zaten bu görev için aktivite var mı kontrol et
        existing = Aktivite.query.filter_by(
            IlgiliNesneTipi='task',
            IlgiliNesneID=todo.TodoID,
            FirmaID=todo.kullanici.FirmaID
        ).first()
        
        if existing:
            # Mevcut aktiviteyi güncelle
            existing.Baslik = f"Görev: {todo.Baslik}"
            existing.Aciklama = todo.Aciklama
            existing.MusteriID = musteri.MusteriID
            if todo.BitisTarihi:
                existing.AktiviteTarihi = todo.BitisTarihi
            db.session.commit()
            return existing
        else:
            # Yeni aktivite oluştur
            aktivite = Aktivite(
                MusteriID=musteri.MusteriID,
                FirmaID=todo.kullanici.FirmaID,
                AktiviteTipi=aktivite_tipi,
                Baslik=f"Görev: {todo.Baslik}",
                Aciklama=todo.Aciklama,
                IlgiliNesneTipi='task',
                IlgiliNesneID=todo.TodoID,
                AktiviteTarihi=todo.BitisTarihi or todo.OlusturmaTarihi,
                OlusturanKullaniciID=todo.KullaniciID
            )
            db.session.add(aktivite)
            db.session.commit()
            return aktivite
    except Exception as e:
        db.session.rollback()
        print(f"Aktivite oluşturma hatası (görev): {e}")
        return None

def get_customer_activities(musteri_id, limit=10):
    """
    Belirli bir müşterinin son aktivitelerini getir
    ORM tabanlı - MySQL ve MSSQL ile uyumlu
    """
    try:
        aktiviteler = Aktivite.query.filter_by(
            MusteriID=musteri_id
        ).order_by(
            Aktivite.AktiviteTarihi.desc()
        ).limit(limit).all()
        
        return aktiviteler
    except Exception as e:
        print(f"Aktivite listesi hatası: {e}")
        return []

def get_customers_without_recent_activities(days=7):
    """
    Son N gün içinde hiç aktivitesi olmayan müşterileri bul
    ORM tabanlı - MySQL ve MSSQL ile uyumlu
    """
    try:
        from sqlalchemy import func
        
        # Bugünden N gün öncesini hesapla
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Son aktivitesi olan müşteri ID'lerini bul
        aktif_musteriler = db.session.query(
            Aktivite.MusteriID
        ).filter(
            Aktivite.AktiviteTarihi >= cutoff_date
        ).distinct().subquery()
        
        # Son aktivitesi olmayan müşterileri bul
        inactive_customers = Musteri.query.filter(
            ~Musteri.MusteriID.in_(
                db.session.query(aktif_musteriler.c.MusteriID)
            ),
            Musteri.Aktif == True
        ).all()
        
        return inactive_customers
    except Exception as e:
        print(f"Pasif müşteri sorgusu hatası: {e}")
        return []





