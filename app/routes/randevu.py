from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_babel import get_locale
from app.extensions import db, csrf
from app.models import (
    Randevu, RandevuYetki, RandevuReferans, RandevuDefterAyar, Kullanici, 
    RandevuIslem, RandevuDefterBlok, Bildirim, Todo, Musteri, MusteriKategori
)
from app.utils.decorators import login_required, admin_required
from sqlalchemy import or_, and_
from datetime import datetime, timedelta, date
from collections import defaultdict

randevu_bp = Blueprint('randevu', __name__)

def check_customer_conflict(musteri_id, randevu_tarihi, sure, exclude_randevu_id=None):
    """
    Belirli bir müşterinin, belirtilen zaman diliminde (farklı bir defterde dahi olsa) 
    başka bir randevusu olup olmadığını kontrol eder.
    """
    if not musteri_id:
        return False, None
        
    randevu_bas = randevu_tarihi
    randevu_bit = randevu_tarihi + timedelta(minutes=sure)
    
    day_start = datetime(randevu_tarihi.year, randevu_tarihi.month, randevu_tarihi.day, 0, 0)
    day_end = day_start + timedelta(days=1)
    
    q = Randevu.query.filter(
        Randevu.MusteriID == musteri_id,
        Randevu.RandevuTarihi >= day_start,
        Randevu.RandevuTarihi < day_end,
        Randevu.Durum != 'iptal'
    )
    
    if exclude_randevu_id:
        q = q.filter(Randevu.RandevuID != exclude_randevu_id)
        
    existing_randevular = q.all()
    
    for r in existing_randevular:
        r_bas = r.RandevuTarihi
        r_bit = r_bas + timedelta(minutes=(r.RandevuSuresi or 60))
        
        # Çakışma var mı?
        if (randevu_bas < r_bit and randevu_bit > r_bas):
            return True, r
            
    return False, None

@randevu_bp.route('/randevular')
@login_required
def randevular():
    # Randevu listesi + referans, defter, durum, tarih ve oluşturan filtresi
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuReferans.Ad).all()
    defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuDefterAyar.DefterAdi).all()
    kullanicilar = Kullanici.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(Kullanici.Ad, Kullanici.Soyad).all()
    
    ref_id = request.args.get('referans_id', type=int)
    defter_id = request.args.get('defter_id', type=int)
    durum = request.args.get('durum')
    olusturan_id = request.args.get('olusturan_id', type=int)
    
    # Tarih filtresi (varsayılan: bugün)
    today_str = datetime.now().strftime('%Y-%m-%d')
    baslangic_str = request.args.get('baslangic', today_str)
    bitis_str = request.args.get('bitis', today_str)
    
    try:
        baslangic = datetime.strptime(baslangic_str, '%Y-%m-%d')
        bitis = datetime.strptime(bitis_str, '%Y-%m-%d')
        # Bitiş tarihini gün sonuna çek
        bitis = bitis.replace(hour=23, minute=59, second=59)
    except ValueError:
        baslangic = datetime.now().replace(hour=0, minute=0, second=0)
        bitis = datetime.now().replace(hour=23, minute=59, second=59)
        baslangic_str = baslangic.strftime('%Y-%m-%d')
        bitis_str = bitis.strftime('%Y-%m-%d')

    # Yetki kontrolu
    if session.get('is_admin', False):
        # Admin tum randevulari gorebilir
        query = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= baslangic,
            Randevu.RandevuTarihi <= bitis
        )
    else:
        # Normal kullanici sadece yetkili oldugu randevulari gorebilir
        query = db.session.query(Randevu).join(RandevuYetki).filter(
            RandevuYetki.KullaniciID == session['user_id'],
            RandevuYetki.GoruntulemeYetkisi == True,
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= baslangic,
            Randevu.RandevuTarihi <= bitis
        )

    # Filtreleri uygula
    if ref_id:
        # Referans filtresi için join gerekebilir veya Randevu modelinde ReferansID varsa
        # Şimdilik pas geçiyorum, modelde ReferansID görmedim
        pass
        
    if defter_id:
        query = query.filter(Randevu.DefterID == defter_id)
        
    if durum:
        query = query.filter(Randevu.Durum == durum)
        
    if olusturan_id:
        query = query.filter(Randevu.OlusturanKullaniciID == olusturan_id)
        
    randevular = query.order_by(Randevu.RandevuTarihi).all()
    
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

@randevu_bp.route('/randevu/<int:randevu_id>')
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
        return redirect(url_for('randevu.randevular'))
    
    return render_template('randevu_detay.html', randevu=randevu)

