import re

file_path = r'd:\Yazılım_Projeler\Python\CRM\app\templates\rapor_musteriler.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace 'Customer added successfully'
pattern1 = r'alert\(\{\{\s*_\("Customer added successfully"\)\s*\|\s*tojson\s*\}\r?\n\s*\}\);?'
if re.search(pattern1, content):
    content = re.sub(pattern1, 'alert(\'{{ _("Customer added successfully") }}\');', content)
else:
    content = re.sub(r'alert\(\{\{\s*_\("Customer added successfully"\).*?\}\s*\);?', 'alert(\'{{ _("Customer added successfully") }}\');', content, flags=re.DOTALL)

# Replace 'An error occurred'
pattern2 = r'alert\(\{\{\s*_\("An error occurred"\)\s*\|\s*tojson\s*\}\r?\n\s*\}\);?'
if re.search(pattern2, content):
    content = re.sub(pattern2, 'alert(\'{{ _("An error occurred") }}\');', content)
else:
    content = re.sub(r'alert\(\{\{\s*_\("An error occurred"\).*?\}\s*\);?', 'alert(\'{{ _("An error occurred") }}\');', content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Formatting bypass applied globally.")
