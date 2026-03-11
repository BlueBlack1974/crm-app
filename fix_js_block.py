# Fix the JavaScript block structure in kullanici_mesajlar.html
with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The problem is:
# Line 357 has a closing } that shouldn't be there
# Line 362 has an extra closing }
# The forEach should be inside the else block

# Remove line 357 (index 356) if it's just whitespace and }
# Remove line 362 (index 361) if it's just whitespace and }

new_lines = []
for i, line in enumerate(lines):
    # Skip line 357 (index 356) if it's just closing brace
    if i == 356 and line.strip() == '}':
        continue
    # Skip line 362 (index 361) if it's just closing brace and indent
    if i == 361 and line.strip() == '}':
        continue
    new_lines.append(line)

with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed JavaScript block structure!")
