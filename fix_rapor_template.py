"""
Rapor müşteriler şablonundaki Jinja2 syntax hatalarını düzeltir
"""

def fix_template():
    template_path = r"D:\Yazılım_Projeler\Python\CRM\app\templates\rapor_musteriler.html"
    
    print(f"Dosya okunuyor: {template_path}")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # 1. Fix: Satır 696-697 arası bozuk array syntaxını düzelt
    content = content.replace(
        "labels: bookLabels.length > 0 ? bookLabels : [{{ _('No Data') | tojson }\n                }],",
        "labels: bookLabels.length > 0 ? bookLabels : [{{ _('No Data') | tojson }}],"
    )
    
    # 2. Fix: Satır 711'deki boşluklu Jinja tagini düzelt
    content = content.replace(
        "text: { { _('Appointment Book Distribution') | tojson } }",
        "text: {{ _('Appointment Book Distribution') | tojson }}"
    )
    
    # 3. Fix: Monthly chart için de aynı hataları düzelt (eğer varsa)
    content = content.replace(
        "labels: monthlyLabels.length > 0 ? monthlyLabels : [{{ _('No Data') | tojson }\n                }],",
        "labels: monthlyLabels.length > 0 ? monthlyLabels : [{{ _('No Data') | tojson }}],"
    )
    
    content = content.replace(
        "text: { { _('Monthly Appointment Distribution') | tojson } }",
        "text: {{ _('Monthly Appointment Distribution') | tojson }}"
    )
    
    if content == original_content:
        print("⚠️  Değiştirilecek bir şey bulunamadı. Dosya zaten düzgün olabilir.")
        return False
    
    print("Değişiklikler yapılıyor...")
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Dosya başarıyla düzeltildi!")
    print("\nYapılan düzeltmeler:")
    print("- Jinja2 tag'lerindeki boşluklar kaldırıldı")
    print("- Array syntax hataları düzeltildi")
    print("\nLütfen Flask uygulamasını yeniden başlatın (CTRL+C sonra tekrar python run.py)")
    
    return True

if __name__ == '__main__':
    try:
        fix_template()
    except Exception as e:
        print(f"❌ Hata oluştu: {e}")
        import traceback
        traceback.print_exc()
