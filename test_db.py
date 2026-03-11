from app import create_app, db
from app.models import Todo
from datetime import datetime, date

app = create_app()

with app.app_context():
    bugun = date.today()
    print(f'Bugün: {bugun}')
    
    # Tüm hatırlatmaları gör
    todos = Todo.query.filter(Todo.HatirlatmaTarihi != None).all()
    print(f'Toplam hatırlatma olan todo: {len(todos)}')
    
    for todo in todos:
        hatirlatma_tarihi = todo.HatirlatmaTarihi.date() if todo.HatirlatmaTarihi else None
        bugune_esit = hatirlatma_tarihi == bugun if hatirlatma_tarihi else False
        print(f'{todo.Baslik} - Hatırlatma: {hatirlatma_tarihi} - Bugüne eşit mi: {bugune_esit}')
        
    # Bugüne ait hatırlatmaları sorgula (kodumuzdaki mantıkla)
    from sqlalchemy import cast, Date
    bugun_hatirlatmalar = Todo.query.filter(
        cast(Todo.HatirlatmaTarihi, Date) == bugun
    ).all()
    print(f'\nBugüne ait hatırlatmalar (CAST ile): {len(bugun_hatirlatmalar)}')
    
    for todo in bugun_hatirlatmalar:
        print(f'{todo.Baslik} - Hatırlatma: {todo.HatirlatmaTarihi}')