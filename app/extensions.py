from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect

# Eklentileri initialize et (henüz app'e bağlama)
db = SQLAlchemy()
babel = Babel()
csrf = CSRFProtect()
