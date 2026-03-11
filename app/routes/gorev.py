from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.extensions import db
from app.models import (
    Todo, TodoDurum, Randevu, RandevuYetki, RandevuDefterAyar, 
    Bildirim, KullaniciLog, Musteri, RandevuIslem, RandevuReferans, Kullanici
)
from app.utils.decorators import login_required
from app.utils.logging import log_user_action
from app.utils.helpers import get_client_ip
from sqlalchemy import or_, and_, func
from datetime import datetime, timedelta
import json

gorev_bp = Blueprint('gorev', __name__)

def create_default_todo_durumlar(firma_id, durum_adi):
    """Yapılacaklar için varsayılan durumları oluştur"""
    try:
        # Varsayılan durumları oluştur
        default_durumlar = [
            {'DurumAdi': 'Beklemede', 'Renk': '#ffc107', 'Sira': 1, 'Aktif': True},
            {'DurumAdi': 'Devam Ediyor', 'Renk': '#17a2b8', 'Sira': 2, 'Aktif': True},
            {'DurumAdi': 'Tamamlandı', 'Renk': '#28a745', 'Sira': 3, 'Aktif': True}
        ]
        
        for durum_data in default_durumlar:
            # Durum zaten var mı kontrol et
            existing = TodoDurum.query.filter_by(
                DurumAdi=durum_data['DurumAdi'], 
                FirmaID=firma_id
            ).first()
            
            if not existing:
                yeni_durum = TodoDurum(
                    DurumAdi=durum_data['DurumAdi'],
                    Renk=durum_data['Renk'],
                    Sira=durum_data['Sira'],
                    Aktif=durum_data['Aktif'],
                    FirmaID=firma_id
                )
                db.session.add(yeni_durum)
        
        db.session.commit()
        
        # İstenen durumun ID'sini döndür
        durum = TodoDurum.query.filter_by(DurumAdi=durum_adi, FirmaID=firma_id).first()
        return durum.DurumID if durum else None
        
    except Exception as e:
        print(f"Varsayılan durumlar oluşturulurken hata: {e}")
        db.session.rollback()
        return None

@gorev_bp.route('/gorevler')
@login_required
def gorevler():
    """Görev listesi sayfası - Randevu bazlı görevler"""
    firma_id = session['firma_id']
    
    # Kullanıcının randevu bazlı TÜM görevlerini getir (tamamlananlar dahil).
    # Ekranda varsayılan olarak tamamlananlar JS ile gizlenecek; filtre 'Tamamlandı' seçildiğinde gösterilecek.
    user_todos = (Todo.query
        .filter_by(KullaniciID=session['user_id'], Tip='Randevu')
        .order_by(Todo.Oncelik.desc(), Todo.OlusturmaTarihi.desc())
        .all())
    
    # Firma bazlı durumları getir
    durumlar = TodoDurum.query.filter_by(FirmaID=firma_id, Aktif=True).order_by(TodoDurum.Sira).all()
    
    # Her durum için sayıları DB'den güvenilir şekilde hesapla (tamamlananlar dahil)
    counts_by_name = dict(
        db.session.query(TodoDurum.DurumAdi, func.count(Todo.TodoID))
        .join(Todo, Todo.DurumID == TodoDurum.DurumID)
        .filter(Todo.KullaniciID == session['user_id'], Todo.Tip == 'Randevu')
        .group_by(TodoDurum.DurumAdi)
        .all()
    )
    durum_istatistikleri = [
        {
            'durum': durum,
            'sayi': int(counts_by_name.get(durum.DurumAdi, 0) or 0)
        }
        for durum in durumlar
    ]
    
    # Toplam görev sayısı
    toplam_gorev = len(user_todos)
    
    # Yaklaşan hatırlatmalar (bugünden itibaren 3 gün)
    bugun = datetime.now().date()
    uc_gun_sonra = bugun + timedelta(days=3)
    yaklasan_gorevler = [t for t in user_todos 
                        if t.HatirlatmaTarihi and (not t.durum or t.durum.DurumAdi != 'Tamamlandı')
                        and bugun <= t.HatirlatmaTarihi.date() <= uc_gun_sonra]
    
    # Bu ayın ilk ve son gününü hesapla
    from datetime import date
    today = date.today()
    first_day_of_month = date(today.year, today.month, 1)
    if today.month == 12:
        last_day_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)
    
    return render_template('gorevler.html', 
                         gorevler=user_todos,
                         toplam_gorev=toplam_gorev,
                         durum_istatistikleri=durum_istatistikleri,
                         yaklasan_gorevler=yaklasan_gorevler,
                         first_day_of_month=first_day_of_month,
                         last_day_of_month=last_day_of_month)

@gorev_bp.route('/gorev-raporlar')
@login_required
def gorev_raporlar():
    """Görev raporları sayfası"""
    return render_template('gorev_raporlar.html')

