# Properly fix the JavaScript block structure
with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# We need to find where forEach is and ensure it's inside the else block
# The else block should close AFTER the forEach, not before

# Looking at the structure:
# Line 354: } else {
# Line 355: const currentUserId...
# Line 358: data.mesajlar.forEach(msg => {
# Line 360: });
# Then we need a closing } for the else block

# Add proper indentation to forEach and add closing brace
for i in range(len(lines)):
    # Line 358-360 should be indented more (inside else block)
    if i == 357 and 'data.mesajlar.forEach' in lines[i]:
        lines[i] = '                    ' + lines[i].lstrip()
    elif i == 358:
        lines[i] = '                        ' + lines[i].lstrip()
    elif i == 359 and '});' in lines[i]:
        lines[i] = '                    ' + lines[i].lstrip()
        # After this line, we need to add the closing } for else
        lines.insert(i+1, '                }\r\n')
        break

with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed forEach indentation and added closing brace!")
