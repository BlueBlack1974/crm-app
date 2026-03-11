file_path = r'd:\Yazılım_Projeler\Python\CRM\app\templates\rapor_musteriler.html'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '{ _("Customer ID not found") | tojson }' in line:
        print(f"Match 1 at line {i+1}: {repr(line)}")
        if '});' in lines[i+1]:
            print(f"Next line: {repr(lines[i+1])}")
            lines[i] = '                alert({{ _("Customer ID not found") | tojson }});\n'
            lines[i+1] = ''

    if '{ _("Customer updated successfully") | tojson }' in line:
        print(f"Match 2 at line {i+1}: {repr(line)}")
        if '});' in lines[i+1]:
            print(f"Next line: {repr(lines[i+1])}")
            lines[i] = '                alert({{ _("Customer updated successfully") | tojson }});\n'
            lines[i+1] = ''

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Replacement complete.")
