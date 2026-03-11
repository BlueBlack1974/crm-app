import re

with open('app/templates/rapor_musteriler.html', 'r', encoding='utf-8') as f:
    content = f.read()

scripts = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
js = '\n'.join(scripts)

print(f'Parantezler: (={js.count("(")}, )={js.count(")")}, fark={js.count("(")-js.count(")")}')
print(f'Süslü parantezler: {{={js.count("{")}, }}={js.count("}")}, fark={js.count("{")-js.count("}")}')

lines = js.split('\n')
b = 0
for i, line in enumerate(lines, 1):
    b += line.count('{') - line.count('}')
    if i >= len(lines) - 5:
        print(f'{i:4d}: brace={b:3d} | {line[:80]}')

print(f'\nSon durum: brace_count={b}')




