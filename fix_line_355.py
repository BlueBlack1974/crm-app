# Fix line 355 in kullanici_mesajlar.html
with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 355 (index 354) should be fixed
# Current: "                    const currentUserId = {{ session.user_id if session.user_id else 'null' }\r\n"
# Should be: "                    const currentUserId = {{ session.user_id if session.user_id else 'null' }};\r\n"

# Line 356 (index 355) should be removed as it's just "};"
# We need to merge them

if len(lines) > 355:
    # Fix line 355 - add the missing }
    lines[354] = lines[354].rstrip('\r\n').rstrip(' }') + ' }};\r\n'
    # Remove line 356 if it's just whitespace and };
    if lines[355].strip() == '};':
        lines.pop(355)

with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed line 355!")
