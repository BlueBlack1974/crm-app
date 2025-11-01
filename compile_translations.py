#!/usr/bin/env python3
"""
Çeviri dosyalarını derle (.po -> .mo)
"""

import os
import subprocess
import sys

def compile_translations():
    translations_dir = 'translations'
    languages = ['tr', 'en', 'fr', 'de']
    
    for lang in languages:
        po_file = os.path.join(translations_dir, lang, 'LC_MESSAGES', 'messages.po')
        mo_file = os.path.join(translations_dir, lang, 'LC_MESSAGES', 'messages.mo')
        
        if not os.path.exists(po_file):
            print(f"[WARN] {po_file} bulunamadi, atlaniyor...")
            continue
        
        print(f"[INFO] {lang} dil dosyasi derleniyor...")
        
        try:
            # Flask-Babel kullanarak derle
            from flask_babel import Babel
            from babel.messages.frontend import compile_catalog
            
            # Babel compile komutunu çalıştır
            result = subprocess.run(
                [sys.executable, '-m', 'babel.messages.frontend', 'compile',
                 '-d', translations_dir, '-l', lang],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"[OK] {lang} basariyla derlendi!")
            else:
                print(f"[WARN] {lang} derleme hatasi:")
                print(result.stderr)
                # Alternatif: msgfmt kullan
                try:
                    import msgfmt
                    msgfmt.make(po_file, mo_file)
                    print(f"[OK] {lang} msgfmt ile basariyla derlendi!")
                except ImportError:
                    print(f"[ERROR] {lang} derlenemedi (babel ve msgfmt bulunamadi)")
                    print("        Uygulama calistiginda otomatik olarak derlenecek.")
        except Exception as e:
            print(f"[WARN] {lang} derleme hatasi: {e}")
            print("        Uygulama calistiginda otomatik olarak derlenecek.")
    
    print("\n[INFO] Derleme tamamlandi!")
    print("[NOTE] Eger derleme hatasi varsa, uygulama calistiginda otomatik olarak derlenecektir.")

if __name__ == '__main__':
    compile_translations()

