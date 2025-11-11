# CSRF Koruması Kurulumu

## ✅ Yapılan Değişiklikler

1. **Flask-WTF eklendi** (`requirements.txt`)
   - Flask-WTF==1.2.1 paketi eklendi

2. **app.py'de CSRF aktifleştirildi**
   - `from flask_wtf.csrf import CSRFProtect`
   - `csrf = CSRFProtect(app)` ile aktifleştirildi

3. **Template'lerde CSRF token desteği**
   - `base.html`: Meta tag eklendi (`<meta name="csrf-token" content="{{ csrf_token() }}">`)
   - `login.html`: Form'a `{{ csrf_token() }}` eklendi
   - `sifre_degistir.html`: Form'a `{{ csrf_token() }}` eklendi
   - `ayarlar/veritabani.html`: Form'a `{{ csrf_token() }}` eklendi

4. **JavaScript Helper (base.html)**
   - Tüm fetch ve XMLHttpRequest isteklerine otomatik CSRF token ekleniyor
   - POST, PUT, PATCH, DELETE istekleri için `X-CSRFToken` header'ı otomatik ekleniyor

## 📋 Kalan Formlar

Aşağıdaki formlara da manuel olarak `{{ csrf_token() }}` eklenmesi gerekiyor:

- `templates/randevu_ekle.html`
- `templates/randevu_duzenle.html`
- `templates/ayarlar/kullanicilar.html`
- `templates/ayarlar/kullanici_duzenle.html`
- `templates/ayarlar/firmalar.html`
- `templates/ayarlar/defter.html`
- `templates/ayarlar/islemler.html`
- `templates/ayarlar/referanslar.html`
- `templates/ayarlar/email.html`
- `templates/ayarlar/sms.html`
- `templates/ayarlar/whatsapp.html`
- `templates/ayarlar/gorev_durumlar.html`
- Diğer POST formları

## 🔧 Kullanım

### HTML Formlar için:
```html
<form method="POST">
    {{ csrf_token() }}
    <!-- form alanları -->
</form>
```

### JavaScript Fetch için:
Otomatik olarak çalışır (base.html'deki helper sayesinde). Manuel eklemek isterseniz:

```javascript
fetch('/api/endpoint', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
    },
    body: JSON.stringify(data)
});
```

## ⚠️ Önemli Notlar

1. Flask-WTF, JSON istekler için header'dan (`X-CSRFToken`) veya form field'dan (`csrf_token`) token okur
2. GET istekleri CSRF korumasından muaf (varsayılan)
3. Production'da HTTPS kullanılmalı (CSRF token'ları güvenli iletişim için)
4. Eğer bazı endpoint'ler CSRF'den muaf tutulması gerekiyorsa:
   ```python
   from flask_wtf.csrf import exempt
   
   @app.route('/api/public', methods=['POST'])
   @csrf.exempt
   def public_api():
       ...
   ```

## 🧪 Test

1. Flask-WTF'nin kurulu olduğundan emin olun:
   ```bash
   pip install Flask-WTF==1.2.1
   ```

2. Uygulamayı çalıştırın ve bir POST formunu test edin
3. CSRF token olmadan POST isteği gönderilirse 400 Bad Request hatası alınmalı







