# -*- coding: utf-8 -*-
import os

translations = {
    'tr': {
        'Appointments': 'Randevular',
        'All References': 'Tüm Referanslar',
        'All Books': 'Tüm Defterler',
        'All Statuses': 'Tüm Durumlar',
        'Cancelled': 'İptal',
        'All Users': 'Tüm Kullanıcılar',
        'Custom': 'Özel',
        'Today': 'Bugün',
        'This Month': 'Bu Ay',
        'This Year': 'Bu Yıl',
        'Start Date': 'Başlangıç Tarihi',
        'End Date': 'Bitiş Tarihi',
        'All': 'Tümü',
        'Reference': 'Referans',
        'Quick Date': 'Hızlı Tarih',
        'Created By': 'Oluşturan',
        'Appointment List': 'Randevu Listesi',
        'Phone': 'Telefon',
        'Duration': 'Süre'
    },
    'en': {
        'Appointments': 'Appointments',
        'All References': 'All References',
        'All Books': 'All Books',
        'All Statuses': 'All Statuses',
        'Cancelled': 'Cancelled',
        'All Users': 'All Users',
        'Custom': 'Custom',
        'Today': 'Today',
        'This Month': 'This Month',
        'This Year': 'This Year',
        'Start Date': 'Start Date',
        'End Date': 'End Date',
        'All': 'All',
        'Reference': 'Reference',
        'Quick Date': 'Quick Date',
        'Created By': 'Created By',
        'Appointment List': 'Appointment List',
        'Phone': 'Phone',
        'Duration': 'Duration'
    },
    'de': {
        'Appointments': 'Termine',
        'All References': 'Alle Referenzen',
        'All Books': 'Alle Bücher',
        'All Statuses': 'Alle Status',
        'Cancelled': 'Abgesagt',
        'All Users': 'Alle Benutzer',
        'Custom': 'Benutzerdefiniert',
        'Today': 'Heute',
        'This Month': 'Dieser Monat',
        'This Year': 'Dieses Jahr',
        'Start Date': 'Startdatum',
        'End Date': 'Enddatum',
        'All': 'Alle',
        'Reference': 'Referenz',
        'Quick Date': 'Schnelles Datum',
        'Created By': 'Erstellt von',
        'Appointment List': 'Terminliste',
        'Phone': 'Telefon',
        'Duration': 'Dauer'
    },
    'fr': {
        'Appointments': 'Rendez-vous',
        'All References': 'Toutes les références',
        'All Books': 'Tous les livres',
        'All Statuses': 'Tous les statuts',
        'Cancelled': 'Annulé',
        'All Users': 'Tous les utilisateurs',
        'Custom': 'Personnalisé',
        'Today': 'Aujourdhui',
        'This Month': 'Ce mois-ci',
        'This Year': 'Cette année',
        'Start Date': 'Date de début',
        'End Date': 'Date de fin',
        'All': 'Tout',
        'Reference': 'Référence',
        'Quick Date': 'Date rapide',
        'Created By': 'Créé par',
        'Appointment List': 'Liste des rendez-vous',
        'Phone': 'Téléphone',
        'Duration': 'Durée'
    }
}

keys = list(translations['tr'].keys())

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
