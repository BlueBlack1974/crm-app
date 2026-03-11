import os

keys = [
    'Dashboard', 'Appointments', 'New Appointment', 'Calendar', 
    'WhatsApp', 'Reports', 'Appointment Report', 'Customer Report',
    'Messages', 'Today\'s Reminders', 'Logs', 'Settings',
    'Language', 'Notifications', 'Mark all as read', 'Clear all',
    'Profile', 'Logout'
]

for root, dirs, files in os.walk('translations'):
    for file in files:
        if file.endswith('.po'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            out_lines = []
            i = 0
            while i < len(lines):
                line = lines[i]
                if line.startswith('#~ msgid '):
                    msgid = line[9:].strip().strip('"')
                    if msgid in keys:
                        out_lines.append(line.replace('#~ ', ''))
                        i += 1
                        while i < len(lines) and lines[i].startswith('#~ msgstr '):
                            out_lines.append(lines[i].replace('#~ ', ''))
                            i += 1
                        continue
                out_lines.append(line)
                i += 1
                
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(out_lines)
