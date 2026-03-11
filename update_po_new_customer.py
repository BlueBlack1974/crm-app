import os
import polib

locale_dir = 'translations'
translations = {
    'tr': {'New Customer': 'Yeni Müşteri'},
    'en': {'New Customer': 'New Customer'},
    'fr': {'New Customer': 'Nouveau Client'},
    'de': {'New Customer': 'Neuer Kunde'}
}

for lang, trans_dict in translations.items():
    po_path = os.path.join(locale_dir, lang, 'LC_MESSAGES', 'messages.po')
    if os.path.exists(po_path):
        po = polib.pofile(po_path)
        for msgid, msgstr in trans_dict.items():
            entry = po.find(msgid)
            if entry:
                entry.msgstr = msgstr
            else:
                entry = polib.POEntry(msgid=msgid, msgstr=msgstr)
                po.append(entry)
        po.save(po_path)
        print(f"Updated {po_path}")
    else:
        print(f"Not found: {po_path}")

print("Done updating PO files.")