@randevu_bp.route('/randevu/ekle', methods=['GET', 'POST'])
@login_required
def randevu_ekle():
    if request.method == 'POST':
        # JSON veya form verilerini al
        if request.is_json:
            data = request.get_json()
            tarih_gun = data.get('tarih_gun')
            saat = data.get('selected_saat') or data.get('saat')
            defter_id = data.get('defter_id')
            if isinstance(defter_id, str):
                defter_id = int(defter_id) if defter_id else None
            referans_id = data.get('referans_id')
            if isinstance(referans_id, str):
                referans_id = int(referans_id) if referans_id else None
            islem_id = data.get('islem_id')
            if isinstance(islem_id, str):
                islem_id = int(islem_id) if islem_id else None
            gorev_id = data.get('gorev_id')
            if isinstance(gorev_id, str):
                gorev_id = int(gorev_id) if gorev_id else None
            musteri_adi = data.get('musteri_adi', '')
            musteri_soyadi = data.get('musteri_soyadi', '')
            musteri_telefon = data.get('musteri_telefon', '') or data.get('telefon', '')
            musteri_email = data.get('musteri_email', '') or data.get('email', '')
            aciklama = data.get('aciklama', '') or data.get('randevu_aciklamasi', '')
            baslik = data.get('baslik', '') or data.get('randevu_baslik', '')
            sure = int(data.get('sure', 60)) # Dakika cinsinden süre
            secilen_musteri_id = data.get('secilen_musteri_id')
            
            if not tarih_gun or not saat or not defter_id:
                return jsonify({'success': False, 'message': 'Tarih, saat ve defter seçimi zorunludur!'}), 400
                
            try:
                randevu_tarihi = datetime.strptime(f"{tarih_gun} {saat}", "%Y-%m-%d %H:%M")
            except ValueError:
                return jsonify({'success': False, 'message': 'Geçersiz tarih formatı!'}), 400
                
            # Müşteri çakışma kontrolü
            if secilen_musteri_id:
                has_conflict, c_rnd = check_customer_conflict(secilen_musteri_id, randevu_tarihi, sure)
                if has_conflict:
                    return jsonify({
                        'success': False, 
                        'message': f'Seçili müşterinin bu saatte başka bir randevusu mevcut: {c_rnd.RandevuBaslik}'
                    }), 400
                
            # Müşteri bul veya oluştur
            musteri = None
            musteri_id = None
            
            # Önce secilen_musteri_id kontrolü
            if secilen_musteri_id:
                musteri_id = int(secilen_musteri_id) if isinstance(secilen_musteri_id, str) else secilen_musteri_id
                musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=session['firma_id']).first()
                if musteri:
                    # Müşteri bilgilerini güncelle
                    musteri_adi = musteri_adi or musteri.MusteriAdi
                    musteri_soyadi = musteri_soyadi or musteri.MusteriSoyadi
                    musteri_telefon = musteri_telefon or musteri.Telefon or ''
                    musteri_email = musteri_email or musteri.Email or ''
            
            # Eğer müşteri bulunamadıysa ve ad/soyad varsa yeni müşteri oluştur
            if not musteri and musteri_adi and musteri_soyadi:
                # Telefon numarasına göre kontrol et
                if musteri_telefon:
                    musteri = Musteri.query.filter_by(Telefon=musteri_telefon, FirmaID=session['firma_id']).first()
                
                if not musteri:
                    musteri = Musteri(
                        FirmaID=session['firma_id'],
                        MusteriAdi=musteri_adi,
                        MusteriSoyadi=musteri_soyadi,
                        Telefon=musteri_telefon,
                        Email=musteri_email,
                        OlusturanKullaniciID=session['user_id']
                    )
                    db.session.add(musteri)
                    db.session.flush() # ID almak için flush
                    musteri_id = musteri.MusteriID
            
            # Randevu oluştur
            yeni_randevu = Randevu(
                FirmaID=session['firma_id'],
                RandevuBaslik=baslik or f"{musteri_adi} {musteri_soyadi} Randevusu",
                RandevuAciklamasi=aciklama,
                RandevuTarihi=randevu_tarihi,
                RandevuSuresi=sure,
                MusteriID=musteri.MusteriID if musteri else None,
                MusteriAdi=musteri_adi,
                MusteriSoyadi=musteri_soyadi,
                MusteriTelefon=musteri_telefon,
                MusteriEmail=musteri_email,
                DefterID=defter_id,
                IslemID=islem_id,
                GorevID=gorev_id,
                OlusturanKullaniciID=session['user_id'],
                Durum='Beklemede'
            )
            
            db.session.add(yeni_randevu)
            db.session.flush()
            
            # Yetkileri ekle (oluşturan tam yetkili)
            yetki = RandevuYetki(
                RandevuID=yeni_randevu.RandevuID,
                KullaniciID=session['user_id'],
                GoruntulemeYetkisi=True,
                DuzenlemeYetkisi=True,
                SilmeYetkisi=True
            )
            db.session.add(yetki)
            
            # Adminlere otomatik yetki ver
            adminler = Kullanici.query.filter_by(FirmaID=session['firma_id'], Admin=True).all()
            for admin in adminler:
                if admin.KullaniciID != session['user_id']:
                    admin_yetki = RandevuYetki(
                        RandevuID=yeni_randevu.RandevuID,
                        KullaniciID=admin.KullaniciID,
                        GoruntulemeYetkisi=True,
                        DuzenlemeYetkisi=True,
                        SilmeYetkisi=True
                    )
                    db.session.add(admin_yetki)
            
            db.session.commit()
            
            # Aktivite oluştur (randevu için)
            try:
                from app.routes.aktivite import create_activity_for_appointment
                create_activity_for_appointment(yeni_randevu)
            except Exception as e:
                print(f"Aktivite oluşturma hatası (randevu): {e}")
            
            return jsonify({'success': True, 'message': 'Randevu başarıyla oluşturuldu!', 'randevu_id': yeni_randevu.RandevuID})
            
    # GET isteği için form verilerini hazırla
    defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
    islemler = RandevuIslem.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
    kategoriler = MusteriKategori.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(MusteriKategori.KategoriAdi).all()
    
    return render_template('randevu_ekle.html', 
                         defter_ayarlar=defterler,
                         islemler=islemler,
                         referanslar=referanslar,
                         musteri_kategoriler=kategoriler)