@gorev_bp.route('/todos')
@login_required
def todos():
    """Todo listesi sayfası - Kişisel yapılacaklar"""
    # Kullanıcının sadece kişisel yapılacaklarını getir
    user_todos = Todo.query.filter_by(KullaniciID=session['user_id'], Tip='Kisisel').order_by(
        Todo.Oncelik.desc(), Todo.OlusturmaTarihi.desc()
    ).all()
    
    # İstatistikler
    toplam_todo = len(user_todos)
    tamamlanan_todo = len([t for t in user_todos if t.durum and t.durum.DurumAdi == 'Tamamlandı'])
    beklemede_todo = len([t for t in user_todos if t.durum and t.durum.DurumAdi == 'Beklemede'])
    devam_eden_todo = len([t for t in user_todos if t.durum and t.durum.DurumAdi == 'Devam Ediyor'])
    
    # Yaklaşan hatırlatmalar (bugünden itibaren 3 gün)
    bugun = datetime.now().date()
    uc_gun_sonra = bugun + timedelta(days=3)
    yaklasan_todos = [t for t in user_todos 
                     if t.HatirlatmaTarihi and (not t.durum or t.durum.DurumAdi != 'Tamamlandı')
                     and bugun <= t.HatirlatmaTarihi.date() <= uc_gun_sonra]
    
    return render_template('todos.html', 
                         todos=user_todos,
                         toplam_todo=toplam_todo,
                         tamamlanan_todo=tamamlanan_todo,
                         beklemede_todo=beklemede_todo,
                         devam_eden_todo=devam_eden_todo,
                         yaklasan_todos=yaklasan_todos)

