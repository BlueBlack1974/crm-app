
import os

file_path = r'd:\Yazılım_Projeler\Python\CRM\translations\tr\LC_MESSAGES\messages.po'

# Generate the map of corrupted -> correct
chars_to_fix = "şçğüıöŞÇĞÜİÖ"
replacements = {}

for c in chars_to_fix:
    try:
        # Simulate the corruption: UTF-8 bytes interpreted as Latin-1
        corrupted = c.encode('utf-8').decode('latin-1')
        replacements[corrupted] = c
    except Exception as e:
        print(f"Skipping {c}: {e}")

# Manual additions if needed (though the loop should cover standard ones)
# 'İ' is C4 B0 -> Ä + degree sign (°)
# 'ı' is C4 B1 -> Ä + plus-minus (±)

print("Replacement map:")
for k, v in replacements.items():
    print(f"{repr(k)} -> {v}")

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content
    for bad, good in replacements.items():
        new_content = new_content.replace(bad, good)
        
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Success: Fixed Latin-1 mojibake in messages.po")
    else:
        print("No changes made. Patterns might still be wrong or already fixed.")

except Exception as e:
    print(f"Error: {e}")