@randevu_bp.route('/randevu/<int:randevu_id>/duzenle', methods=['GET', 'POST'])
@login_required
def randevu_duzenle(randevu_id):
    """Randevu düzenleme sayfası"""
    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first_or_404()
    
    # Yetki kontrolü
    if not session.get('is_admin', False) and randevu.OlusturanKullaniciID != session['user_id']:
        # Yetki tablosundan kontrol et
        yetki = RandevuYetki.query.filter_by(RandevuID=randevu_id, KullaniciID=session['user_id'], DuzenlemeYetkisi=True).first()
        if not yetki:
            flash('Bu randevuyu düzenleme yetkiniz yok', 'error')
            return redirect(url_for('randevu.randevular'))
    
    if request.method == 'POST':
        try:
            # Form verilerini al
            tarih_gun = request.form.get('tarih_gun')  # Template'de tarih_gun kullanılıyor
            saat = request.form.get('saat')
            referans_id = request.form.get('referans_id', type=int)
            randevu_suresi = request.form.get('randevu_suresi', type=int)  # Template'de randevu_suresi kullanılıyor
            randevu_notlar = request.form.get('randevu_notlar', '').strip()
            atanan_kullanici_id = request.form.get('atanan_kullanici', type=int)
            
            if not tarih_gun or not saat or not randevu_suresi:
                flash('Lütfen tüm zorunlu alanları doldurun', 'error')
                return redirect(url_for('randevu.randevu_duzenle', randevu_id=randevu_id))
            
            # Tarih/saat birleştir
            try:
                randevu_dt = datetime.strptime(f"{tarih_gun} {saat}", '%Y-%m-%d %H:%M')
            except ValueError:
                flash('Tarih/saat formatı geçersiz', 'error')
                return redirect(url_for('randevu.randevu_duzenle', randevu_id=randevu_id))
            
            # Referans bilgisini güncelle
            ref = None
            if referans_id:
                ref = RandevuReferans.query.filter_by(ReferansID=referans_id, FirmaID=session['firma_id']).first()
                if ref:
                    randevu.RandevuBaslik = ref.Ad
            
            # Randevu bilgilerini güncelle
            randevu.RandevuTarihi = randevu_dt
            randevu.RandevuSuresi = randevu_suresi
            randevu.RandevuAciklamasi = randevu_notlar
            
            # Müşteri bilgilerini güncelle (eğer müşteri varsa)
            if randevu.musteri:
                telefon_ulke_kodu = request.form.get('telefon_ulke_kodu', '+90')
                telefon_numara = request.form.get('musteri_telefon', '').replace(' ', '').replace('-', '')
                tam_telefon = f"{telefon_ulke_kodu}{telefon_numara}" if telefon_numara else ''
                
                randevu.musteri.Telefon = tam_telefon or randevu.musteri.Telefon
                randevu.musteri.Email = request.form.get('musteri_email', '') or randevu.musteri.Email
                
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
                
                randevu.musteri.Cinsiyet = request.form.get('musteri_cinsiyet', '') or randevu.musteri.Cinsiyet
            
            db.session.commit()
            
            # Aktivite güncelle (randevu için)
            try:
                from app.routes.aktivite import create_activity_for_appointment
                create_activity_for_appointment(randevu)
            except Exception as e:
                print(f"Aktivite güncelleme hatası (randevu): {e}")
            
            flash('Randevu başarıyla güncellendi', 'success')
            return redirect(url_for('randevu.randevu_detay', randevu_id=randevu.RandevuID))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {str(e)}', 'error')
            
    # GET isteği
    defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
    islemler = RandevuIslem.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
    referanslar = RandevuReferans.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(RandevuReferans.Ad).all()
    
    # Min süre hesapla (randevu defterinden)
    min_sure = 30  # Varsayılan
    if randevu.DefterID:
        defter_ayar = RandevuDefterAyar.query.filter_by(AyarID=randevu.DefterID, FirmaID=session['firma_id']).first()
        if defter_ayar:
            min_sure = defter_ayar.SlotDakika
    elif defterler:
        min_sure = defterler[0].SlotDakika if defterler else 30
    
    return render_template('randevu_duzenle.html', 
                         randevu=randevu,
                         defterler=defterler,
                         islemler=islemler,
                         referanslar=referanslar,
                         min_sure=min_sure)

