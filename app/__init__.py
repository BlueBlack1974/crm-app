from flask import Flask, session, request
from config import config
from app.extensions import db, babel, csrf

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Konfigürasyonu yükle
    app.config.from_object(config[config_name])
    
    # Locale selector fonksiyonu
    def get_locale():
        # Session varsa ve language set edilmişse onu kullan
        if session and session.get('language'):
            lang = session.get('language')
            return lang
        # Yoksa varsayılan dili kullan
        return app.config.get('BABEL_DEFAULT_LOCALE', 'tr')
    
    # Eklentileri başlat
    db.init_app(app)
    csrf.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    
    # Blueprint'leri kaydet
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.settings import settings_bp
    from app.routes.api import api_bp
    from app.routes.randevu import randevu_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(randevu_bp)
    
    from app.routes.gorev import gorev_bp
    app.register_blueprint(gorev_bp)
    
    from app.routes.musteri import musteri_bp
    app.register_blueprint(musteri_bp)
    
    from app.routes.rapor import rapor_bp
    app.register_blueprint(rapor_bp)
    
    from app.routes.aktivite import aktivite_bp
    app.register_blueprint(aktivite_bp)
    
    from app.routes.instagram import instagram_bp
    app.register_blueprint(instagram_bp)
    
    from app.routes.kullanici_mesaj import kullanici_mesaj_bp
    app.register_blueprint(kullanici_mesaj_bp)
    
    # Loglama sistemini başlat
    from app.utils.logging import start_logger
    start_logger(app)
    
    # Context processor - çeviri fonksiyonunu template'lere ekle
    @app.context_processor
    def inject_translations():
        from flask_babel import gettext
        return {'_': gettext}
    
    return app
