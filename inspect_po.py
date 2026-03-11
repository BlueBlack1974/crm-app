
path = r'd:\Yazılım_Projeler\Python\CRM\translations\tr\LC_MESSAGES\messages.po'
try:
    with open(path, 'rb') as f:
        for i, line in enumerate(f):
            if b"Giri" in line:
                print(f"Line {i+1}: {line}")
                # Print hex
                print(f"Hex: {line.hex()}")
                if i > 1100: break 
except Exception as e:
    print(e)
