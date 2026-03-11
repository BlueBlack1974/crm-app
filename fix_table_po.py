# -*- coding: utf-8 -*-
import os

translations = {
    'tr': {
        'Title': 'Başlık',
        'Customer': 'Müşteri',
        'Date': 'Tarih',
        'Book': 'Defter',
        'Status': 'Durum',
        'Actions': 'İşlemler'
    },
    'en': {
        'Title': 'Title',
        'Customer': 'Customer',
        'Date': 'Date',
        'Book': 'Book',
        'Status': 'Status',
        'Actions': 'Actions'
    },
    'de': {
        'Title': 'Titel',
        'Customer': 'Kunde',
        'Date': 'Datum',
        'Book': 'Buch',
        'Status': 'Status',
        'Actions': 'Aktionen'
    },
    'fr': {
        'Title': 'Titre',
        'Customer': 'Client',
        'Date': 'Date',
        'Book': 'Livre',
        'Status': 'Statut',
        'Actions': 'Actions'
    }
}

keys = ['Title', 'Customer', 'Date', 'Book', 'Status', 'Actions']

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
