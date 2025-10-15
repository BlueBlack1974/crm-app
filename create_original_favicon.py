from PIL import Image
import os

def create_original_favicon():
    """Logo.png dosyasından orijinal favicon oluştur"""
    
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
        
        for size in sizes:
            # Resmi yeniden boyutlandır
            resized_img = source_img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Dosyayı kaydet
            filename = f'static/img/favicon-{size}x{size}.png'
            resized_img.save(filename, 'PNG')
            print(f"Oluşturuldu: {filename}")
        
        # ICO dosyası oluştur (48x48 boyutunu kullan)
        ico_img = source_img.resize((48, 48), Image.Resampling.LANCZOS)
        ico_img.save('static/img/favicon.ico', format='ICO')
        print("Oluşturuldu: static/img/favicon.ico")
        
        # Apple Touch Icon (120x120)
        apple_icon = source_img.resize((120, 120), Image.Resampling.LANCZOS)
        apple_icon.save('static/img/apple-touch-icon.png', 'PNG')
        print("Oluşturuldu: static/img/apple-touch-icon.png")
        
        # SVG dosyası oluştur (120x120 boyutunu kullan)
        svg_img = source_img.resize((120, 120), Image.Resampling.LANCZOS)
        svg_img.save('static/img/favicon.svg', format='PNG')
        print("Oluşturuldu: static/img/favicon.svg")
        
        print("Tüm orijinal favicon dosyaları başarıyla oluşturuldu!")
        
    except Exception as e:
        print(f"Hata oluştu: {e}")

if __name__ == "__main__":
    create_original_favicon()

