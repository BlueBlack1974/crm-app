# Refactor loadChat to use data-attributes
with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update HTML
# Search for the onclick line
old_html_pattern = """            <div class="list-group-item chat-item position-relative d-flex align-items-center"
                onclick="loadChat({{ conv.kullanici.KullaniciID }}, this, &quot;{{ conv.kullanici.Ad }} {{ conv.kullanici.Soyad }}&quot;, &quot;{{ conv.kullanici.ProfilFotografi }}&quot;)"
                data-user-name="{{ conv.kullanici.Ad }} {{ conv.kullanici.Soyad }}">"""

new_html_pattern = """            <div class="list-group-item chat-item position-relative d-flex align-items-center"
                onclick="loadChat(this)"
                data-user-id="{{ conv.kullanici.KullaniciID }}"
                data-user-name="{{ conv.kullanici.Ad }} {{ conv.kullanici.Soyad }}"
                data-user-avatar="{{ conv.kullanici.ProfilFotografi }}">"""

# We need to be careful with exact whitespace in search.
# Let's try to match by parts or regex if direct replacement fails.
# But for now let's try direct replacement assuming previous reads were accurate.

# 2. Update JS function definition
old_js_def = "function loadChat(userId, element, userName, avatarPath) {"
new_js_def = """function loadChat(element) {
        const userId = element.dataset.userId;
        const userName = element.dataset.userName;
        const avatarPath = element.dataset.userAvatar;"""

# Replace HTML
# Note: The file might have slightly different whitespace/newlines.
# Using a more robust replacement strategy.

import re

# Regex for the HTML part
html_regex = r'<div class="list-group-item chat-item position-relative d-flex align-items-center"\s+onclick="loadChat\([^"]+"\)\s+data-user-name="[^"]+">'
html_replacement = """<div class="list-group-item chat-item position-relative d-flex align-items-center"
                onclick="loadChat(this)"
                data-user-id="{{ conv.kullanici.KullaniciID }}"
                data-user-name="{{ conv.kullanici.Ad }} {{ conv.kullanici.Soyad }}"
                data-user-avatar="{{ conv.kullanici.ProfilFotografi }}">"""

# Update HTML using simple replacement if possible, or manual splicing
lines = content.splitlines()
new_lines = []
skip = False

for i, line in enumerate(lines):
    if 'onclick="loadChat(' in line and '{{ conv.kullanici.KullaniciID }}' in line:
        # Found the onclick line
        # The previous line (div) needs to be kept, but we are replacing the block
        pass
    
# Let's use the exact string we just wrote in the previous step (Step 226)
# It was: onclick="loadChat({{ conv.kullanici.KullaniciID }}, this, &quot;{{ conv.kullanici.Ad }} {{ conv.kullanici.Soyad }}&quot;, &quot;{{ conv.kullanici.ProfilFotografi }}&quot;)"

# Let's rewrite the file logic to find the lines
for i in range(len(lines)):
    if 'onclick="loadChat' in lines[i] and '&quot;' in lines[i]:
        # This is line 212
        lines[i] = '                onclick="loadChat(this)"'
        # We need to add the other data attributes.
        # Line 213 is data-user-name.
        # We can add data-user-id and data-user-avatar around it.
    
    if 'data-user-name="' in lines[i] and '{{ conv.kullanici.Ad }}' in lines[i]:
        # Append other attributes
        indent = '                '
        lines[i] = f'{indent}data-user-id="{{{{ conv.kullanici.KullaniciID }}}}"\r\n{lines[i].rstrip()}\r\n{indent}data-user-avatar="{{{{ conv.kullanici.ProfilFotografi }}}}"'

    if 'function loadChat(userId, element, userName, avatarPath) {' in lines[i]:
        lines[i] = '    function loadChat(element) {'
        lines.insert(i+1, "        const userId = element.getAttribute('data-user-id');")
        lines.insert(i+2, "        const userName = element.getAttribute('data-user-name');")
        lines.insert(i+3, "        const avatarPath = element.getAttribute('data-user-avatar');")

content_out = '\n'.join(lines)
# Actually, the string replacement above is risky with indices if we insert lines while iterating.
# Be careful.

# Better approach: Replace string blocks.

# 2. Update JS
content = content.replace("function loadChat(userId, element, userName, avatarPath) {", 
                          """function loadChat(element) {
        const userId = element.getAttribute('data-user-id');
        const userName = element.getAttribute('data-user-name');
        const avatarPath = element.getAttribute('data-user-avatar');""")

# 1. Update HTML
# We know exact line content from previous reads
# Line 212: onclick="loadChat({{ conv.kullanici.KullaniciID }}, this, &quot;{{ conv.kullanici.Ad }} {{ conv.kullanici.Soyad }}&quot;, &quot;{{ conv.kullanici.ProfilFotografi }}&quot;)"
line_212_old = '                onclick="loadChat({{ conv.kullanici.KullaniciID }}, this, &quot;{{ conv.kullanici.Ad }} {{ conv.kullanici.Soyad }}&quot;, &quot;{{ conv.kullanici.ProfilFotografi }}&quot;)"'
line_212_new = '                onclick="loadChat(this)"\n                data-user-id="{{ conv.kullanici.KullaniciID }}"\n                data-user-avatar="{{ conv.kullanici.ProfilFotografi }}"'

content = content.replace(line_212_old.strip(), line_212_new.strip())

with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Refactored to use data attributes!")
