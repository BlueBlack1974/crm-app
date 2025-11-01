#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basit Flask Sunucusu - Python 3.13 Uyumlu
"""

import os
import sys

# Python 3.13 timezone fix
os.environ.setdefault('PYTHONTZPATH', '')

try:
    from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
    from flask_sqlalchemy import SQLAlchemy
    from werkzeug.security import generate_password_hash, check_password_hash
    from datetime import datetime, timedelta
    import secrets
    from dotenv import load_dotenv
    from functools import wraps
    
    print("[OK] Tum kutuphaneler basariyla yuklendi!")
    
    # Flask uygulaması oluştur
    app = Flask(__name__)
    
    # Basit test sayfası
    @app.route('/')
    def index():
        return """
        <html>
        <head><title>CRM Test</title></head>
        <body>
            <h1>[OK] Flask Calisiyor!</h1>
            <p>Python 3.13 ile Flask başarıyla çalıştı!</p>
            <p>Şimdi ana uygulamayı çalıştırabilirsiniz.</p>
        </body>
        </html>
        """
    
    if __name__ == '__main__':
        print("[START] Basit Flask sunucusu baslatiliyor...")
        app.run(debug=True, host='127.0.0.1', port=5000)
        
except ImportError as e:
    print(f"[HATA] Kutuphane hatasi: {e}")
    print("[COZUM] pip install flask flask-sqlalchemy werkzeug python-dotenv")
except Exception as e:
    print(f"[HATA] Genel hata: {e}")
    print("[ONERI] Python 3.11 veya 3.12 kullanmayi deneyin")

