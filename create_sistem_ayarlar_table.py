"""
SistemAyarlar tablosunu oluştur
"""
from app import app, db, SistemAyar

try:
    with app.app_context():
        # Tabloyu oluştur
        db.create_all()
        
        # SistemAyarlar tablosunun var olup olmadığını kontrol et
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'SistemAyarlar' not in inspector.get_table_names():
            print("SistemAyarlar tablosu bulunamadı, oluşturuluyor...")
            SistemAyar.__table__.create(db.engine)
            print("SistemAyarlar tablosu oluşturuldu!")
        else:
            print("SistemAyarlar tablosu zaten mevcut.")
        
        # Varsayılan ayarları kontrol et
        db_type = SistemAyar.query.filter_by(AyarAdi='database_type').first()
        if not db_type:
            print("Varsayılan veritabanı ayarı yok, oluşturuluyor...")
            default_setting = SistemAyar(
                AyarAdi='database_type',
                AyarDegeri='mssql',
                Aciklama='Veritabanı tipi (mssql veya mysql)'
            )
            db.session.add(default_setting)
            db.session.commit()
            print("Varsayılan ayar oluşturuldu!")
        else:
            print(f"Mevcut veritabanı tipi: {db_type.AyarDegeri}")
            
except Exception as e:
    print(f"Hata: {e}")
    import traceback
    traceback.print_exc()



