import urllib.request
try:
    with open('d:\\Yazılım_Projeler\\Python\\CRM\\app\\templates\\base.html', 'r', encoding='utf-8') as f:
        html = f.read()
        lines = html.split('\n')
        for i, line in enumerate(lines):
            if 'dark' in line.lower() and ('form-control' in line.lower() or 'table' in line.lower() or 'input' in line.lower()):
                print(f'{i+1}: {line.strip()}')
