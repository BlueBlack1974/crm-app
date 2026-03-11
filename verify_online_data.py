from app import create_app
from app.extensions import db
from app.models import Kullanici, AktifOturum
from datetime import datetime

app = create_app()

with app.app_context():
    print(f"Server Time: {datetime.now()}")
    
    users = Kullanici.query.filter_by(Aktif=True).all()
    
    for u in users:
        print(f"\nUser: {u.KullaniciAdi} (ID: {u.KullaniciID})")
        # u.aktif_oturum is a relationship, accessing it triggers the query
        sessions = u.aktif_oturum 
        
        # It should be iterable if uselist=True (default for 1-to-many)
        try:
            iter(sessions)
        except TypeError:
            sessions = [sessions] if sessions else []
            
        if not sessions:
            print("  No active sessions.")
            continue
            
        is_online = False
        for s in sessions:
            if not s: continue
            try:
                # Handle possible None for SonGorulmeZamani
                if not s.SonGorulmeZamani:
                    print(f"  Session {s.ID}: Last Seen is None")
                    continue
                    
                diff = (datetime.now() - s.SonGorulmeZamani).total_seconds()
                status = "ONLINE" if diff < 300 else "OFFLINE"
                if diff < 300: is_online = True
                
                print(f"  Session {s.ID}: Last Seen: {s.SonGorulmeZamani} (Diff: {diff:.1f}s) -> {status}")
            except Exception as e:
                print(f"  Error reading session {s.ID}: {e}")
            
        print(f"  Overall Status: {'ONLINE' if is_online else 'OFFLINE'}")
