import flask
from jinja2 import Environment, FileSystemLoader

try:
    env = Environment(loader=FileSystemLoader('d:/Yazýlým_Projeler/Python/CRM/app/templates'))
    template = env.get_template('rapor_musteriler.html')
    print("Template parsed successfully!")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"JINJA ERROR: {e}")
