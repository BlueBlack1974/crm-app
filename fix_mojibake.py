
import os

file_path = r'd:\Yazılım_Projeler\Python\CRM\translations\tr\LC_MESSAGES\messages.po'

replacements = {
    'Ã¼': 'ü',
    'ÅŸ': 'ş',
    'Ã§': 'ç',
    'ÄŸ': 'ğ',
    'Ä±': 'ı',
    'Ã¶': 'ö',
    'Ã–': 'Ö',
    'Ã‡': 'Ç',
    'Åž': 'Ş',
    'Ä°': 'İ',
    'Ãœ': 'Ü',
    'Ä': 'Ğ', # Edge case for capital Ğ if corrupted differently, but usually covered.
    # Common ones again for safety if mixed
    'Ã¢': 'â',
}

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Apply replacements
    # It's safer to handle the multi-byte sequences first if they overlap, but these are mostly distinct.
    
    # Specific known corruptions from grep:
    # "GiriÅŸ" -> "Giriş" (ÅŸ -> ş)
    # "KullanÄ±cÄ±" -> "Kullanıcı" (Ä± -> ı)
    # "deÄŸiÅŸtirildi" -> "değiştirildi" (ÄŸ -> ğ, ÅŸ -> ş)
    
    new_content = content
    for bad, good in replacements.items():
        new_content = new_content.replace(bad, good)
        
    # Extra safety: some might be "Å" without the following char if cut off, 
    # but "ÅŸ" covers 'ş'. "Å" alone is rare in TR unless it's 'Ş' corrupted differently?
    # "Åž" is 'Ş'.
    
    # Let's write it back
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Fixed mojibake in messages.po")
    else:
        print("No changes needed or patterns not found.")

except Exception as e:
    print(f"Error processing file: {e}")
