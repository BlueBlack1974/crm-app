# -*- coding: utf-8 -*-
import os

translations = {
    'tr': {
        'Recent Appointments': 'Son Randevular',
        'No appointments found': 'Randevu bulunamadı',
        'Use the button above to create your first appointment.': 'İlk randevunuzu oluşturmak için yukarıdaki butonu kullanın.',
        'Create New Appointment': 'Yeni Randevu Oluştur'
    },
    'en': {
        'Recent Appointments': 'Recent Appointments',
        'No appointments found': 'No appointments found',
        'Use the button above to create your first appointment.': 'Use the button above to create your first appointment.',
        'Create New Appointment': 'Create New Appointment'
    },
    'de': {
        'Recent Appointments': 'Letzte Termine',
        'No appointments found': 'Keine Termine gefunden',
        'Use the button above to create your first appointment.': 'Verwenden Sie die Schaltfläche oben, um Ihren ersten Termin zu erstellen.',
        'Create New Appointment': 'Neuen Termin erstellen'
    },
    'fr': {
        'Recent Appointments': 'Rendez-vous récents',
        'No appointments found': 'Aucun rendez-vous trouvé',
        'Use the button above to create your first appointment.': 'Utilisez le bouton ci-dessus pour créer votre premier rendez-vous.',
        'Create New Appointment': 'Créer un nouveau rendez-vous'
    }
}

keys = [
    'Recent Appointments', 'No appointments found', 
    'Use the button above to create your first appointment.', 'Create New Appointment'
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
