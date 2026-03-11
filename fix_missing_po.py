# -*- coding: utf-8 -*-
import os
import re

translations = {
    'tr': {
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
        'Customer Notes': 'Müşteri Notları'
    },
    'en': {
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
        'Customer Notes': 'Customer Notes'
    },
    'de': {
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
        'Customer Notes': 'Kundennotizen'
    },
    'fr': {
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
        'Customer Notes': 'Notes client'
    }
}

for lang, data in translations.items():
    filepath = os.path.join('translations', lang, 'LC_MESSAGES', 'messages.po')
    if not os.path.exists(filepath):
        continue
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    appended = False
    with open(filepath, 'a', encoding='utf-8') as f:
        for key, val in data.items():
            # Tam kelime eşleşmesi kontrolü msgid "key" (quotes included)
            # Escaping the key if there are quotes inside
            escaped_key = key.replace('"', '\\"')
            escaped_val = val.replace('"', '\\"')
            
            # Use basic string matching because re might fail with complex strings
            search_str = f'msgid "{escaped_key}"'
            
            if search_str not in content:
                f.write(f'\nmsgid "{escaped_key}"\nmsgstr "{escaped_val}"\n\n')
                appended = True
            
    if appended:
        print(f"Added missing keys for {lang}")
