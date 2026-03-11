import re

file_path = r'd:\Yazılım_Projeler\Python\CRM\app\templates\rapor_musteriler.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the broken multi-line 'Customer ID not found' 
pattern1 = r'alert\(\{\{\s*_\("Customer ID not found"\)\s*\|\s*tojson\s*\}\r?\n\s*\}\);\r?\n\s*return;\r?\n\s*\}'
if re.search(pattern1, content):
    content = re.sub(pattern1, 'alert(\'{{ _("Customer ID not found") }}\');\n                return;\n            }', content)
else:
    # If the file hasn't been completely broken, or is in an intermediate state
    # let's just indiscriminately replace anything containing the string
    content = re.sub(r'alert\(\{\{\s*_\("Customer ID not found"\).*?\}\s*\);?', 'alert(\'{{ _("Customer ID not found") }}\');', content, flags=re.DOTALL)

# Replace 'Customer updated successfully'
pattern2 = r'alert\(\{\{\s*_\("Customer updated successfully"\)\s*\|\s*tojson\s*\}\r?\n\s*\}\);?'
if re.search(pattern2, content):
    content = re.sub(pattern2, 'alert(\'{{ _("Customer updated successfully") }}\');', content)
else:
    content = re.sub(r'alert\(\{\{\s*_\("Customer updated successfully"\).*?\}\s*\);?', 'alert(\'{{ _("Customer updated successfully") }}\');', content, flags=re.DOTALL)

# Replace 'Error updating customer'
pattern3 = r'alert\(\{\{\s*_\("Error updating customer"\)\s*\|\s*tojson\s*\}\r?\n\s*\}\);?'
if re.search(pattern3, content):
    content = re.sub(pattern3, 'alert(\'{{ _("Error updating customer") }}\');', content)
else:
    content = re.sub(r'alert\(\{\{\s*_\("Error updating customer"\).*?\}\s*\);?', 'alert(\'{{ _("Error updating customer") }}\');', content, flags=re.DOTALL)


# Replace 'defaultUserName'
pattern4 = r'const defaultUserName = \{\{\s*session\.get\(\'user_name\',\s*\'\'\)\s*\|\s*tojson\s*\|\s*safe\r?\n\s*\}\r?\n\s*\};\r?\n'
if re.search(pattern4, content):
    content = re.sub(pattern4, 'const defaultUserName = \'{{ session.get("user_name", "") }}\';\n', content)
else:
    # fallback
    content = re.sub(r'const defaultUserName = \{\{\s*session\.get\(\'user_name\',\s*\'\'\).*?;\r?\n', 'const defaultUserName = \'{{ session.get("user_name", "") }}\';\n', content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Formatting bypass applied.")
