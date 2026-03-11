# -*- coding: utf-8 -*-
import os

translations = {
    'tr': {
        'Customer Notes': 'Müşteri Notları'
    },
    'en': {
        'Customer Notes': 'Customer Notes'
    },
    'de': {
        'Customer Notes': 'Kundennotizen'
    },
    'fr': {
        'Customer Notes': 'Notes client'
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
