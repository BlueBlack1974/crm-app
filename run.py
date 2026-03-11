import os
import sys

# app.py modülünü import et (app package değil)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# app.py'den initialize_app fonksiyonunu import et
import importlib.util
spec = importlib.util.spec_from_file_location("main_app", "app.py")
main_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_app)

if __name__ == '__main__':
    # initialize_app fonksiyonunu çağır
    app = main_app.initialize_app()
    
    # Development modunda debug=True
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.environ.get('FLASK_PORT', 5000)))

