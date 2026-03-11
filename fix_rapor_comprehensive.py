"""
Rapor müşteriler şablonundaki TÜM Jinja2 syntax hatalarını düzeltir
"""
import re

def fix_template_comprehensive():
    template_path = r"D:\Yazılım_Projeler\Python\CRM\app\templates\rapor_musteriler.html"
    
    print(f"Dosya okunuyor: {template_path}")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    changes_made = []
    
    for i, line in enumerate(lines, 1):
        original_line = line
        
        # Fix 1: {{ gender_data | tojson} eksik parantez
        if 'gender_data | tojson' in line and '}}' not in line:
            line = line.replace('{{ gender_data | tojson', '{{ gender_data | tojson }}')
            changes_made.append(f"Satır {i}: gender_data tojson tag kapandı")
        
        # Fix 2: Boşluklu Jinja taglerini düzelt
        line = re.sub(r'\{\{\s+_\(', '{{ _(', line)
        line = re.sub(r'\)\s+\|\s+tojson\s+\}\s+\}', ') | tojson }}', line)
        
        # Fix 3: Array syntax hataları
        if "[{{ _('No Data') | tojson }" in line and not "}}]" in line:
            line = line.replace("[{{ _('No Data') | tojson }", "[{{ _('No Data') | tojson }}]")
            changes_made.append(f"Satır {i}: Array syntax düzeltildi")
        
        if line != original_line:
            if f"Satır {i}" not in str(changes_made):
                changes_made.append(f"Satır {i}: Jinja2 syntax düzeltildi")
        
        fixed_lines.append(line)
    
    print(f"\nToplam {len(changes_made)} değişiklik yapıldı:")
    for change in changes_made[:10]:  # İlk 10 değişikliği göster
        print(f"  - {change}")
    if len(changes_made) > 10:
        print(f"  ... ve {len(changes_made) - 10} değişiklik daha")
    
    # Dosyayı yaz
    with open(template_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)
    
    print("\n✅ Dosya başarıyla düzeltildi!")
    print("\n⚠️  ÖNEMLİ:")
    print("1. VS Code'da rapor_musteriler.html dosyasını KAPATIN")
    print("2. Flask uygulamasını yeniden başlatın (CTRL+C sonra python run.py)")
    
    return True

if __name__ == '__main__':
    try:
        fix_template_comprehensive()
    except Exception as e:
        print(f"❌ Hata oluştu: {e}")
        import traceback
        traceback.print_exc()
