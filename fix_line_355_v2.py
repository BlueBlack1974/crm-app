# Fix the duplicate braces on line 355
with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the problematic line
content = content.replace(
    "const currentUserId = {{ session.user_id if session.user_id else 'null' }}; }};",
    "const currentUserId = {{ session.user_id if session.user_id else 'null' }};"
)

# Also remove the orphaned }; line if it exists
lines = content.split('\n')
fixed_lines = []
skip_next = False
for i, line in enumerate(lines):
    if skip_next:
        skip_next = False
        continue
    fixed_lines.append(line)
    # If this line has the fixed currentUserId and next line is just whitespace + };
    if 'const currentUserId = {{ session.user_id if session.user_id else' in line and i + 1 < len(lines):
        next_line = lines[i + 1].strip()
        if next_line == '};':
            skip_next = True

content = '\n'.join(fixed_lines)

with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("Fixed!")
