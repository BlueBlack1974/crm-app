# Refactor to use global LOGGED_IN_USER_ID
with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 1. Insert global variable at the top of script
# Look for <script> or let currentChatUserId
for i, line in enumerate(lines):
    if 'let currentChatUserId = null;' in line:
        # Insert before this line
        lines.insert(i, "    const LOGGED_IN_USER_ID = {{ session.user_id if session.user_id else 'null' }};\n")
        break

# 2. Replace local usages
# Usage 1: const currentUserId = {{ session.user_id if session.user_id else 'null' }};
# Usage 2: const currentUserId = {{ session.user_id }};
# We want to replace these constructs with: const currentUserId = LOGGED_IN_USER_ID;

new_lines = []
for line in lines:
    # Check for usage 1
    if "const currentUserId = {{ session.user_id if session.user_id else 'null' }};" in line:
        line = line.replace("{{ session.user_id if session.user_id else 'null' }};", "LOGGED_IN_USER_ID;")
    
    # Check for usage 2
    elif "const currentUserId = {{ session.user_id }};" in line:
        line = line.replace("{{ session.user_id }};", "LOGGED_IN_USER_ID;")
        
    new_lines.append(line)

with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Refactored to use global LOGGED_IN_USER_ID!")
