import sys
from jinja2 import Environment, FileSystemLoader

try:
    env = Environment(loader=FileSystemLoader('d:/Yazılım_Projeler/Python/CRM/app/templates'))
    env.filters['tojson'] = lambda x: x
    with open('d:/Yazılım_Projeler/Python/CRM/app/templates/rapor_musteriler.html', 'r', encoding='utf-8') as f:
        source = f.read()
    env.parse(source)
    print("Template parsed successfully!")
except Exception as e:
    print(f"JINJA ERROR: {e}")
    if hasattr(e, 'lineno'):
        print(f"LINE NUMBER: {e.lineno}")
