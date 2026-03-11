import os

history_dir = os.path.expandvars(r'%LOCALAPPDATA%\JetBrains')
if not os.path.exists(history_dir):
    print("No JetBrains folder found.")
    exit(0)

pycharm_dirs = [os.path.join(history_dir, d) for d in os.listdir(history_dir) if 'PyCharm' in d]
local_hist_dirs = [os.path.join(pd, 'LocalHistory') for pd in pycharm_dirs if os.path.exists(os.path.join(pd, 'LocalHistory'))]

best_content = ''
max_len = 0

for hist_dir in local_hist_dirs:
    for root, _, files in os.walk(hist_dir):
        for file in files:
            path = os.path.join(root, file)
            try:
                with open(path, 'rb') as f:
                    data = f.read()
                
                text = data.decode('utf-8', errors='ignore')
                
                # Split roughly by standard HTML or Jinja tags that would start the file
                blocks = text.split('{% extends "base.html" %}')
                for b in blocks[1:]:
                    if 'id="calendarView"' in b and 'quick_durum' in b:
                        # Extract until the last script tag or endblock
                        end_idx = b.rfind('{% endblock %}')
                        if end_idx != -1:
                            full_block = '{% extends "base.html" %}' + b[:end_idx + 14]
                            if len(full_block) > max_len:
                                max_len = len(full_block)
                                best_content = full_block
            except Exception as e:
                pass

if best_content:
    print('Found recovered content! Length:', len(best_content))
    out_path = r'd:\\Yazılım_Projeler\\Python\\CRM\\app\\templates\\gorevler.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(best_content)
    print('Recovered file written to', out_path)
else:
    print('Still could not find full content.')
