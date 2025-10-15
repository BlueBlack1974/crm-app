from PIL import Image
import os

def create_transparent_favicon():
    """Logo.png dosyasından şeffaf arka planlı favicon oluştur"""
    
    # Kaynak PNG dosyası
    source_file = 'static/img/Logo.png'
    
    if not os.path.exists(source_file):
        print(f"Hata: {source_file} dosyası bulunamadı!")
        return
    
    # Farklı boyutlar
    sizes = [12, 24, 36, 48, 60, 72, 84, 96, 108, 120]
    
    try:
        # Kaynak resmi aç
        source_img = Image.open(source_file)
        print(f"Kaynak resim boyutu: {source_img.size}")
        
        # Eğer resim RGBA değilse, RGBA'ya çevir
        if source_img.mode != 'RGBA':
            source_img = source_img.convert('RGBA')
        
        for size in sizes:
            # Resmi yeniden boyutlandır
            resized_img = source_img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Beyaz pikselleri şeffaf yap
            data = resized_img.getdata()
            new_data = []
            for item in data:
                # Beyaz pikselleri şeffaf yap (RGB değerleri 240'tan büyükse)
                if item[0] > 240 and item[1] > 240 and item[2] > 240:
                    new_data.append((255, 255, 255, 0))  # Şeffaf
                else:
                    new_data.append(item)
            
            resized_img.putdata(new_data)
            
            # Dosyayı kaydet
            filename = f'static/img/favicon-{size}x{size}.png'
            resized_img.save(filename, 'PNG')
            print(f"Oluşturuldu: {filename}")
        
        # ICO dosyası oluştur (48x48 boyutunu kullan)
        ico_img = source_img.resize((48, 48), Image.Resampling.LANCZOS)
        if ico_img.mode != 'RGBA':
            ico_img = ico_img.convert('RGBA')
        
        # Beyaz pikselleri şeffaf yap
        data = ico_img.getdata()
        new_data = []
        for item in data:
            if item[0] > 240 and item[1] > 240 and item[2] > 240:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        
        ico_img.putdata(new_data)
        ico_img.save('static/img/favicon.ico', format='ICO')
        print("Oluşturuldu: static/img/favicon.ico")
        
        # Apple Touch Icon (120x120)
        apple_icon = source_img.resize((120, 120), Image.Resampling.LANCZOS)
        if apple_icon.mode != 'RGBA':
            apple_icon = apple_icon.convert('RGBA')
        
        # Beyaz pikselleri şeffaf yap
        data = apple_icon.getdata()
        new_data = []
        for item in data:
            if item[0] > 240 and item[1] > 240 and item[2] > 240:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        
        apple_icon.putdata(new_data)
        apple_icon.save('static/img/apple-touch-icon.png', 'PNG')
        print("Oluşturuldu: static/img/apple-touch-icon.png")
        
        # SVG dosyası oluştur (120x120 boyutunu kullan)
        svg_img = source_img.resize((120, 120), Image.Resampling.LANCZOS)
        if svg_img.mode != 'RGBA':
            svg_img = svg_img.convert('RGBA')
        
        # Beyaz pikselleri şeffaf yap
        data = svg_img.getdata()
        new_data = []
        for item in data:
            if item[0] > 240 and item[1] > 240 and item[2] > 240:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        
        svg_img.putdata(new_data)
        svg_img.save('static/img/favicon.svg', format='PNG')
        print("Oluşturuldu: static/img/favicon.svg")
        
        print("Tüm şeffaf favicon dosyaları başarıyla oluşturuldu!")
        
    except Exception as e:
        print(f"Hata oluştu: {e}")

if __name__ == "__main__":
    create_transparent_favicon()

