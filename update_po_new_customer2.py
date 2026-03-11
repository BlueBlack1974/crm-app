import os

locale_dir = 'translations'
translations = {
    'tr': 'Yeni Müşteri',
    'en': 'New Customer',
    'fr': 'Nouveau Client',
    'de': 'Neuer Kunde'
}

for lang, msgstr in translations.items():
    po_path = os.path.join(locale_dir, lang, 'LC_MESSAGES', 'messages.po')
    if os.path.exists(po_path):
        with open(po_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'msgid "New Customer"' not in content:
            with open(po_path, 'a', encoding='utf-8') as f:
                f.write('\nmsgid "New Customer"\n')
                f.write(f'msgstr "{msgstr}"\n')
            print(f"Added to {po_path}")
        else:
            print(f"Already exists in {po_path}")
    else:
        print(f"Not found: {po_path}")

print("Done updating PO files.")
