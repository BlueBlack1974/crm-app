# -*- coding: utf-8 -*-
import sys
from jinja2 import Environment, FileSystemLoader

try:
    env = Environment(loader=FileSystemLoader('d:/Yazılım_Projeler/Python/CRM/app/templates'))
    
    # Add some mock filters and variables so it doesn't fail on missing globals if it tries to render (we just parse)
    env.filters['tojson'] = lambda x: x
    
    # Parse the template to find syntax errors
    with open('d:/Yazılım_Projeler/Python/CRM/app/templates/rapor_musteriler.html', 'r', encoding='utf-8') as f:
        source = f.read()
    env.parse(source)
    print("Template parsed successfully!")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"JINJA ERROR: {e}")
