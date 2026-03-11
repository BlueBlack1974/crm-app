# Fix catch block indentation
with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix lines 367-370 (indices 366-369)
# They should have proper indentation matching the promise chain
for i in range(len(lines)):
    if i == 367 and 'chatArea.innerHTML' in lines[i] and 'Error loading messages' in lines[i]:
        # Fix indentation - should have 16 spaces
        lines[i] = '                chatArea.innerHTML = \'<div class="text-danger text-center mt-5">{{ _("Error loading messages.") }}</div>\';\r\n'
    elif i == 368 and 'console.error' in lines[i]:
        # Fix indentation - should have 16 spaces
        lines[i] = '                console.error(err);\r\n'
    elif i == 369 and lines[i].strip() == '});':
        # Fix indentation - should have 12 spaces
        lines[i] = '            });\r\n'

with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed catch block indentation!")
