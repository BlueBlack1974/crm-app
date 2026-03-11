"""
WhatsApp mesajlarını kontrol etme scripti
"""
# app.py'yi modül olarak import et
import app as app_module

# Flask app oluştur
app = app_module.create_app()

with app.app_context():
    # Modelleri app_module'den al
    WhatsAppMesaj = app_module.WhatsAppMesaj
    Musteri = app_module.Musteri
    Firma = app_module.Firma
    db = app_module.db
    
    print("=" * 60)
    print("WhatsApp Mesajları Kontrolü")
    print("=" * 60)
    
    # Firma kontrolü
    firma = Firma.query.first()
    if not firma:
        print("HATA: Firma bulunamadı!")
        exit(1)
    
    print(f"Firma: {firma.FirmaAdi} (ID: {firma.FirmaID})")
    print()
    
    # Toplam mesaj sayısı
    toplam_mesaj = WhatsAppMesaj.query.filter_by(FirmaID=firma.FirmaID).count()
    print(f"Toplam WhatsApp mesaj sayısı: {toplam_mesaj}")
    print()
    
    if toplam_mesaj == 0:
        print("⚠️ Veritabanında WhatsApp mesajı yok.")
        print("Bu normal olabilir çünkü:")
        print("1. WhatsApp webhook henüz kurulmamış olabilir")
        print("2. Henüz mesaj gönderilmemiş/alınmamış olabilir")
        print("3. Mesajlar henüz veritabanına kaydedilmemiş olabilir")
    else:
        print(f"✅ {toplam_mesaj} mesaj bulundu:")
        print()
        
        # İlk 10 mesajı göster
        mesajlar = WhatsAppMesaj.query.filter_by(FirmaID=firma.FirmaID).order_by(WhatsAppMesaj.Tarih.desc()).limit(10).all()
        
        for i, mesaj in enumerate(mesajlar, 1):
            print(f"{i}. Mesaj ID: {mesaj.MesajID}")
            print(f"   Musteri ID: {mesaj.MusteriID}")
            print(f"   Yön: {mesaj.Yyon}")
            print(f"   Gönderen: {mesaj.GonderenTelefon}")
            print(f"   Alıcı: {mesaj.AliciTelefon}")
            print(f"   Mesaj: {mesaj.MesajMetni[:50] if mesaj.MesajMetni else 'N/A'}...")
            print(f"   Tarih: {mesaj.Tarih}")
            print()
    
    # Müşteri kontrolü
    print("=" * 60)
    print("Müşteri Kontrolü")
    print("=" * 60)
    
    musteriler = Musteri.query.filter_by(FirmaID=firma.FirmaID).limit(5).all()
    print(f"İlk 5 müşteri:")
    for musteri in musteriler:
        mesaj_sayisi = WhatsAppMesaj.query.filter_by(
            FirmaID=firma.FirmaID,
            MusteriID=musteri.MusteriID
        ).count()
        print(f"  - {musteri.Ad} {musteri.Soyad} (ID: {musteri.MusteriID})")
        print(f"    Telefon: {musteri.Telefon}")
        print(f"    Mesaj sayısı: {mesaj_sayisi}")
        print()
    
    print("=" * 60)
