# Fix onclick attribute quote escaping on line 212
with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the onclick with proper quote escaping
# Old: onclick="loadChat(..., this, '{{ ... }}', '{{ ... }}')"
# New: onclick="loadChat(..., this, &quot;{{ ... }}&quot;, &quot;{{ ... }}&quot;)"

old_onclick = """onclick="loadChat({{ conv.kullanici.KullaniciID }}, this, '{{ conv.kullanici.Ad }} {{ conv.kullanici.Soyad }}', '{{ conv.kullanici.ProfilFotografi }}')" """

new_onclick = """onclick="loadChat({{ conv.kullanici.KullaniciID }}, this, &quot;{{ conv.kullanici.Ad }} {{ conv.kullanici.Soyad }}&quot;, &quot;{{ conv.kullanici.ProfilFotografi }}&quot;)" """

content = content.replace(old_onclick.strip(), new_onclick.strip())

with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed onclick attribute quote escaping!")
