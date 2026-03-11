import os

file_path = r'd:\Yazılım_Projeler\Python\CRM\translations\tr\LC_MESSAGES\messages.po'

new_translations = """
msgid "Instagram Messages"
msgstr "Instagram Mesajları"

msgid "Instagram Direct Messages"
msgstr "Instagram Direkt Mesajlar"

msgid "No customers with Instagram account found."
msgstr "Instagram hesabı olan müşteri bulunamadı."

msgid "Start a conversation"
msgstr "Bir sohbet başlat"

msgid "Unknown User"
msgstr "Bilinmeyen Kullanıcı"

msgid "Select a conversation"
msgstr "Bir sohbet seçin"

msgid "No message history available."
msgstr "Mesaj geçmişi bulunmuyor."

msgid "Customer has not contacted us yet."
msgstr "Müşteri henüz bizimle iletişime geçmedi."

msgid "No messages yet."
msgstr "Henüz mesaj yok."

msgid "Cannot send message: This customer has no linked Instagram ID (PSID). They must contact you first."
msgstr "Mesaj gönderilemiyor: Bu müşterinin bağlı bir Instagram ID'si (PSID) yok. Önce onların sizinle iletişime geçmesi gerekiyor."
"""

try:
    # Read existing content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if we already appended (partially) or if we need to clean up bad encoding
    if "Instagram Mesajları" in content:
        print("Translations might already be present.")
        # We might want to re-write valid utf-8 just in case
    else:
        content += new_translations

    # Write back with strict utf-8
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("File updated successfully with UTF-8.")

except UnicodeDecodeError:
    print("UnicodeDecodeError encountered. Attempting to fix...")
    # Try reading with 'latin-1' or similar and save as utf-8
    with open(file_path, 'r', encoding='latin-1') as f:
        content = f.read()
    
    # Remove potential garbage at end if any, or just append if safe
    if "Instagram Mesajları" not in content:
        content += new_translations
        
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("File recovered and updated with UTF-8.")
