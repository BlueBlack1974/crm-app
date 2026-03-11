"""
AI Asistan Blueprint - Google Gemini entegrasyonu
Merkezi API key, firma bazlı kullanım limiti
"""
from flask import Blueprint, jsonify, session, request
from app.extensions import db
from app.models import Firma, Randevu, Musteri, Todo, TodoDurum, Kullanici
from app.utils.decorators import login_required
from datetime import datetime, date
from sqlalchemy import func
import os

ai_bp = Blueprint('ai', __name__)

def _get_firma_or_error():
    """Firma'yı getir, AI kontrollerini yap."""
    firma_id = session.get('firma_id')
    if not firma_id:
        return None, jsonify({'success': False, 'error': 'Oturum hatası.'}), 401

    firma = Firma.query.get(firma_id)
    if not firma:
        return None, jsonify({'success': False, 'error': 'Firma bulunamadı.'}), 404

    if not firma.AIAktif:
        return None, jsonify({'success': False, 'error': 'AI Asistan bu firma için aktif değil.'}), 403

    user_id = session.get('user_id')
    if user_id:
        kullanici = Kullanici.query.get(user_id)
        if kullanici and not kullanici.AIModulu:
            return None, jsonify({'success': False, 'error': 'Bu özellik için yetkiniz bulunmamaktadır.'}), 403

    return firma, None, None


def _check_and_increment_limit(firma):
    """Limit kontrolü yap, aşıldıysa False döndür; yoksa sayacı artır."""
    bugun = date.today()
    ay_str = bugun.strftime('%Y-%m')

    # Ay değiştiyse sayacı sıfırla
    if firma.AIKullanimAy != ay_str:
        firma.AIKullanimAy = ay_str
        firma.AIKullanilanSayi = 0

    # Limit kontrolü (0 = sınırsız)
    if firma.AIAylikLimit > 0 and firma.AIKullanilanSayi >= firma.AIAylikLimit:
        return False

    firma.AIKullanilanSayi += 1
    db.session.commit()
    return True


def _call_gemini(prompt: str) -> str:
    """Gemini API'yi çağır ve yanıt döndür."""
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        raise ValueError('GEMINI_API_KEY sunucuda ayarlanmamış.')

    from google import genai
    client = genai.Client(api_key=api_key)
    
    model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')
    response = client.models.generate_content(
        model=model_name,
        contents=prompt
    )
    return response.text