@randevu_bp.route('/randevu/sil/<int:randevu_id>', methods=['POST'])
@login_required
def randevu_sil(randevu_id):
    # Randevuyu ve erisim yetkisini kontrol et
    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
    if not randevu:
        flash('Randevu bulunamadı veya erişim yetkiniz yok', 'error')
        return redirect(url_for('randevu.randevular'))

    is_admin = session.get('is_admin', False)
    has_delete_perm = False
    
    if is_admin:
        has_delete_perm = True
    else:
        perm = RandevuYetki.query.filter_by(
            RandevuID=randevu_id,
            KullaniciID=session['user_id'],
            SilmeYetkisi=True
        ).first()
        if perm:
            has_delete_perm = True
            
    if not has_delete_perm:
        flash('Bu randevuyu silme yetkiniz yok', 'error')
        return redirect(url_for('randevu.randevular'))

    try:
        # Cascade delete ile tüm ilgili kayıtlar otomatik silinir (modelde tanımlıysa)
        # Değilse manuel silmek gerekebilir
        db.session.delete(randevu)
        db.session.commit()
        
        flash('Randevu silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Randevu silinirken hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('randevu.randevular'))

@randevu_bp.route('/api/randevu/tasi', methods=['POST'])
@login_required
def api_randevu_tasi():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "JSON verisi bulunamadı"}), 400
            
        randevu_id = data.get('randevu_id')
        yeni_tarih = data.get('yeni_tarih')  # YYYY-MM-DD HH:MM format
        
        if not randevu_id or not yeni_tarih:
            return jsonify({"success": False, "message": "Eksik parametre"}), 400
        
        randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
        if not randevu:
            return jsonify({"success": False, "message": "Randevu bulunamadı"}), 404
            
        # Yetki kontrolü (düzenleme yetkisi)
        if not session.get('is_admin', False):
            yetki = RandevuYetki.query.filter_by(RandevuID=randevu_id, KullaniciID=session['user_id'], DuzenlemeYetkisi=True).first()
            if not yetki:
                return jsonify({"success": False, "message": "Yetkiniz yok"}), 403
        
        try:
            yeni_dt = datetime.strptime(yeni_tarih, '%Y-%m-%d %H:%M')
            randevu.RandevuTarihi = yeni_dt
            db.session.commit()
            return jsonify({"success": True, "message": "Randevu taşındı"})
        except ValueError:
            return jsonify({"success": False, "message": "Geçersiz tarih formatı"}), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@randevu_bp.route('/api/randevu-slotlari', methods=['GET'])
