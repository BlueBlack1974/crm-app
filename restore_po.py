# -*- coding: utf-8 -*-
import os

langs = ['tr', 'en', 'de', 'fr']

for lang in langs:
    filepath = os.path.join('translations', lang, 'LC_MESSAGES', 'messages.po')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        out_lines = []
        for line in lines:
            if line.startswith('#~ '):
                # Remove the '#~ ' prefix to uncomment the translation
                out_lines.append(line[3:])
            else:
                out_lines.append(line)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(out_lines)
        print(f"Restored obsolete translations in {lang}/messages.po")

