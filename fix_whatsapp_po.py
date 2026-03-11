# -*- coding: utf-8 -*-
import os

translations = {
    'tr': {
        'Select a customer to start chatting': 'Sohbete başlamak için bir müşteri seçin',
        'Select a customer from the list to view messages': 'Mesajları görüntülemek için listeden bir müşteri seçin'
    },
    'en': {
        'Select a customer to start chatting': 'Select a customer to start chatting',
        'Select a customer from the list to view messages': 'Select a customer from the list to view messages'
    },
    'de': {
        'Select a customer to start chatting': 'Wählen Sie einen Kunden aus, um den Chat zu starten',
        'Select a customer from the list to view messages': 'Wählen Sie einen Kunden aus der Liste, um Nachrichten anzuzeigen'
    },
    'fr': {
        'Select a customer to start chatting': 'Sélectionnez un client pour discuter',
        'Select a customer from the list to view messages': 'Sélectionnez un client dans la liste pour voir les messages'
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
            escaped_key = key.replace('"', '\\"')
            escaped_val = val.replace('"', '\\"')
            
            search_str = f'msgid "{escaped_key}"'
            
            if search_str not in content:
                f.write(f'\nmsgid "{escaped_key}"\nmsgstr "{escaped_val}"\n\n')
                appended = True
            
    if appended:
        print(f"Added missing keys for {lang}")
