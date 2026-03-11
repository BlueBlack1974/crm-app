from datetime import datetime, timedelta
import time
from app.extensions import db
from app.models import Todo, Bildirim, RandevuHatirlatma, Randevu, RandevuSMSHatirlatma, FirmaSMSAyar
from app.utils.email import send_email_with_firma_settings, send_email_simple
from app.utils.sms import send_sms_with_firma_settings

def check_todo_reminders():
    """Todo hatırlatmalarını kontrol et ve bildirim oluştur"""
    try:
        bugun = datetime.now().date()
        simdi = datetime.now()
        
        # Bugün hatırlatma tarihi olan todoları bul (DateTime'ı Date'e cast et)
        hatirlatma_todos = Todo.query.filter(
            db.func.cast(Todo.HatirlatmaTarihi, db.Date) == bugun
        ).all()
        
        # Tamamlanmamış todoları filtrele
        hatirlatma_todos = [todo for todo in hatirlatma_todos if not todo.durum or todo.durum.DurumAdi != 'Tamamlandı']
        
        yeni_bildirim_sayisi = 0
        
        for todo in hatirlatma_todos:
            # Bu todo için bugün zaten bildirim oluşturulmuş mu kontrol et
            existing_notification = Bildirim.query.filter(
                Bildirim.KullaniciID == todo.KullaniciID,
                Bildirim.Metin.contains(todo.Baslik),
                Bildirim.Tip == 'todo_reminder',
                Bildirim.OlusturmaTarihi >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            ).first()
            
            if not existing_notification:
                # Yeni bildirim oluştur
                bildirim = Bildirim(
                    KullaniciID=todo.KullaniciID,
                    FirmaID=1,  # Varsayılan firma ID
                    Metin=f'[HATIRLATMA] "{todo.Baslik}" gorevinin hatirlatma tarihi bugun!',
                    Tip='todo_reminder',
                    Okundu=False
                )
                db.session.add(bildirim)
                yeni_bildirim_sayisi += 1
                print(f"Todo hatırlatma bildirimi oluşturuldu: {todo.Baslik} (Kullanıcı: {todo.KullaniciID})")
        
        db.session.commit()
        
        if yeni_bildirim_sayisi > 0:
            print(f"Todo hatırlatma kontrolü tamamlandı. {yeni_bildirim_sayisi} yeni bildirim oluşturuldu.")
        else:
            print(f"Todo hatırlatma kontrolü tamamlandı. {len(hatirlatma_todos)} todo kontrol edildi, yeni bildirim yok.")
        
    except Exception as e:
        print(f"Todo hatırlatma kontrolünde hata: {str(e)}")
        db.session.rollback()

def todo_reminder_worker(app):
    """Todo hatırlatma worker'ı - her 5 dakikada bir çalışır"""
    with app.app_context():
        while True:
            try:
                now = datetime.now()
                # Her 5 dakikada bir kontrol et
                check_todo_reminders()
                
                # 5 dakika bekle
                time.sleep(300)
                
            except Exception as e:
                print(f"Todo reminder worker hatası: {str(e)}")
                time.sleep(300)