# ─────────────────────────────────────────────
# ENDPOINT 1: Randevu Analizi
# ─────────────────────────────────────────────
@ai_bp.route('/api/ai/randevu-analiz', methods=['POST'])
@login_required
def randevu_analiz():
    firma, err_resp, err_code = _get_firma_or_error()
    if err_resp:
        return err_resp, err_code

    if not _check_and_increment_limit(firma):
        return jsonify({'success': False, 'error': f'Aylık AI limitinize ulaştınız ({firma.AIAylikLimit} istek/ay).'}), 429

    try:
        # Bu ay verilerini topla
        bugun = date.today()
        ay_basi = date(bugun.year, bugun.month, 1)

        randevular = Randevu.query.filter(
            Randevu.FirmaID == firma.FirmaID,
            Randevu.RandevuTarihi >= ay_basi
        ).all()

        # Saat dağılımı
        saat_dagilim = {}
        gun_dagilim = ['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar']
        gun_sayim = {g: 0 for g in gun_dagilim}
        iptal_sayisi = 0
        toplam = len(randevular)

        for r in randevular:
            if r.RandevuTarihi:
                saat = r.RandevuTarihi.hour
                saat_dagilim[saat] = saat_dagilim.get(saat, 0) + 1
                gun_sayim[gun_dagilim[r.RandevuTarihi.weekday()]] += 1
            if r.Durum == 'İptal':
                iptal_sayisi += 1

        en_yogun_saat = max(saat_dagilim, key=saat_dagilim.get) if saat_dagilim else '-'
        en_yogun_gun = max(gun_sayim, key=gun_sayim.get) if gun_sayim else '-'
        en_yogun_saat_str = f"{en_yogun_saat}:00-{en_yogun_saat+1}:00" if isinstance(en_yogun_saat, int) else "-"

        prompt = f"""Sen bir CRM asistanısın. Aşağıda bir işletmenin bu aylık randevu verilerini analiz et ve Türkçe, praktik önerilerde bulun.

VERİLER:
- Bu ay toplam randevu: {toplam}
- İptal sayısı: {iptal_sayisi} ({round(iptal_sayisi/toplam*100) if toplam else 0}%)
- En yoğun gün: {en_yogun_gun} ({gun_sayim.get(en_yogun_gun, 0)} randevu)
- En yoğun saat dilimi: {en_yogun_saat_str}
- Saat dağılımı: {dict(sorted(saat_dagilim.items()))}
- Gün dağılımı: {gun_sayim}

Lütfen şunları içeren kısa bir analiz yaz (max 200 kelime):
1. Genel yorum (2-3 cümle)
2. En yoğun/boş zamanlar hakkında öneri
3. İptal oranı varsa çözüm önerisi
Yanıtı madde madde, sade Türkçe ile yaz."""

        yanit = _call_gemini(prompt)
        return jsonify({
            'success': True,
            'yanit': yanit,
            'kullanilan': firma.AIKullanilanSayi,
            'limit': firma.AIAylikLimit
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────
# ENDPOINT 2: Müşteri Analizi
# ─────────────────────────────────────────────
@ai_bp.route('/api/ai/musteri-analiz', methods=['POST'])
@login_required
def musteri_analiz():
    firma, err_resp, err_code = _get_firma_or_error()
    if err_resp:
        return err_resp, err_code

    musteri_id = request.json.get('musteri_id') if request.is_json else None
    if not musteri_id:
        return jsonify({'success': False, 'error': 'musteri_id gerekli.'}), 400

    if not _check_and_increment_limit(firma):
        return jsonify({'success': False, 'error': f'Aylık AI limitinize ulaştınız ({firma.AIAylikLimit} istek/ay).'}), 429

    try:
        musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma.FirmaID).first()
        if not musteri:
            return jsonify({'success': False, 'error': 'Müşteri bulunamadı.'}), 404

        # Randevu geçmişi
        randevular = Randevu.query.filter_by(MusteriID=musteri_id).order_by(Randevu.RandevuTarihi.desc()).limit(10).all()
        # Görevler
        gorevler = Todo.query.filter_by(MusteriID=musteri_id).order_by(Todo.OlusturmaTarihi.desc()).limit(5).all() if hasattr(Todo, 'MusteriID') else []

        randevu_ozet = []
        for r in randevular:
            randevu_ozet.append(f"- {r.RandevuTarihi.strftime('%d.%m.%Y') if r.RandevuTarihi else '?'}: {r.Durum or '?'}")

        gorev_ozet = []
        for g in gorevler:
            durum = g.durum.DurumAdi if g.durum else '?'
            gorev_ozet.append(f"- {g.Baslik or '?'}: {durum}")

        son_randevu = randevular[0].RandevuTarihi if randevular else None
        gun_fark = (date.today() - son_randevu.date()).days if son_randevu else None

        prompt = f"""Sen bir CRM asistanısın. Aşağıdaki müşteri verisini analiz et ve Türkçe öneriler sun.

MÜŞTERİ: {musteri.Ad} {musteri.Soyad}
Kayıt tarihi: {musteri.OlusturmaTarihi.strftime('%d.%m.%Y') if musteri.OlusturmaTarihi else '?'}
Son randevu: {son_randevu.strftime('%d.%m.%Y') if son_randevu else 'Yok'} ({f'{gun_fark} gün önce' if gun_fark else '-'})

SON 10 RANDEVU:
{chr(10).join(randevu_ozet) if randevu_ozet else 'Randevu yok'}

SON GÖREVLER:
{chr(10).join(gorev_ozet) if gorev_ozet else 'Görev yok'}

Lütfen şunları içeren kısa bir analiz yaz (max 150 kelime):
1. Müşteri sadakat/aktiflik yorumu
2. İptal alışkanlığı varsa belirt
3. {f'Uzun süredir gelmemiş ({gun_fark} gün), yeniden kazanma önerisi' if gun_fark and gun_fark > 60 else 'Müşteriye özel öneri'}
Sade Türkçe, madde madde."""

        yanit = _call_gemini(prompt)
        return jsonify({
            'success': True,
            'yanit': yanit,
            'musteri': f'{musteri.Ad} {musteri.Soyad}',
            'kullanilan': firma.AIKullanilanSayi,
            'limit': firma.AIAylikLimit
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────
# ENDPOINT 3: Rapor Özeti
# ─────────────────────────────────────────────
@ai_bp.route('/api/ai/rapor-ozet', methods=['POST'])
@login_required
def rapor_ozet():
    firma, err_resp, err_code = _get_firma_or_error()
    if err_resp:
        return err_resp, err_code

    if not _check_and_increment_limit(firma):
        return jsonify({'success': False, 'error': f'Aylık AI limitinize ulaştınız ({firma.AIAylikLimit} istek/ay).'}), 429

    try:
        bugun = date.today()
        ay_basi = date(bugun.year, bugun.month, 1)
        gecen_ay_basi = date(bugun.year, bugun.month - 1, 1) if bugun.month > 1 else date(bugun.year - 1, 12, 1)
        gecen_ay_sonu = ay_basi

        # Bu ay
        bu_ay_randevu = Randevu.query.filter(
            Randevu.FirmaID == firma.FirmaID,
            Randevu.RandevuTarihi >= ay_basi
        ).count()
        bu_ay_iptal = Randevu.query.filter(
            Randevu.FirmaID == firma.FirmaID,
            Randevu.RandevuTarihi >= ay_basi,
            Randevu.Durum == 'İptal'
        ).count()
        bu_ay_musteri = Musteri.query.filter(
            Musteri.FirmaID == firma.FirmaID,
            Musteri.OlusturmaTarihi >= ay_basi
        ).count()

        # Geçen ay
        gecen_ay_randevu = Randevu.query.filter(
            Randevu.FirmaID == firma.FirmaID,
            Randevu.RandevuTarihi >= gecen_ay_basi,
            Randevu.RandevuTarihi < gecen_ay_sonu
        ).count()
        gecen_ay_musteri = Musteri.query.filter(
            Musteri.FirmaID == firma.FirmaID,
            Musteri.OlusturmaTarihi >= gecen_ay_basi,
            Musteri.OlusturmaTarihi < gecen_ay_sonu
        ).count()

        # Görev durumları
        gorev_durumlar = db.session.query(
            TodoDurum.DurumAdi, func.count(Todo.TodoID)
        ).join(Todo, Todo.DurumID == TodoDurum.DurumID).filter(
            Todo.Tip == 'Randevu'
        ).group_by(TodoDurum.DurumAdi).all()
        gorev_ozet = ', '.join([f'{d}: {c}' for d, c in gorev_durumlar]) or 'Veri yok'

        randevu_degisim = bu_ay_randevu - gecen_ay_randevu
        musteri_degisim = bu_ay_musteri - gecen_ay_musteri

        prompt = f"""Sen bir CRM iş analistisin. Aşağıdaki aylık rapor verilerini analiz et.
Tarih: {bugun.strftime('%B %Y')}
İşletme: {firma.FirmaAdi}

BU AY:
- Toplam randevu: {bu_ay_randevu} ({'+' if randevu_degisim >= 0 else ''}{randevu_degisim} geçen aya göre)
- İptal: {bu_ay_iptal} ({round(bu_ay_iptal/bu_ay_randevu*100) if bu_ay_randevu else 0}%)
- Yeni müşteri: {bu_ay_musteri} ({'+' if musteri_degisim >= 0 else ''}{musteri_degisim} geçen aya göre)

GEÇEN AY:
- Randevu: {gecen_ay_randevu}
- Yeni müşteri: {gecen_ay_musteri}

GÖREV DURUMLARI: {gorev_ozet}

Lütfen kısa bir yönetici özeti yaz (max 180 kelime):
1. Bu ayın genel değerlendirmesi (1-2 cümle)
2. Olumlu/olumsuz öne çıkan noktalar
3. Önümüzdeki ay için 2 somut öneri
Sade Türkçe, profesyonel ton."""

        yanit = _call_gemini(prompt)
        return jsonify({
            'success': True,
            'yanit': yanit,
            'ay': bugun.strftime('%B %Y'),
            'kullanilan': firma.AIKullanilanSayi,
            'limit': firma.AIAylikLimit
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────
# ENDPOINT 4: API Key Test
# ─────────────────────────────────────────────
@ai_bp.route('/api/ai/test-connection', methods=['POST'])
@login_required
def test_connection():
    if not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Yetkisiz erişim.'}), 403

    try:
        yanit = _call_gemini("Merhaba! Kısa bir Türkçe selamlama cümlesi yaz (10 kelimeden az).")
        return jsonify({'success': True, 'yanit': yanit})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Bağlantı hatası: {e}'}), 500


# ─────────────────────────────────────────────
# AI Kullanım Durumu
# ─────────────────────────────────────────────
@ai_bp.route('/api/ai/kullanim-durumu', methods=['GET'])
@login_required
def kullanim_durumu():
    firma_id = session.get('firma_id')
    firma = Firma.query.get(firma_id)
    if not firma:
        return jsonify({'success': False}), 404

    bugun = date.today()
    ay_str = bugun.strftime('%Y-%m')
    kullanilan = firma.AIKullanilanSayi if firma.AIKullanimAy == ay_str else 0

    return jsonify({
        'success': True,
        'ai_aktif': firma.AIAktif,
        'kullanilan': kullanilan,
        'limit': firma.AIAylikLimit,
        'kalan': max(0, firma.AIAylikLimit - kullanilan) if firma.AIAylikLimit > 0 else None,
        'ay': ay_str
    })
