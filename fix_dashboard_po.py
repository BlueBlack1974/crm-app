# -*- coding: utf-8 -*-
import os

translations = {
    'tr': {
        'Total Appointments': 'Toplam Randevu',
        'This Week': 'Bu Hafta',
        'Pending': 'Beklemede',
        'Confirmed': 'Onaylanan',
        'My Todos': 'Yapılacaklarım',
        'Todo Statistics': 'Yapılacaklar İstatistikleri',
        'My Tasks': 'Görevlerim',
        'View All': 'Tümünü Gör',
        'Mark as Completed': 'Tamamlandı İşaretle',
        'Edit': 'Düzenle',
        'Delete': 'Sil',
        'DELETE': 'SİL',
        'Total': 'Toplam',
        'Completed': 'Tamamlanan',
        'In Progress': 'Devam Eden',
        'Henüz Yok': 'Henüz Yok',
        'Oluştur': 'Oluştur'
    },
    'en': {
        'Total Appointments': 'Total Appointments',
        'This Week': 'This Week',
        'Pending': 'Pending',
        'Confirmed': 'Confirmed',
        'My Todos': 'My Todos',
        'Todo Statistics': 'Todo Statistics',
        'My Tasks': 'My Tasks',
        'View All': 'View All',
        'Mark as Completed': 'Mark as Completed',
        'Edit': 'Edit',
        'Delete': 'Delete',
        'DELETE': 'DELETE',
        'Total': 'Total',
        'Completed': 'Completed',
        'In Progress': 'In Progress',
        'Henüz Yok': 'None Yet',
        'Oluştur': 'Create'
    },
    'de': {
        'Total Appointments': 'Termine Gesamt',
        'This Week': 'Diese Woche',
        'Pending': 'Ausstehend',
        'Confirmed': 'Bestätigt',
        'My Todos': 'Meine Todos',
        'Todo Statistics': 'Todo Statistiken',
        'My Tasks': 'Meine Aufgaben',
        'View All': 'Alle anzeigen',
        'Mark as Completed': 'Als erledigt markieren',
        'Edit': 'Bearbeiten',
        'Delete': 'Löschen',
        'DELETE': 'LÖSCHEN',
        'Total': 'Gesamt',
        'Completed': 'Abgeschlossen',
        'In Progress': 'In Bearbeitung',
        'Henüz Yok': 'Noch keine',
        'Oluştur': 'Erstellen'
    },
    'fr': {
        'Total Appointments': 'Rendez-vous totaux',
        'This Week': 'Cette semaine',
        'Pending': 'En attente',
        'Confirmed': 'Confirmé',
        'My Todos': 'Mes Todos',
        'Todo Statistics': 'Statistiques Todo',
        'My Tasks': 'Mes Tâches',
        'View All': 'Voir tout',
        'Mark as Completed': 'Marquer comme terminé',
        'Edit': 'Modifier',
        'Delete': 'Supprimer',
        'DELETE': 'SUPPRIMER',
        'Total': 'Total',
        'Completed': 'Terminé',
        'In Progress': 'En cours',
        'Henüz Yok': 'Aucun pour le moment',
        'Oluştur': 'Créer'
    }
}

keys = [
    'Total Appointments', 'This Week', 'Pending', 'Confirmed',
    'My Todos', 'Todo Statistics', 'My Tasks', 'View All',
    'Mark as Completed', 'Edit', 'Delete', 'DELETE', 'Total',
    'Completed', 'In Progress', 'Henüz Yok', 'Oluştur'
]

for lang in translations.keys():
    filepath = os.path.join('translations', lang, 'LC_MESSAGES', 'messages.po')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        out_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check for commented obsolete msgid
            if line.startswith('#~ msgid '):
                msgid = line[9:].strip().strip('"')
                if msgid in keys:
                    out_lines.append('msgid "{}"\n'.format(msgid))
                    i += 1
                    while i < len(lines) and lines[i].startswith('#~ msgstr '):
                        i += 1
                    
                    msgstr = translations[lang][msgid]
                    out_lines.append('msgstr "{}"\n\n'.format(msgstr))
                    continue
            
            # Check for uncommented msgid that might have wrong translation
            if line.startswith('msgid '):
                msgid = line[6:].strip().strip('"')
                if msgid in keys:
                    out_lines.append(line)
                    i += 1
                    while i < len(lines) and lines[i].startswith('msgstr '):
                        i += 1
                    msgstr = translations[lang][msgid]
                    out_lines.append('msgstr "{}"\n\n'.format(msgstr))
                    continue

            out_lines.append(line)
            i += 1
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(out_lines)
