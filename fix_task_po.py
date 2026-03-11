# -*- coding: utf-8 -*-
import os

translations = {
    'tr': {'Yapılacaklar': 'Yapılacaklar', 'Görevler': 'Görevler', 'Görev Raporları': 'Görev Raporları'},
    'en': {'Yapılacaklar': 'Todos', 'Görevler': 'Tasks', 'Görev Raporları': 'Task Reports'},
    'de': {'Yapılacaklar': 'Aufgabenliste', 'Görevler': 'Aufgaben', 'Görev Raporları': 'Aufgabenberichte'},
    'fr': {'Yapılacaklar': 'Liste de tâches', 'Görevler': 'Tâches', 'Görev Raporları': 'Rapports de tâches'}
}

keys = ['Yapılacaklar', 'Görevler', 'Görev Raporları']

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