@login_required
def api_randevu_slotlari():
    """Randevu slotlarını getir"""
    try:
        tarih = request.args.get('tarih')
        defter_id = request.args.get('defter_id')
        
        if not tarih or not defter_id:
            return jsonify({'success': False, 'message': 'Tarih ve defter ID gerekli!'}), 400
        
        # Defter ayarlarını al
        defter_ayar = RandevuDefterAyar.query.filter_by(AyarID=defter_id, FirmaID=session['firma_id']).first()
        if not defter_ayar:
            return jsonify({'success': False, 'message': 'Defter bulunamadı!'}), 404
            
        gun = datetime.strptime(tarih, '%Y-%m-%d').date()
        
        # Çalışma saatleri
        bas_saat = defter_ayar.BaslangicSaati or "09:00"
        bit_saat = defter_ayar.BitisSaati or "18:00"
        slot_dk = defter_ayar.SlotDakika or 30
        
        bas_dt = datetime.strptime(f"{tarih} {bas_saat}", "%Y-%m-%d %H:%M")
        bit_dt = datetime.strptime(f"{tarih} {bit_saat}", "%Y-%m-%d %H:%M")
        
        # Mevcut randevuları al
        randevular = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID == defter_id,
            Randevu.RandevuTarihi >= bas_dt,
            Randevu.RandevuTarihi < bit_dt,
            Randevu.Durum != 'İptal'
        ).all()
        
        # Blokları al
        bloklar = RandevuDefterBlok.query.filter(
            RandevuDefterBlok.FirmaID == session['firma_id'],
            RandevuDefterBlok.Aktif == True,
            RandevuDefterBlok.BaslangicTarih <= gun,
            or_(RandevuDefterBlok.BitisTarih == None, RandevuDefterBlok.BitisTarih >= gun),
            or_(RandevuDefterBlok.DefterID == None, RandevuDefterBlok.DefterID == defter_id)
        ).all()
        
        def is_blocked(start, end):
            for b in bloklar:
                if not b.SaatBaslangic or not b.SaatBitis:
                    return True # Tüm gün bloklu
                
                try:
                    b_start = datetime.strptime(f"{tarih} {b.SaatBaslangic}", "%Y-%m-%d %H:%M")
                    b_end = datetime.strptime(f"{tarih} {b.SaatBitis}", "%Y-%m-%d %H:%M")
                    
                    if start < b_end and end > b_start:
                        return True
                except:
                    continue
            return False
            
        def is_occupied(start, end):
            for r in randevular:
                r_end = r.RandevuTarihi + timedelta(minutes=r.RandevuSuresi)
                if start < r_end and end > r.RandevuTarihi:
                    return True
            return False

        slots = []
        curr = bas_dt
        while curr + timedelta(minutes=slot_dk) <= bit_dt:
            end = curr + timedelta(minutes=slot_dk)
            
            status = 'available'
            if is_blocked(curr, end):
                status = 'blocked'
            elif is_occupied(curr, end):
                status = 'occupied'
                
            slots.append({
                'time': curr.strftime('%H:%M'),
                'status': status
            })
            curr = end
            
        return jsonify({
            'success': True,
            'slotlar': [s['time'] for s in slots if s['status'] == 'available'],
            'tum_slotlar': slots
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@randevu_bp.route('/api/randevu-defterleri', methods=['GET'])
@login_required
def api_randevu_defterleri():
    """Randevu defterlerini getir"""
    try:
        defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
        
        defter_listesi = []
        for d in defterler:
            defter_listesi.append({
                'AyarID': d.AyarID, 
                'DefterAdi': d.DefterAdi,
                'SlotDakika': d.SlotDakika
            })
        
        return jsonify({
            'success': True,
            'defterler': defter_listesi
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@randevu_bp.route('/randevu/durum/<int:randevu_id>', methods=['POST'])
@login_required
def randevu_durum(randevu_id):
    yeni_durum = request.form.get('durum')
    if yeni_durum not in ['Beklemede', 'Onaylandi', 'Iptal', 'Tamamlandi']:
        flash('Geçersiz durum', 'error')
        return redirect(url_for('randevu.randevular'))

    randevu = Randevu.query.filter_by(RandevuID=randevu_id, FirmaID=session['firma_id']).first()
    if not randevu:
        flash('Randevu bulunamadı veya erişim yetkiniz yok', 'error')
        return redirect(url_for('randevu.randevular'))

    is_admin = session.get('is_admin', False)
    # Yetki kontrolü
    if not is_admin:
        # Düzenleme yetkisi kontrolü
        yetki = RandevuYetki.query.filter_by(
            RandevuID=randevu_id, 
            KullaniciID=session['user_id'], 
            DuzenlemeYetkisi=True
        ).first()
        
        if not yetki and randevu.OlusturanKullaniciID != session['user_id']:
            flash('Bu randevunun durumunu değiştirme yetkiniz yok', 'error')
            return redirect(url_for('randevu.randevular'))

    eski_durum = randevu.Durum
    randevu.Durum = yeni_durum
    randevu.GuncellemeTarihi = datetime.now()
    
    db.session.commit()
    
    # Eğer randevu iptal edildiyse, slot'u açık hale getir
    if yeni_durum == 'Iptal':
        # Randevu iptal edildiğinde slot artık kullanılabilir
        # Bu durumda slot API'si otomatik olarak bu slot'u açık gösterecek
        pass
    
    flash('Randevu durumu güncellendi', 'success')
    return redirect(url_for('randevu.randevular'))

@randevu_bp.route('/takvim')
@login_required
def takvim():
    import calendar
    
    # Parametreler
    year = request.args.get('year', type=int) or datetime.now().year
    month = request.args.get('month', type=int) or datetime.now().month
    view_type = request.args.get('view', 'month')  # month, week
    defter_id = request.args.get('defter_id', type=int)
    week_start_param = request.args.get('week_start')
    
    # Tarih aralığını belirle
    if view_type == 'month':
        # Ayın ilk ve son günü
        start_date = datetime(year, month, 1)
        # Ayın son günü
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)
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
        defterler = RandevuDefterAyar.query.filter_by(FirmaID=session['firma_id'], Aktif=True).all()
    else:
        # Normal kullanıcılar için defter listesi
        from sqlalchemy import distinct
        kullanici_defter_ids = db.session.query(distinct(Randevu.DefterID)).filter(
            Randevu.OlusturanKullaniciID == session['user_id'],
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID.isnot(None)
        ).all()
        
        defter_id_list = [defter_id[0] for defter_id in kullanici_defter_ids if defter_id[0] is not None]
        
        if defter_id_list:
            defterler = RandevuDefterAyar.query.filter(
                RandevuDefterAyar.AyarID.in_(defter_id_list),
                RandevuDefterAyar.FirmaID == session['firma_id'],
                RandevuDefterAyar.Aktif == True
            ).all()
        else:
            defterler = []
    
    # Eğer defter seçilmemişse haftalık görünümde ilk defter seçili gelir
    if not defter_id and view_type == 'week' and defterler:
        defter_id = defterler[0].AyarID
    
    # Randevuları getir
    if session.get('is_admin', False):
        query = db.session.query(Randevu, RandevuIslem).outerjoin(RandevuIslem, Randevu.IslemID == RandevuIslem.IslemID).filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.RandevuTarihi >= start_date,
            Randevu.RandevuTarihi < end_date,
            Randevu.Durum != 'Iptal'
        )
        if defter_id:
            query = query.filter(Randevu.DefterID == defter_id)
        results = query.order_by(Randevu.RandevuTarihi).all()
        randevular = []
        for randevu, islem in results:
            randevu.islem_adi = islem.IslemAdi if islem else None
            randevular.append(randevu)
    else:
        if 'defter_id_list' in locals() and defter_id_list:
            query = db.session.query(Randevu, RandevuIslem).outerjoin(RandevuIslem, Randevu.IslemID == RandevuIslem.IslemID).filter(
                Randevu.FirmaID == session['firma_id'],
                Randevu.RandevuTarihi >= start_date,
                Randevu.RandevuTarihi < end_date,
                Randevu.Durum != 'Iptal',
                Randevu.DefterID.in_(defter_id_list)
            )
            if defter_id:
                query = query.filter(Randevu.DefterID == defter_id)
            results = query.order_by(Randevu.RandevuTarihi).all()
            randevular = []
            for randevu, islem in results:
                randevu.islem_adi = islem.IslemAdi if islem else None
                randevular.append(randevu)
        else:
            randevular = []
    
    # Haftalık görünüm için değişkenler
    week_start = start_date.date() if view_type == 'week' else None
    prev_week_start = (start_date - timedelta(days=7)).strftime('%Y-%m-%d') if view_type == 'week' else None
    next_week_start = (start_date + timedelta(days=7)).strftime('%Y-%m-%d') if view_type == 'week' else None
    
    # Haftalık görünüm için tarih aralığı başlığı
    week_range_title = None
    if view_type == 'week':
        week_end = start_date + timedelta(days=6)
        # Kullanıcının diline göre ay isimleri
        lang = str(get_locale())
        month_names = {
            'tr': ['', 'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 
                   'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'],
            'en': ['', 'January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December'],
            'de': ['', 'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
                   'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
            'fr': ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                   'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        }
        months = month_names.get(lang, month_names['tr'])
        if start_date.month == week_end.month:
            # Aynı ay içinde
            week_range_title = f"{start_date.day} - {week_end.day} {months[start_date.month]} {start_date.year}"
        else:
            # Farklı aylar
            week_range_title = f"{start_date.day} {months[start_date.month]} - {week_end.day} {months[week_end.month]} {week_end.year}"
    
    # start_date ve end_date'i date objesine çevir
    from datetime import date as date_type
    start_date_val = start_date.date() if isinstance(start_date, datetime) else start_date
    if view_type == 'week':
        end_date_val = (end_date - timedelta(days=1)).date() if isinstance(end_date, datetime) else (end_date - timedelta(days=1))
    else:
        end_date_val = end_date.date() if isinstance(end_date, datetime) else end_date
    
    return render_template('takvim.html',
                         randevular=randevular,
                         year=year,
                         month=month,
                         view_type=view_type,
                         defter_id=defter_id,
                         selected_defter_id=defter_id,
                         week_start=week_start.strftime('%Y-%m-%d') if week_start else None,
                         prev_week_start=prev_week_start,
                         next_week_start=next_week_start,
                         week_range_title=week_range_title,
                         start_date=start_date_val,
                         end_date=end_date_val,
                         defterler=defterler)

# API: Secilebilir saat slotlari
@randevu_bp.route('/api/slots')
@login_required
def api_slots():
    # Inputs
    date_str = request.args.get('date')  # YYYY-MM-DD
    defter_id = request.args.get('defter_id', type=int)
    musteri_id = request.args.get('musteri_id', type=int)
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

    # O gun var olan randevular (sadece seçili defter için)
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0)
    day_end = day_start + timedelta(days=1)
    existing = Randevu.query.filter(
        Randevu.FirmaID == firma_id,
        Randevu.DefterID == defter_id,  # Sadece seçili defter
        Randevu.RandevuTarihi >= day_start,
        Randevu.RandevuTarihi < day_end,
        Randevu.Durum != 'iptal'  # İptal edilen randevuları hariç tut
    ).all()

    def is_overlapping(slot_start: datetime, slot_end: datetime) -> bool:
        # Önce defterdeki mevcut randevularla çakışmaya bak
        for r in existing:
            r_start = r.RandevuTarihi
            r_end = r_start + timedelta(minutes=(r.RandevuSuresi or 60))
            if r_start < slot_end and slot_start < r_end:
                return True
                
        # Eğer musteri_id verilmişse, müşterinin başka defterlerdeki (veya bu defterdeki) 
        # randevularıyla çakışmasını da kontrol et
        if musteri_id:
            has_conflict, _ = check_customer_conflict(musteri_id, slot_start, slot_dk)
            if has_conflict:
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
@randevu_bp.route('/api/slot/check', methods=['POST'])
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
        
        musteri_id = data.get('musteri_id')
        if musteri_id:
            try:
                musteri_id = int(musteri_id)
            except ValueError:
                musteri_id = None
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
        q = Randevu.query.filter(
            Randevu.FirmaID == session['firma_id'],
            Randevu.DefterID == defter_id,
            Randevu.RandevuTarihi >= day_start,
            Randevu.RandevuTarihi < day_end,
            Randevu.Durum != 'iptal'
        )
        
        if exclude_randevu_id:
            q = q.filter(Randevu.RandevuID != exclude_randevu_id)
            
        existing_randevular = q.all()
        
        cakisma = False
        cakisan_randevu = None
        
        for r in existing_randevular:
            r_bas = r.RandevuTarihi
            r_bit = r_bas + timedelta(minutes=(r.RandevuSuresi or 60))
            
            if (randevu_bas < r_bit and randevu_bit > r_bas):
                cakisma = True
                cakisan_randevu = r
                break
        
        if cakisma:
            return jsonify({
                "success": True, 
                "available": False, 
                "message": "Seçilen saatte başka bir randevu mevcut",
                "cakisan_randevu": {
                    "baslik": cakisan_randevu.RandevuBaslik,
                    "saat": cakisan_randevu.RandevuTarihi.strftime('%H:%M')
                }
            })
            
        # Müşterinin başka bir randevusu var mı? (Tüm defterlerde)
        if musteri_id:
            has_conflict, c_randevu = check_customer_conflict(musteri_id, randevu_dt, randevu_suresi, exclude_randevu_id)
            if has_conflict:
                return jsonify({
                    "success": True, 
                    "available": False, 
                    "message": "Bu müşterinin aynı saatte başka bir randevusu mevcut",
                    "cakisan_randevu": {
                        "baslik": c_randevu.RandevuBaslik,
                        "saat": c_randevu.RandevuTarihi.strftime('%H:%M')
                    }
                })
            
        # Blok kontrolü
        bloklar = RandevuDefterBlok.query.filter(
            RandevuDefterBlok.FirmaID == session['firma_id'],
            RandevuDefterBlok.Aktif == True,
            RandevuDefterBlok.BaslangicTarih <= randevu_dt.date(),
            or_(RandevuDefterBlok.BitisTarih == None, RandevuDefterBlok.BitisTarih >= randevu_dt.date()),
            or_(RandevuDefterBlok.DefterID == None, RandevuDefterBlok.DefterID == defter_id)
        ).all()
        
        bloklu = False
        for b in bloklar:
            if not b.SaatBaslangic or not b.SaatBitis:
                bloklu = True
                break
                
            try:
                b_bas = datetime.strptime(f"{tarih_str} {b.SaatBaslangic}", "%Y-%m-%d %H:%M")
                b_bit = datetime.strptime(f"{tarih_str} {b.SaatBitis}", "%Y-%m-%d %H:%M")
                
                if (randevu_bas < b_bit and randevu_bit > b_bas):
                    bloklu = True
                    break
            except:
                continue
                
        if bloklu:
            return jsonify({
                "success": True, 
                "available": False, 
                "message": "Seçilen saat aralığı bloklanmış (mola/tatil)"
            })
            
        return jsonify({"success": True, "available": True, "message": "Müsait"})
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Hata: {str(e)}"}), 500

@randevu_bp.route('/api/randevu/seri-kaydet', methods=['POST'])
@login_required
@csrf.exempt
def api_randevu_seri_kaydet():
    """Toplu randevu serisi kaydetme"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "JSON verisi bulunamadı"}), 400
            
        baslik = data.get('baslik')
        defter_id = data.get('defter_id')
        musteri_id = data.get('musteri_id')
        islem_id = data.get('islem_id')
        aciklama = data.get('aciklama', '')
        randevular_data = data.get('randevular', [])
        
        if not baslik or not defter_id or not musteri_id or not randevular_data:
            return jsonify({"success": False, "message": "Eksik parametreler. Başlık, Defter, Müşteri ve en az 1 tarih gerekli."}), 400
            
        # Müşteriyi bul
        from app.models import Musteri, RandevuIslem, RandevuDefterAyar, RandevuSeri
        musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=session['firma_id']).first()
        if not musteri:
            return jsonify({"success": False, "message": "Müşteri bulunamadı"}), 404
            
        # Randevu serisini oluştur
        yeni_seri = RandevuSeri(
            FirmaID=session['firma_id'],
            MusteriID=musteri.MusteriID,
            DefterID=defter_id,
            IslemID=islem_id if islem_id else None,
            Baslik=baslik,
            ToplamRandevu=len(randevular_data),
            Aciklama=aciklama,
            OlusturanKullaniciID=session['user_id']
        )
        
        db.session.add(yeni_seri)
        db.session.flush() # SeriID'yi almak için
        
        eklenen_randevular = []
        for index, rnd_data in enumerate(randevular_data):
            try:
                tarih_str = rnd_data.get('tarih')
                saat_str = rnd_data.get('saat')
                sure = rnd_data.get('sure', 60)
                
                randevu_dt = datetime.strptime(f"{tarih_str} {saat_str}", "%Y-%m-%d %H:%M")
                
                # Müşteri çakışma kontrolü
                has_conflict, c_rnd = check_customer_conflict(musteri_id, randevu_dt, sure)
                if has_conflict:
                    print(f"[WARN] Müşteri çakışması tespit edildi: {tarih_str} {saat_str}")
                    # Eğer çakışma varsa bu slotu atlayabilir veya hata verebiliriz. 
                    # Kullanıcı "başka saate olabilir" dediği için seride çakışanları atlamak yerine 
                    # kayıt sırasında hata verip düzeltmesini istemek daha güvenli olabilir.
                    # Ancak seri planlama sırasında slotlar zaten boş olanlara göre hesaplandığı için 
                    # buraya düşmesi eşzamanlı bir kayıt durumunda olur.
                    continue
                
                yeni_randevu = Randevu(
                    RandevuBaslik=f"{baslik} - Seans {index+1}",
                    RandevuAciklamasi=aciklama,
                    RandevuTarihi=randevu_dt,
                    RandevuSuresi=sure,
                    MusteriID=musteri.MusteriID,
                    MusteriAdi=musteri.MusteriAdi,
                    MusteriSoyadi=musteri.MusteriSoyadi,
                    MusteriTelefon=musteri.Telefon,
                    MusteriEmail=musteri.Email,
                    IslemID=islem_id if islem_id else None,
                    OlusturanKullaniciID=session['user_id'],
                    FirmaID=session['firma_id'],
                    DefterID=defter_id,
                    SeriID=yeni_seri.SeriID,
                    SeriNo=index + 1
                )
                db.session.add(yeni_randevu)
                eklenen_randevular.append(yeni_randevu)
            except Exception as item_err:
                print(f"[WARN] Randevu öğesi eklenirken hata: {item_err}")
                continue
                
        # Eğer hiçbiri eklenemediyse hata ver
        if not eklenen_randevular:
            db.session.rollback()
            return jsonify({"success": False, "message": "Geçerli tarih/saat bilgisi bulunamadı."}), 400
            
        # Admin değilse yetkileri ekle
        is_admin = session.get('is_admin', False)
        if not is_admin:
            db.session.flush() # Randevu ID'lerini almak için
            for r in eklenen_randevular:
                yeni_yetki = RandevuYetki(
                    RandevuID=r.RandevuID,
                    KullaniciID=session['user_id'],
                    GoruntulemeYetkisi=True,
                    DuzenlemeYetkisi=True,
                    SilmeYetkisi=True
                )
                db.session.add(yeni_yetki)
                
        # Aktivite loglarını (ve diğer logları) oluştur
        try:
            from app.routes.aktivite import create_activity_for_appointment
            from app.utils.logging import log_user_action
            
            for r in eklenen_randevular:
                create_activity_for_appointment(r)
                log_user_action('CREATE', 'Randevu', r.RandevuID, 
                                detail=f"Randevu serisi oluşturuldu: {r.RandevuTarihi.strftime('%d.%m.%Y %H:%M')} - {r.MusteriAdi}")
        except Exception as e:
            print(f"[WARN] Randevu serisi için log oluşturma hatası: {e}")
            
        db.session.commit()
        return jsonify({
            "success": True, 
            "message": f"Randevu serisi ve {len(eklenen_randevular)} randevu başarıyla oluşturuldu.",
            "seri_id": yeni_seri.SeriID
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Sunucu hatası: {str(e)}"}), 500

