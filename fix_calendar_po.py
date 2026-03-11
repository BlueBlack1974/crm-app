# -*- coding: utf-8 -*-
import os

translations = {
    'tr': {
        'Monthly': 'Aylık',
        'Weekly': 'Haftalık',
        'Select Book': 'Defter Seç',
        'All Books': 'Tüm Defterler',
        'Calendar': 'Takvim',
        'Weekly View': 'Haftalık Görünüm',
        'This Week': 'Bu Hafta',
        'Today': 'Bugün',
        'Mon': 'Pzt',
        'Tue': 'Sal',
        'Wed': 'Çar',
        'Thu': 'Per',
        'Fri': 'Cum',
        'Sat': 'Cmt',
        'Sun': 'Paz',
        'Are you sure you want to move the appointment to': 'Randevuyu şu tarihe taşımak istediğinizden emin misiniz:',
        'Appointment moved successfully!': 'Randevu başarıyla taşındı!',
        'Session expired. Please login again.': 'Oturum süresi doldu. Lütfen tekrar giriş yapın.',
        'Invalid operation': 'Geçersiz işlem',
        'Error': 'Hata',
        'Unknown error': 'Bilinmeyen hata',
        'An error occurred while moving the appointment': 'Randevu taşınırken bir hata oluştu'
    },
    'en': {
        'Monthly': 'Monthly',
        'Weekly': 'Weekly',
        'Select Book': 'Select Book',
        'All Books': 'All Books',
        'Calendar': 'Calendar',
        'Weekly View': 'Weekly View',
        'This Week': 'This Week',
        'Today': 'Today',
        'Mon': 'Mon',
        'Tue': 'Tue',
        'Wed': 'Wed',
        'Thu': 'Thu',
        'Fri': 'Fri',
        'Sat': 'Sat',
        'Sun': 'Sun',
        'Are you sure you want to move the appointment to': 'Are you sure you want to move the appointment to',
        'Appointment moved successfully!': 'Appointment moved successfully!',
        'Session expired. Please login again.': 'Session expired. Please login again.',
        'Invalid operation': 'Invalid operation',
        'Error': 'Error',
        'Unknown error': 'Unknown error',
        'An error occurred while moving the appointment': 'An error occurred while moving the appointment'
    },
    'de': {
        'Monthly': 'Monatlich',
        'Weekly': 'Wöchentlich',
        'Select Book': 'Buch auswählen',
        'All Books': 'Alle Bücher',
        'Calendar': 'Kalender',
        'Weekly View': 'Wochenansicht',
        'This Week': 'Diese Woche',
        'Today': 'Heute',
        'Mon': 'Mo',
        'Tue': 'Di',
        'Wed': 'Mi',
        'Thu': 'Do',
        'Fri': 'Fr',
        'Sat': 'Sa',
        'Sun': 'So',
        'Are you sure you want to move the appointment to': 'Möchten Sie den Termin wirklich verschieben auf',
        'Appointment moved successfully!': 'Termin erfolgreich verschoben!',
        'Session expired. Please login again.': 'Sitzung abgelaufen. Bitte erneut anmelden.',
        'Invalid operation': 'Ungültiger Vorgang',
        'Error': 'Fehler',
        'Unknown error': 'Unbekannter Fehler',
        'An error occurred while moving the appointment': 'Beim Verschieben des Termins ist ein Fehler aufgetreten'
    },
    'fr': {
        'Monthly': 'Mensuel',
        'Weekly': 'Hebdomadaire',
        'Select Book': 'Sélectionner le carnet',
        'All Books': 'Tous les carnets',
        'Calendar': 'Calendrier',
        'Weekly View': 'Vue de semaine',
        'This Week': 'Cette semaine',
        'Today': 'Aujourdhui',
        'Mon': 'Lun',
        'Tue': 'Mar',
        'Wed': 'Mer',
        'Thu': 'Jeu',
        'Fri': 'Ven',
        'Sat': 'Sam',
        'Sun': 'Dim',
        'Are you sure you want to move the appointment to': 'Êtes-vous sûr de vouloir déplacer le rendez-vous à',
        'Appointment moved successfully!': 'Rendez-vous déplacé avec succès!',
        'Session expired. Please login again.': 'Session expirée. Veuillez vous reconnecter.',
        'Invalid operation': 'Opération invalide',
        'Error': 'Erreur',
        'Unknown error': 'Erreur inconnue',
        'An error occurred while moving the appointment': 'Une erreur est survenue lors du déplacement du rendez-vous'
    }
}

keys = list(translations['tr'].keys())

for lang in translations.keys():
    filepath = os.path.join('translations', lang, 'LC_MESSAGES', 'messages.po')
    if os.path.exists(filepath):
        # Oku
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        out_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Yorumlanan veya doğrudan eşleşen satırları al
            if line.startswith('#~ msgid ') or line.startswith('msgid '):
                prefix = '#~ msgid ' if line.startswith('#~ ') else 'msgid '
                msgid = line[len(prefix):].strip().strip('"')
                
                if msgid in keys:
                    out_lines.append(f'msgid "{msgid}"\n')
                    i += 1
                    # Sonraki msgstr kısmını atla
                    while i < len(lines) and (lines[i].startswith('#~ msgstr ') or lines[i].startswith('msgstr ')):
                        i += 1
                        
                    # Kendi msgstr mizi yaz
                    msgstr = translations[lang][msgid]
                    out_lines.append(f'msgstr "{msgstr}"\n\n')
                    continue
                    
            out_lines.append(line)
            i += 1
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(out_lines)
