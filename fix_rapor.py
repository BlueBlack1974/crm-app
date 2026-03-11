import sys
import re

file_path = r'd:\Yazılım_Projeler\Python\CRM\app\templates\rapor_musteriler.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix line 1439
pattern1 = r'alert\(\{\{\s*_\("Customer ID not found"\)\s*\|\s*tojson\s*\}\r?\n\s*\}\);\r?\n\s*return;\r?\n\s*\}'
replacement1 = 'alert({{ _("Customer ID not found") | tojson }});\n                return;\n            }'
val1_matches = re.findall(pattern1, content)
print("Matches found for pattern 1:", len(val1_matches))
content = re.sub(pattern1, replacement1, content)

# Fix line 1456
pattern2 = r'alert\(\{\{\s*_\("Customer updated successfully"\)\s*\|\s*tojson\s*\}\r?\n\s*\}\);'
replacement2 = 'alert({{ _("Customer updated successfully") | tojson }});'
val2_matches = re.findall(pattern2, content)
print("Matches found for pattern 2:", len(val2_matches))
content = re.sub(pattern2, replacement2, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("File updated manually.")
