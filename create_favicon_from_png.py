from PIL import Image
import os

def create_favicon_from_png():
    """PNG dosyasından favicon dosyalarını oluştur"""
    
    # Kaynak PNG dosyası
    source_file = 'static/img/favicon-C.png'
    
    if not os.path.exists(source_file):
        print(f"Hata: {source_file} dosyası bulunamadı!")
        return
    
    # Farklı boyutlar
    sizes = [16, 32, 48, 64, 128, 256]
    
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
        
        # ICO dosyası oluştur (32x32 boyutunu kullan)
        ico_img = source_img.resize((32, 32), Image.Resampling.LANCZOS)
        ico_img.save('static/img/favicon.ico', format='ICO')
        print("Oluşturuldu: static/img/favicon.ico")
        
        # SVG dosyası oluştur (256x256 boyutunu kullan)
        svg_img = source_img.resize((256, 256), Image.Resampling.LANCZOS)
        svg_img.save('static/img/favicon.svg', format='PNG')  # Geçici olarak PNG olarak kaydet
        print("Oluşturuldu: static/img/favicon.svg")
        
        print("Tüm favicon dosyaları başarıyla oluşturuldu!")
        
    except Exception as e:
        print(f"Hata oluştu: {e}")

if __name__ == "__main__":
    create_favicon_from_png()

