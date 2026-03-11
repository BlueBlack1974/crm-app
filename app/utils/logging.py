import queue
import json
import threading
from flask import request, session
from functools import wraps
from app.extensions import db
from app.models import KullaniciLog, Randevu, Musteri, Kullanici
from app.utils.helpers import get_client_ip

# Log kuyruğu
log_queue = queue.Queue()

def background_logger(app):
    """Arka planda log kayıtlarını veritabanına yazan thread"""
    with app.app_context():
        while True:
            try:
                log_data = log_queue.get(timeout=1)
                if log_data is None:  # Shutdown signal
                    break
                db.session.add(log_data)
                db.session.commit()
            except queue.Empty:
                # Timeout - bu normal, devam et
                continue
            except Exception as e:
                print(f"Log yazma hatası: {e}")
                try:
                    db.session.rollback()
                except:
                    pass

def start_logger(app):
    """Loglama sistemini başlat"""
    log_thread = threading.Thread(target=background_logger, args=(app,), daemon=True)
    log_thread.start()


def log_user_action(action_type, table_name, record_id=None, old_data=None, new_data=None, detail=None):
    """Kullanıcı işlemini asenkron olarak logla"""
    try:
        if 'user_id' not in session:
            return
    except RuntimeError:
        # Session context yoksa (test ortamı gibi) loglama yapma
        return
    
    log_data = KullaniciLog(
        KullaniciID=session['user_id'],
        IslemTipi=action_type,
        TabloAdi=table_name,
        KayitID=record_id,
        EskiVeri=json.dumps(old_data, ensure_ascii=False) if old_data else None,
        YeniVeri=json.dumps(new_data, ensure_ascii=False) if new_data else None,
        IslemDetayi=detail,
        IPAdresi=get_client_ip(),
        UserAgent=request.headers.get('User-Agent', '')
    )
    log_queue.put(log_data)

def log_user_action_decorator(action_type, table_name, record_id_param=None, detail_func=None):
    """Loglama decorator'ı"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            
            # Record ID'yi al
            record_id = None
            if record_id_param and record_id_param in kwargs:
                record_id = kwargs[record_id_param]
            
            # Detay fonksiyonu varsa çalıştır
            detail = None
            if detail_func:
                try:
                    detail = detail_func(result, *args, **kwargs)
                except:
                    pass
            
            # Logla
            log_user_action(action_type, table_name, record_id, detail=detail)
            
            return result
        return decorated_function
    return decorator

def get_record_info(log):
    """Log için record bilgisini hazırla"""
    try:
        if not log.KayitID:
            return None
            
        if log.TabloAdi == 'Randevu':
            randevu = Randevu.query.filter_by(RandevuID=log.KayitID, FirmaID=log.kullanici.FirmaID).first()
            if randevu:
                tarih_str = randevu.RandevuTarihi.strftime('%d.%m.%Y %H:%M')
                musteri_adi = f"{randevu.MusteriAdi or ''} {randevu.MusteriSoyadi or ''}".strip()
                if musteri_adi:
                    return f"{tarih_str} - {musteri_adi} ({randevu.RandevuBaslik})"
                else:
                    return f"{tarih_str} - {randevu.RandevuBaslik}"
            else:
                return f"ID: {log.KayitID}"
                
        elif log.TabloAdi == 'Musteri':
            musteri = Musteri.query.filter_by(MusteriID=log.KayitID, FirmaID=log.kullanici.FirmaID).first()
            if musteri:
                musteri_adi = f"{musteri.Ad or ''} {musteri.Soyad or ''}".strip()
                if musteri_adi and musteri.Telefon:
                    return f"{musteri_adi} ({musteri.Telefon})"
                elif musteri_adi:
                    return musteri_adi
                elif musteri.Telefon:
                    return musteri.Telefon
                else:
                    return f"ID: {log.KayitID}"
            else:
                return f"ID: {log.KayitID}"
                
        elif log.TabloAdi == 'Kullanici':
            kullanici = Kullanici.query.filter_by(KullaniciID=log.KayitID, FirmaID=log.kullanici.FirmaID).first()
            if kullanici:
                kullanici_adi = f"{kullanici.Ad or ''} {kullanici.Soyad or ''}".strip()
                if kullanici_adi:
                    return f"{kullanici_adi} ({kullanici.KullaniciAdi})"
                else:
                    return kullanici.KullaniciAdi
            else:
                return f"ID: {log.KayitID}"
                
        elif log.TabloAdi == 'Sistem':
            # Sistem logları için detay bilgisini kullan
            if log.IslemDetayi:
                return log.IslemDetayi[:50] + "..." if len(log.IslemDetayi) > 50 else log.IslemDetayi
            else:
                return "Sistem İşlemi"
                
        else:
            # Diğer tablolar için sadece ID göster
            return f"ID: {log.KayitID}"
            
    except Exception:
        # Hata durumunda sadece ID göster
        return f"ID: {log.KayitID}" if log.KayitID else None
