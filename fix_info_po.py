# -*- coding: utf-8 -*-
import os

translations = {
    'tr': {
        'Information': 'Bilgilendirme',
        'Note': 'Not',
        'Full permissions will be automatically granted to the appointment you create.': 'Oluşturduğunuz randevuya otomatik olarak tam yetki verilecektir.',
        'Appointment Statuses': 'Randevu Durumları',
        'Pending': 'Beklemede',
        'Newly created appointments': 'Yeni oluşturulan randevular',
        'Confirmed': 'Onaylandı',
        'Confirmed appointments': 'Onaylanan randevular',
        'Cancelled': 'İptal',
        'Cancelled appointments': 'İptal edilen randevular',
        'Completed': 'Tamamlandı',
        'Completed appointments': 'Tamamlanan randevular',
        'Calendar': 'Takvim',
        'Cancel': 'İptal',
        'Session expired. Please login again.': 'Oturum süresi doldu. Lütfen tekrar giriş yapın.',
        'Failed to load slots': 'Saatler yüklenirken bir hata oluştu',
        'No available time slots for this date. Please choose another date.': 'Bu tarihte uygun saat dilimi bulunmuyor. Lütfen başka bir tarih seçin.'
    },
    'en': {
        'Information': 'Information',
        'Note': 'Note',
        'Full permissions will be automatically granted to the appointment you create.': 'Full permissions will be automatically granted to the appointment you create.',
        'Appointment Statuses': 'Appointment Statuses',
        'Pending': 'Pending',
        'Newly created appointments': 'Newly created appointments',
        'Confirmed': 'Confirmed',
        'Confirmed appointments': 'Confirmed appointments',
        'Cancelled': 'Cancelled',
        'Cancelled appointments': 'Cancelled appointments',
        'Completed': 'Completed',
        'Completed appointments': 'Completed appointments',
        'Calendar': 'Calendar',
        'Cancel': 'Cancel',
        'Session expired. Please login again.': 'Session expired. Please login again.',
        'Failed to load slots': 'Failed to load slots',
        'No available time slots for this date. Please choose another date.': 'No available time slots for this date. Please choose another date.'
    },
    'de': {
        'Information': 'Information',
        'Note': 'Hinweis',
        'Full permissions will be automatically granted to the appointment you create.': 'Sie erhalten automatisch volle Rechte für den erstellten Termin.',
        'Appointment Statuses': 'Terminstatus',
        'Pending': 'Ausstehend',
        'Newly created appointments': 'Neu erstellte Termine',
        'Confirmed': 'Bestätigt',
        'Confirmed appointments': 'Bestätigte Termine',
        'Cancelled': 'Abgesagt',
        'Cancelled appointments': 'Abgesagte Termine',
        'Completed': 'Abgeschlossen',
        'Completed appointments': 'Abgeschlossene Termine',
        'Calendar': 'Kalender',
        'Cancel': 'Abbrechen',
        'Session expired. Please login again.': 'Sitzung abgelaufen. Bitte erneut anmelden.',
        'Failed to load slots': 'Slots konnten nicht geladen werden',
        'No available time slots for this date. Please choose another date.': 'Keine freien Termine an diesem Datum. Bitte wählen Sie ein anderes Datum.'
    },
    'fr': {
        'Information': 'Information',
        'Note': 'Note',
        'Full permissions will be automatically granted to the appointment you create.': 'Des autorisations complètes seront automatiquement accordées pour le rendez-vous créé.',
        'Appointment Statuses': 'Statuts de rendez-vous',
        'Pending': 'En attente',
        'Newly created appointments': 'Rendez-vous nouvellement créés',
        'Confirmed': 'Confirmé',
        'Confirmed appointments': 'Rendez-vous confirmés',
        'Cancelled': 'Annulé',
        'Cancelled appointments': 'Rendez-vous annulés',
        'Completed': 'Terminé',
        'Completed appointments': 'Rendez-vous terminés',
        'Calendar': 'Calendrier',
        'Cancel': 'Annuler',
        'Session expired. Please login again.': 'Session expirée. Veuillez vous reconnecter.',
        'Failed to load slots': 'Échec du chargement des créneaux',
        'No available time slots for this date. Please choose another date.': 'Aucun créneau disponible pour cette date. Veuillez choisir une autre date.'
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
