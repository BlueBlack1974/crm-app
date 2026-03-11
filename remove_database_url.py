#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DATABASE_URL satırını .env dosyasından kaldır"""

import os

# .env dosyasının yolu
env_path = r'D:\Yazılım_Projeler\Python\CRM\.env'

try:
    # Dosyayı oku
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # DATABASE_URL ile başlayan satırları filtrele
        filtered_lines = []
        removed_count = 0
        for line in lines:
            stripped = line.strip()
            # DATABASE_URL ile başlayan satırları atla (boşluk veya # ile başlayanlar hariç)
            if stripped and not stripped.startswith('#') and stripped.startswith('DATABASE_URL'):
                removed_count += 1
                print(f"Kaldirilan satir: {stripped[:80]}...")
                continue
            filtered_lines.append(line)
        
        # Dosyayı yaz
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(filtered_lines)
        
        print(f"✓ DATABASE_URL satiri kaldirildi. ({removed_count} satir silindi)")
    else:
        print(f"✗ .env dosyasi bulunamadi: {env_path}")
        print("Dosya mevcut degil veya farkli bir konumda olabilir.")
        
except Exception as e:
    print(f"Hata: {e}")