# Dakikada bir calisan basit hatirlatma is parcacigi
def reminder_worker(app):
    with app.app_context():
        while True:
            try:
                now = datetime.now()
                
                # Sadece gelecekteki randevular için hatırlatma kontrol et (24 saat içinde)
                future_limit = now + timedelta(hours=24)
                
                # Gonderilmemis ve epostasi olan hatirlatmalari getir
                # Sadece gelecekteki randevular için kontrol et
                pending = db.session.query(RandevuHatirlatma).join(Randevu).filter(
                    RandevuHatirlatma.Gonderildi == False,
                    RandevuHatirlatma.RecipientEmail != None,
                    RandevuHatirlatma.RecipientEmail != '',
                    Randevu.RandevuTarihi >= now,  # Gelecekteki randevular
                    Randevu.RandevuTarihi <= future_limit  # 24 saat içindeki randevular
                ).all()

                # SMS hatirlatmalarini da kontrol et
                pending_sms = db.session.query(RandevuSMSHatirlatma).join(Randevu).filter(
                    RandevuSMSHatirlatma.Gonderildi == False,
                    RandevuSMSHatirlatma.RecipientPhone != None,
                    RandevuSMSHatirlatma.RecipientPhone != '',
                    Randevu.RandevuTarihi >= now,
                    Randevu.RandevuTarihi <= future_limit
                ).all()

                # Eğer gönderilecek hiçbir hatırlatma yoksa, bekle
                if not pending and not pending_sms:
                    time.sleep(60)
                    continue

                for h in pending:
                    r = h.randevu
                    if not r:
                        continue
                    # Ne zaman gonderilmeli?
                    target_send_time = r.RandevuTarihi - timedelta(minutes=h.MinutesBefore)
                    # UTC varsayimi: RandevuTarihi zaten naive ise karşılaştırma naive-naive
                    if target_send_time <= now and not h.Gonderildi:
                        subject = f"Randevu Hatırlatma - {r.RandevuTarihi.strftime('%d.%m.%Y %H:%M')}"
                        body = (
                            f"Merhaba,\n\n"
                            f"{r.RandevuTarihi.strftime('%d.%m.%Y %H:%M')} tarihinde bir randevunuz bulunmaktadır.\n"
                            f"Referans: {r.RandevuBaslik}\n"
                            f"Süre: {r.RandevuSuresi or 60} dk\n\n"
                            f"Bu bir otomatik bilgilendirmedir."
                        )
                        # Önce firma ayarlarını kullan, yoksa genel ayarları kullan
                        ok = send_email_with_firma_settings(r.FirmaID, h.RecipientEmail, subject, body)
                        if not ok:
                            # Firma ayarları başarısız olursa genel ayarları dene
                            ok = send_email_simple(h.RecipientEmail, subject, body)
                        if ok:
                            h.Gonderildi = True
                            h.GonderimTarihi = datetime.now()
                            db.session.commit()

                # SMS hatirlatmalarini isleme
                for s in pending_sms:
                    r = s.randevu
                    if not r:
                        continue
                    target_send_time = r.RandevuTarihi - timedelta(minutes=s.MinutesBefore)
                    if target_send_time <= now and not s.Gonderildi:
                        # Firma SMS ayar metnini kullan
                        sms_ayar = FirmaSMSAyar.query.filter_by(FirmaID=s.FirmaID, Aktif=True).first()
                        sms_text = (sms_ayar.VarsayilanSMSMetni if sms_ayar and sms_ayar.VarsayilanSMSMetni else
                                    "Merhaba {MUSTERI_ADI}, {RANDEVU_TARIH} tarihindeki randevunuzu hatırlatırız.")
                        try:
                            defter_adi = r.defter.DefterAdi if r.defter else ''
                        except Exception:
                            defter_adi = ''
                        # Ad + Soyad birlestir
                        try:
                            if r.musteri and r.musteri.MusteriSoyadi:
                                full_name = f"{r.musteri.MusteriAdi} {r.musteri.MusteriSoyadi}".strip()
                            else:
                                full_name = (r.MusteriAdi or '').strip()
                        except Exception:
                            full_name = (r.MusteriAdi or '').strip()

                        sms_text = sms_text.replace('{MUSTERI_ADI}', full_name or '-')\
                                           .replace('{RANDEVU_TARIH}', r.RandevuTarihi.strftime('%d.%m.%Y %H:%M'))\
                                           .replace('{DEFTER_ADI}', defter_adi)

                        ok = send_sms_with_firma_settings(s.FirmaID, s.RecipientPhone, sms_text)
                        if ok:
                            s.Gonderildi = True
                            s.GonderimTarihi = datetime.now()
                            db.session.commit()
            except Exception as e:
                print(f"Hatirlatma isci hatasi: {e}")
            finally:
                # 60 saniye bekle
                time.sleep(60)