@gorev_bp.route('/todos/ekle', methods=['POST'])
@login_required
def todo_ekle():
    """Yeni todo ekle"""
    try:
        data = request.get_json()
        
        # Tarih formatlarını parse et
        bitis_tarihi = None
        if data.get('bitis_tarihi'):
            bitis_tarihi = datetime.strptime(data['bitis_tarihi'], '%Y-%m-%d')
        
        hatirlatma_tarihi = None
        if data.get('hatirlatma_tarihi'):
            hatirlatma_tarihi = datetime.strptime(data['hatirlatma_tarihi'], '%Y-%m-%d')
        
        # Randevu tarihini parse et
        randevu_tarihi = None
        if data.get('randevu_tarihi'):
            randevu_tarihi = datetime.strptime(data['randevu_tarihi'], '%Y-%m-%d').date()
        
        # Durum ID'sini al - önce durum_id, sonra durum adından
        durum_id = None
        if data.get('durum_id'):
            # Direkt durum ID'si gönderilmiş
            durum_id = int(data['durum_id'])
        elif data.get('durum'):
            # Durum adından ID'yi bul (firma kontrolü yok)
            durum = TodoDurum.query.filter_by(DurumAdi=data['durum']).first()
            if durum:
                durum_id = durum.DurumID
            else:
                # Eğer durum bulunamazsa varsayılan durumları oluştur
                durum_id = create_default_todo_durumlar(session['firma_id'], data['durum'])
        
        # Tip belirleme
        todo_tip = data.get('tip', 'Kisisel')
        
        # Yeni todo oluştur
        yeni_todo = Todo(
            KullaniciID=session['user_id'],
            Baslik=data['baslik'],
            Aciklama=data.get('aciklama', ''),
            Oncelik=data.get('oncelik', 'Orta'),
            DurumID=durum_id,  # Yeni durum sistemi
            Tip=todo_tip,  # Kisisel veya Randevu
            BitisTarihi=bitis_tarihi,
            HatirlatmaTarihi=hatirlatma_tarihi,
            # Müşteri bilgileri
            MusteriAdi=data.get('musteri_adi', ''),
            MusteriSoyadi=data.get('musteri_soyadi', ''),
            MusteriTelefon=data.get('musteri_telefon', ''),
            MusteriEmail=data.get('musteri_email', ''),
            # Randevu bilgileri (eğer görev ise)
            RandevuTarihi=randevu_tarihi,
            RandevuDefteriID=data.get('randevu_defteri_id'),
            RandevuSaati=data.get('selected_randevu_saat'),
            AtananKullaniciID=data.get('kullanici_id')
        )
        
        db.session.add(yeni_todo)
        db.session.flush()  # ID'yi almak için
        
        # Eğer randevu bilgileri varsa randevu oluştur
        if (data.get('randevu_tarihi') and data.get('randevu_defteri_id') and 
            data.get('selected_randevu_saat')):
            
            try:
                # Randevu tarihini parse et
                randevu_dt = datetime.strptime(f"{data['randevu_tarihi']} {data['selected_randevu_saat']}", '%Y-%m-%d %H:%M')
                
                # Randevu defterini kontrol et
                defter_ayar = RandevuDefterAyar.query.filter_by(
                    AyarID=data['randevu_defteri_id'], 
                    FirmaID=session['firma_id'], 
                    Aktif=True
                ).first()
                
                if defter_ayar:
                    # Çakışma kontrolü
                    randevu_suresi = defter_ayar.SlotDakika  # Defter ayarındaki slot dakikası
                    randevu_bas = randevu_dt
                    randevu_bit = randevu_dt + timedelta(minutes=randevu_suresi)
                    
                    # Mevcut randevularla çakışma kontrolü
                    day_start_chk = datetime(randevu_dt.year, randevu_dt.month, randevu_dt.day, 0, 0)
                    day_end_chk = day_start_chk + timedelta(days=1)
                    
                    existing_randevular = Randevu.query.filter(
                        Randevu.FirmaID == session['firma_id'],
                        Randevu.DefterID == data['randevu_defteri_id'],
                        Randevu.RandevuTarihi >= day_start_chk,
                        Randevu.RandevuTarihi < day_end_chk,
                        Randevu.Durum != 'Iptal'
                    ).all()
                    
                    cakisma_var = False
                    for r in existing_randevular:
                        r_start = r.RandevuTarihi
                        r_dur = r.RandevuSuresi or 60
                        r_end = r_start + timedelta(minutes=int(r_dur))
                        if r_start < randevu_bit and randevu_bas < r_end:
                            cakisma_var = True
                            break
                    
                    if not cakisma_var:
                        # Randevu oluştur
                        randevu = Randevu(
                            RandevuBaslik=data['baslik'],
                            RandevuAciklamasi=data.get('aciklama', ''),
                            RandevuTarihi=randevu_dt,
                            RandevuSuresi=randevu_suresi,
                            MusteriAdi=data.get('musteri_adi', ''),
                            MusteriSoyadi=data.get('musteri_soyadi', 'Müşteri'),
                            MusteriTelefon=data.get('musteri_telefon', ''),
                            MusteriEmail=data.get('musteri_email', ''),
                            OlusturanKullaniciID=session['user_id'],
                            FirmaID=session['firma_id'],
                            DefterID=data['randevu_defteri_id'],
                            GorevID=yeni_todo.TodoID  # Görev ID'sini bağla
                        )
                        
                        db.session.add(randevu)
                        db.session.flush()  # Randevu ID'sini almak için
                        
                        # Todo'ya RandevuID'yi ekle
                        yeni_todo.RandevuID = randevu.RandevuID
                        
                        # Kullanıcıya randevu yetkisi ver
                        try:
                            randevu_yetki = RandevuYetki(
                                RandevuID=randevu.RandevuID,
                                KullaniciID=session['user_id'],
                                GoruntulemeYetkisi=True,
                                DuzenlemeYetkisi=True,
                                SilmeYetkisi=True
                            )
                            db.session.add(randevu_yetki)
                        except Exception as yetki_error:
                            print(f"Randevu yetkisi ekleme hatası: {yetki_error}")
                        
                    else:
                        print("Randevu oluşturulamadı: Çakışma var")
                else:
                    print("Randevu defteri bulunamadı")
                    
            except Exception as randevu_error:
                print(f"Randevu oluşturma hatası: {randevu_error}")
                # Randevu hatası olsa bile todo'yu kaydet
        
        db.session.commit()
        
        # Aktivite oluştur (görev için)
        try:
            from app.routes.aktivite import create_activity_for_task
            create_activity_for_task(yeni_todo)
        except Exception as e:
            print(f"Aktivite oluşturma hatası (görev): {e}")
        
        # Log ekle
        try:
            log_user_action(
                action_type='Todo Oluşturuldu',
                table_name='Todos',
                record_id=yeni_todo.TodoID,
                old_data=None,
                new_data={'baslik': data['baslik'], 'oncelik': data.get('oncelik', 'Orta')},
                detail=f"Başlık: {data['baslik']}"
            )
        except Exception as log_error:
            print(f"Log hatası (önemli değil): {log_error}")
        
        return jsonify({'success': True, 'message': 'Todo başarıyla eklendi!'})
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()  # Detaylı hata log'u
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@gorev_bp.route('/todos/<int:todo_id>/guncelle', methods=['GET', 'POST'])
@login_required
def todo_guncelle(todo_id):
    """Todo güncelle"""
    try:
        todo = Todo.query.filter_by(TodoID=todo_id, KullaniciID=session['user_id']).first()
        if not todo:
            return jsonify({'success': False, 'message': 'Todo bulunamadı!'}), 404
        
        # GET isteği - todo verilerini döndür
        if request.method == 'GET':
            return jsonify({
                'success': True,
                'todo': {
                    'TodoID': todo.TodoID,
                    'Baslik': todo.Baslik,
                    'Aciklama': todo.Aciklama,
                    'Oncelik': todo.Oncelik,
                    'DurumID': todo.DurumID,
                    'Durum': todo.durum.DurumAdi if todo.durum else None,
                    'BitisTarihi': todo.BitisTarihi.strftime('%Y-%m-%d') if todo.BitisTarihi else None,
                    'HatirlatmaTarihi': todo.HatirlatmaTarihi.strftime('%Y-%m-%d') if todo.HatirlatmaTarihi else None,
                    'AtananKullaniciID': todo.AtananKullaniciID,
                    'RandevuDefteriID': todo.RandevuDefteriID,
                    'MusteriAdi': todo.MusteriAdi,
                    'MusteriSoyadi': todo.MusteriSoyadi,
                    'Telefon': todo.MusteriTelefon,
                    'Email': todo.MusteriEmail
                }
            })
        
        data = request.get_json()
        old_data = {
            'baslik': todo.Baslik,
            'aciklama': todo.Aciklama,
            'oncelik': todo.Oncelik,
            'durum': todo.durum.DurumAdi if todo.durum else None,
            'bitis_tarihi': todo.BitisTarihi.isoformat() if todo.BitisTarihi else None,
            'hatirlatma_tarihi': todo.HatirlatmaTarihi.isoformat() if todo.HatirlatmaTarihi else None,
            'musteri_adi': todo.MusteriAdi,
            'musteri_soyadi': todo.MusteriSoyadi,
            'musteri_telefon': todo.MusteriTelefon,
            'musteri_email': todo.MusteriEmail
        }
        
        # Durum ID'sini al - durum adından ID'ye çevir
        durum_id = None
        if data.get('durum'):
            try:
                # Önce sayı olarak deneyelim
                durum_id = int(data['durum'])
            except (ValueError, TypeError):
                # Sayı değilse, durum adından ID bulalım
                try:
                    firma_id = session.get('firma_id')
                    if firma_id:
                        durum_obj = TodoDurum.query.filter_by(
                            FirmaID=firma_id,
                            DurumAdi=data['durum']
                        ).first()
                        if durum_obj:
                            durum_id = durum_obj.DurumID
                except Exception as e:
                    pass
        
        # Güncelle
        todo.Baslik = data['baslik']
        todo.Aciklama = data.get('aciklama', '')
        todo.Oncelik = data.get('oncelik', 'Orta')
        todo.DurumID = durum_id  # Yeni durum sistemi
        
        # Atanan kullanıcıyı güncelle
        if data.get('AtananKullaniciID'):
            todo.AtananKullaniciID = data['AtananKullaniciID']
        
        # Randevu defteri ID'sini güncelle
        if data.get('randevu_defteri_id'):
            todo.RandevuDefteriID = data['randevu_defteri_id']
        
        # Müşteri bilgilerini güncelle
        todo.MusteriAdi = data.get('musteri_adi', '')
        todo.MusteriSoyadi = data.get('musteri_soyadi', '')
        todo.MusteriTelefon = data.get('musteri_telefon', '')
        todo.MusteriEmail = data.get('musteri_email', '')
        
        # Tarih formatlarını parse et
        if data.get('bitis_tarihi'):
            todo.BitisTarihi = datetime.strptime(data['bitis_tarihi'], '%Y-%m-%d')
        else:
            todo.BitisTarihi = None
            
        if data.get('hatirlatma_tarihi'):
            todo.HatirlatmaTarihi = datetime.strptime(data['hatirlatma_tarihi'], '%Y-%m-%d')
        else:
            todo.HatirlatmaTarihi = None
        
        # Eğer durum "Tamamlandı" ise tamamlanma tarihini set et
        if todo.durum and todo.durum.DurumAdi == 'Tamamlandı' and not todo.TamamlanmaTarihi:
            todo.TamamlanmaTarihi = datetime.now()
        elif not todo.durum or todo.durum.DurumAdi != 'Tamamlandı':
            todo.TamamlanmaTarihi = None
        
        db.session.commit()
        
        # Aktivite güncelle (görev için)
        try:
            from app.routes.aktivite import create_activity_for_task
            create_activity_for_task(todo)
        except Exception as e:
            print(f"Aktivite güncelleme hatası (görev): {e}")
        
        # Log ekle
        try:
            log_user_action(
                action_type='Todo Güncellendi',
                table_name='Todos',
                record_id=todo_id,
                old_data=old_data,
                new_data=data,
                detail=f"Başlık: {data['baslik']}"
            )
        except Exception as log_error:
            print(f"Log hatası (önemli değil): {log_error}")
        
        return jsonify({'success': True, 'message': 'Todo başarıyla güncellendi!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@gorev_bp.route('/todos/<int:todo_id>/delete', methods=['DELETE'])
@login_required
def todo_delete(todo_id):
    """Todo sil"""
    try:
        todo = Todo.query.filter_by(TodoID=todo_id, KullaniciID=session['user_id']).first()
        if not todo:
            return jsonify({'success': False, 'message': 'Todo bulunamadı!'}), 404
        
        baslik = todo.Baslik
        
        # Önce bağlantılı randevuyu sil (eğer varsa)
        if todo.RandevuID:
            randevu = Randevu.query.filter_by(RandevuID=todo.RandevuID).first()
            if randevu:
                # Önce RandevuYetki kayıtlarını sil
                RandevuYetki.query.filter_by(RandevuID=randevu.RandevuID).delete()
                
                # GorevID'yi NULL yap (circular reference'ı kır)
                randevu.GorevID = None
                db.session.flush()
                
                # Randevu'yu sil
                db.session.delete(randevu)
        
        # Todo'yu sil
        db.session.delete(todo)
        db.session.commit()
        
        # Log ekle
        try:
            log_user_action(
                action_type='Todo Silindi',
                table_name='Todos',
                record_id=todo_id,
                old_data={'baslik': baslik, 'tip': todo.Tip},
                new_data=None,
                detail=f"Başlık: {baslik}"
            )
        except Exception as log_error:
            print(f"Log hatası (önemli değil): {log_error}")
        
        return jsonify({'success': True, 'message': 'Todo ve bağlantılı randevu başarıyla silindi!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@gorev_bp.route('/todos/<int:todo_id>/durum', methods=['POST'])
@login_required
def todo_durum_degistir(todo_id):
    """Todo durumunu değiştir"""
    try:
        todo = Todo.query.filter_by(TodoID=todo_id, KullaniciID=session['user_id']).first()
        if not todo:
            return jsonify({'success': False, 'message': 'Todo bulunamadı!'}), 404
        
        data = request.get_json()
        yeni_durum_adi = data.get('durum')
        
        # Durum adından ID'yi bul
        yeni_durum_id = None
        if yeni_durum_adi:
            # Önce firmanın durumları içinde ara, yoksa genel kataloğa bak
            durum = TodoDurum.query.filter_by(
                DurumAdi=yeni_durum_adi,
                FirmaID=session.get('firma_id'),
                Aktif=True
            ).first()
            if not durum:
                durum = TodoDurum.query.filter_by(DurumAdi=yeni_durum_adi, Aktif=True).first()
            if not durum:
                return jsonify({'success': False, 'message': 'Geçersiz durum!'}), 400
            yeni_durum_id = durum.DurumID
        
        eski_durum = todo.durum.DurumAdi if todo.durum else 'Durum Yok'
        todo.DurumID = yeni_durum_id
        
        # Eğer durum "Tamamlandı" ise tamamlanma tarihini set et, KAYDI SİLME
        yeni_durum_adi = durum.DurumAdi if durum else None
        if yeni_durum_adi == 'Tamamlandı':
            if not todo.TamamlanmaTarihi:
                todo.TamamlanmaTarihi = datetime.now()
            
            # Bu todo ile ilgili bildirimleri sil
            Bildirim.query.filter(
                Bildirim.KullaniciID == todo.KullaniciID,
                Bildirim.Metin.contains(todo.Baslik),
                Bildirim.Tip == 'todo_reminder'
            ).delete(synchronize_session=False)
            
            # Kaydı silmeden değişiklikleri kaydet
            db.session.commit()
            
            # Aktivite güncelle (görev tamamlandı)
            try:
                from app.routes.aktivite import create_activity_for_task
                create_activity_for_task(todo)
            except Exception as e:
                print(f"Aktivite güncelleme hatası (görev tamamlandı): {e}")
        else:
            todo.TamamlanmaTarihi = None
            db.session.commit()
            
            # Aktivite güncelle (görev durumu değişti)
            try:
                from app.routes.aktivite import create_activity_for_task
                create_activity_for_task(todo)
            except Exception as e:
                print(f"Aktivite güncelleme hatası (görev durumu): {e}")
        
        # Log ekle
        if yeni_durum_adi == 'Tamamlandı':
            log_user_action(
                action_type='Todo Tamamlandı',
                table_name='Todos',
                record_id=todo_id,
                old_data={'durum': eski_durum},
                new_data={'durum': yeni_durum_adi, 'action': 'completed'},
                detail=f"Başlık: {todo.Baslik} - {eski_durum} → {yeni_durum_adi} (Silinmedi)"
            )
            return jsonify({'success': True, 'message': 'Görev tamamlandı olarak işaretlendi!'})
        else:
            log_user_action(
                action_type='Todo Durumu Değiştirildi',
                table_name='Todos',
                record_id=todo_id,
                old_data={'durum': eski_durum},
                new_data={'durum': yeni_durum_adi},
                detail=f"Başlık: {todo.Baslik} - {eski_durum} → {yeni_durum_adi}"
            )
            return jsonify({'success': True, 'message': f'Durum {yeni_durum_adi} olarak güncellendi!'})
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@gorev_bp.route('/api/gorev-raporlar')
@login_required
def api_gorev_raporlar():
    """Görev raporları API'si"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Kullanıcı bilgisi bulunamadı'}), 400
        
        # Filtre parametreleri
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        status_filter = request.args.get('status', 'all')
        user_filter = request.args.get('user', 'all')
        priority_filter = request.args.get('priority', 'all')
        type_filter = request.args.get('type', 'all')
        
        # Admin ise tüm görevleri, değilse sadece kendi görevlerini getir
        if session.get('is_admin', False):
            query = Todo.query
        else:
            query = Todo.query.filter_by(KullaniciID=user_id)
        
        # Tarih filtresi
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Son gün dahil
                query = query.filter(Todo.OlusturmaTarihi.between(start_dt, end_dt))
            except ValueError:
                pass
        
        # Durum filtresi
        if status_filter != 'all':
            query = query.filter(Todo.DurumID == status_filter)
        
        # Kullanıcı filtresi
        if user_filter != 'all':
            query = query.filter(Todo.KullaniciID == user_filter)
        
        # Öncelik filtresi
        if priority_filter != 'all':
            query = query.filter(Todo.Oncelik == priority_filter)
        
        # Tip filtresi
        if type_filter != 'all':
            query = query.filter(Todo.Tip == type_filter)
        
        gorevler = query.all()
        
        # İstatistikler
        total_tasks = len(gorevler)
        completed_tasks = len([g for g in gorevler if g.durum and g.durum.DurumAdi == 'Tamamlandı'])
        pending_tasks = len([g for g in gorevler if g.durum and g.durum.DurumAdi != 'Tamamlandı'])
        completion_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
        
        stats = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'pending_tasks': pending_tasks,
            'completion_rate': completion_rate
        }
        
        # Durum dağılımı (renkler TodoDurum.Renk değerlerinden)
        status_counts = {}
        status_colors_map = {}
        for gorev in gorevler:
            durum_adi = gorev.durum.DurumAdi if gorev.durum else 'Durum Yok'
            status_counts[durum_adi] = status_counts.get(durum_adi, 0) + 1
            if durum_adi not in status_colors_map:
                renk = (gorev.durum.Renk if gorev.durum and getattr(gorev.durum, 'Renk', None) else '#6c757d')
                status_colors_map[durum_adi] = renk
        # Listeleri aynı sırada üret
        status_labels = list(status_counts.keys())
        status_values = [status_counts[lbl] for lbl in status_labels]
        status_colors = [status_colors_map.get(lbl, '#6c757d') for lbl in status_labels]
        status_chart = {
            'labels': status_labels,
            'values': status_values,
            'colors': status_colors
        }
        
        # Öncelik dağılımı (sabit renkler)
        priority_counts = {}
        priority_colors_map = {
            'Yüksek': '#dc3545',    # Kırmızı
            'Orta': '#ffc107',      # Sarı
            'Düşük': '#28a745',     # Yeşil
            'Belirsiz': '#6c757d'   # Gri
        }
        for gorev in gorevler:
            priority = gorev.Oncelik or 'Belirsiz'
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        priority_labels = list(priority_counts.keys())
        priority_values = [priority_counts[lbl] for lbl in priority_labels]
        priority_colors = [priority_colors_map.get(lbl, '#6c757d') for lbl in priority_labels]
        
        priority_chart = {
            'labels': priority_labels,
            'values': priority_values,
            'colors': priority_colors
        }
        
        # Kullanıcı dağılımı
        user_counts = {}
        for gorev in gorevler:
            kullanici_adi = f"{gorev.kullanici.Ad} {gorev.kullanici.Soyad}" if gorev.kullanici else 'Bilinmeyen'
            user_counts[kullanici_adi] = user_counts.get(kullanici_adi, 0) + 1
        
        user_chart = {
            'labels': list(user_counts.keys()),
            'values': list(user_counts.values()),
            'colors': ['#007bff', '#28a745', '#ffc107', '#dc3545', '#6c757d', '#17a2b8', '#fd7e14', '#20c997']
        }
        
        # Kullanıcı tamamlanan görevler dağılımı
        user_completed_counts = {}
        for gorev in gorevler:
            if gorev.durum and gorev.durum.DurumAdi == 'Tamamlandı':
                kullanici_adi = f"{gorev.kullanici.Ad} {gorev.kullanici.Soyad}" if gorev.kullanici else 'Bilinmeyen'
                user_completed_counts[kullanici_adi] = user_completed_counts.get(kullanici_adi, 0) + 1
        
        user_completed_chart = {
            'labels': list(user_completed_counts.keys()),
            'values': list(user_completed_counts.values()),
            'colors': ['#28a745', '#007bff', '#ffc107', '#dc3545', '#6c757d', '#17a2b8', '#fd7e14', '#20c997']
        }
        
        # Aylık trend (son 12 ay)
        trend_data = {}
        for gorev in gorevler:
            month_key = gorev.OlusturmaTarihi.strftime('%Y-%m')
            if month_key not in trend_data:
                trend_data[month_key] = {'created': 0, 'completed': 0}
            trend_data[month_key]['created'] += 1
            
            if gorev.durum and gorev.durum.DurumAdi == 'Tamamlandı' and gorev.TamamlanmaTarihi:
                completed_month = gorev.TamamlanmaTarihi.strftime('%Y-%m')
                if completed_month not in trend_data:
                    trend_data[completed_month] = {'created': 0, 'completed': 0}
                trend_data[completed_month]['completed'] += 1
        
        # Son 12 ayı oluştur (doğru yıl-ay hesaplaması)
        trend_labels = []
        trend_created = []
        trend_completed = []
        
        current_date = datetime.now()
        for i in range(12):
            # Ay hesaplaması: mevcut aydan geriye git
            month_offset = i
            year = current_date.year
            month = current_date.month - month_offset
            
            # Ay 0 veya negatif olursa yılı azalt
            while month <= 0:
                month += 12
                year -= 1
            
            month_key = f"{year}-{month:02d}"
            
            # Ay adını Türkçe olarak oluştur
            month_names = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
            month_name = f"{month_names[month-1]} {year}"
            
            trend_labels.insert(0, month_name)
            trend_created.insert(0, trend_data.get(month_key, {}).get('created', 0))
            trend_completed.insert(0, trend_data.get(month_key, {}).get('completed', 0))
        
        trend_chart = {
            'labels': trend_labels,
            'created': trend_created,
            'completed': trend_completed
        }
        
        # Görev detayları
        tasks = []
        for gorev in gorevler:
            tasks.append({
                'baslik': gorev.Baslik,
                'durum': gorev.durum.DurumAdi if gorev.durum else 'Durum Yok',
                'durum_rengi': gorev.durum.Renk if gorev.durum and gorev.durum.Renk else '#6c757d',
                'oncelik': gorev.Oncelik or 'Belirsiz',
                'kullanici_adi': f"{gorev.kullanici.Ad} {gorev.kullanici.Soyad}" if gorev.kullanici else 'Bilinmeyen',
                'olusturma_tarihi': gorev.OlusturmaTarihi.isoformat() if gorev.OlusturmaTarihi else None,
                'bitis_tarihi': gorev.BitisTarihi.isoformat() if gorev.BitisTarihi else None,
                'musteri_adi': f"{gorev.MusteriAdi or ''} {gorev.MusteriSoyadi or ''}".strip() or None
            })
        
        return jsonify({
            'success': True,
            'stats': stats,
            'charts': {
                'status': status_chart,
                'priority': priority_chart,
                'user': user_chart,
                'user_completed': user_completed_chart,
                'trend': trend_chart
            },
            'tasks': tasks
        })
        
    except Exception as e:
        print(f"Görev raporları hatası: {e}")
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@gorev_bp.route('/api/gorev-bilgi/<int:gorev_id>', methods=['GET'])
@login_required
def gorev_bilgi(gorev_id):
    """Görev bilgilerini getir"""
    try:
        # Görevi bul
        gorev = Todo.query.filter_by(TodoID=gorev_id, KullaniciID=session['user_id'], Tip='Randevu').first()
        
        if not gorev:
            return jsonify({'success': False, 'message': 'Görev bulunamadı!'}), 404
        
        # Durum bilgisini güvenli şekilde al
        durum_adi = None
        try:
            durum_adi = gorev.durum.DurumAdi if gorev.durum else None
        except:
            pass
            
        data = {
            'TodoID': gorev.TodoID,
            'Baslik': gorev.Baslik,
            'Aciklama': gorev.Aciklama,
            'Oncelik': gorev.Oncelik,
            'Durum': durum_adi,
            'BitisTarihi': gorev.BitisTarihi.strftime('%Y-%m-%d') if gorev.BitisTarihi else None,
            'HatirlatmaTarihi': gorev.HatirlatmaTarihi.strftime('%Y-%m-%d') if gorev.HatirlatmaTarihi else None,
            'MusteriAdi': gorev.MusteriAdi,
            'MusteriSoyadi': gorev.MusteriSoyadi,
            'MusteriTelefon': gorev.MusteriTelefon,
            'MusteriEmail': gorev.MusteriEmail,
            'RandevuID': gorev.RandevuID
        }
        
        return jsonify({'success': True, 'gorev': data})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@gorev_bp.route('/api/gorev-to-randevu/<int:gorev_id>', methods=['POST'])
@login_required
def gorev_to_randevu(gorev_id):
    """Görevi randevu defterine taşı"""
    try:
        # Görevi bul
        gorev = Todo.query.filter_by(TodoID=gorev_id, KullaniciID=session['user_id'], Tip='Randevu').first()
        if not gorev:
            return jsonify({'success': False, 'message': 'Görev bulunamadı!'}), 404
        
        # Görev tipini 'Randevu' olarak değiştir (zaten Randevu ama emin olmak için)
        gorev.Tip = 'Randevu'
        
        # Randevu defteri için gerekli alanları ekle/güncelle
        if not gorev.RandevuTarihi:
            gorev.RandevuTarihi = gorev.BitisTarihi or datetime.now().date()
        
        if not gorev.RandevuSaati:
            gorev.RandevuSaati = '09:00'  # Varsayılan saat
        
        # Durumu 'Beklemede' yap
        beklemede_durum = TodoDurum.query.filter_by(DurumAdi='Beklemede', FirmaID=session['firma_id']).first()
        if beklemede_durum:
            gorev.DurumID = beklemede_durum.DurumID
        
        db.session.commit()
        
        # Log ekle
        try:
            log_user_action(
                action_type='Görev Randevu Defterine Taşındı',
                table_name='Todos',
                record_id=gorev_id,
                old_data={'tip': 'Randevu'},
                new_data={'tip': 'Randevu', 'randevu_tarihi': str(gorev.RandevuTarihi), 'randevu_saati': gorev.RandevuSaati},
                detail=f"Başlık: {gorev.Baslik} - Randevu Tarihi: {gorev.RandevuTarihi}"
            )
        except Exception as log_error:
            print(f"Log hatası (önemli değil): {log_error}")
        
        return jsonify({'success': True, 'message': 'Görev başarıyla randevu defterine taşındı!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@gorev_bp.route('/todos/<int:todo_id>/sil', methods=['DELETE'])
@login_required
def todo_sil(todo_id):
    """Todo sil"""
    try:
        todo = Todo.query.filter_by(TodoID=todo_id, KullaniciID=session['user_id']).first()
        if not todo:
            return jsonify({'success': False, 'message': 'Todo bulunamadı!'}), 404
        
        baslik = todo.Baslik
        
        # Önce bağlantılı randevuyu sil (eğer varsa)
        if todo.RandevuID:
            randevu = Randevu.query.filter_by(RandevuID=todo.RandevuID).first()
            if randevu:
                # Önce RandevuYetki kayıtlarını sil
                RandevuYetki.query.filter_by(RandevuID=randevu.RandevuID).delete()
                
                # GorevID'yi NULL yap (circular reference'ı kır)
                randevu.GorevID = None
                db.session.flush()
                
                # Randevu'yu sil
                db.session.delete(randevu)
        
        # Todo'yu sil
        db.session.delete(todo)
        db.session.commit()
        
        # Log ekle
        try:
            log_user_action(
                action_type='Todo Silindi',
                table_name='Todos',
                record_id=todo_id,
                old_data={'baslik': baslik, 'durum': todo.durum.DurumAdi if todo.durum else 'Durum Yok'},
                new_data=None,
                detail=f"Başlık: {baslik}"
            )
        except Exception as log_error:
            print(f"Log hatası (önemli değil): {log_error}")
        
        return jsonify({'success': True, 'message': 'Todo ve bağlantılı randevu başarıyla silindi!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@gorev_bp.route('/todos/api')
@login_required
def todos_api():
    """Todo verilerini API olarak döndür (dashboard için)"""
    try:
        # Kullanıcının todolarını getir
        todos = Todo.query.filter_by(KullaniciID=session['user_id']).all()
        
        result = []
        for todo in todos:
            result.append({
                'id': todo.TodoID,
                'baslik': todo.Baslik,
                'aciklama': todo.Aciklama,
                'oncelik': todo.Oncelik,
                'durum': todo.durum.DurumAdi if todo.durum else 'Durum Yok',
                'bitis_tarihi': todo.BitisTarihi.isoformat() if todo.BitisTarihi else None,
                'hatirlatma_tarihi': todo.HatirlatmaTarihi.isoformat() if todo.HatirlatmaTarihi else None,
                'olusturma_tarihi': todo.OlusturmaTarihi.isoformat(),
                'tamamlanma_tarihi': todo.TamamlanmaTarihi.isoformat() if todo.TamamlanmaTarihi else None
            })
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500

@gorev_bp.route('/api/gorev-durumlar')
@login_required
def api_gorev_durumlar():
    """Görev durumlarını listele"""
    durumlar = TodoDurum.query.filter_by(FirmaID=session['firma_id'], Aktif=True).order_by(TodoDurum.Sira).all()
    return jsonify({'success': True, 'durumlar': [{
        'DurumID': d.DurumID,
        'DurumAdi': d.DurumAdi,
        'Renk': d.Renk
    } for d in durumlar]})
