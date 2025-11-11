# Deployment Rehberi - CRM Uygulaması

Bu rehber, CRM uygulamasını production ortamında yayınlamak için adımları içerir.

## 🚀 Deployment Seçenekleri

### 1. Self-Hosted (Kendi Sunucunuz)

#### Gereksinimler
- Python 3.8+
- MySQL/MSSQL Server
- Nginx (reverse proxy için)
- Systemd (servis yönetimi için)

#### Adımlar

1. **Production WSGI Server Kurulumu**
   ```bash
   pip install gunicorn
   ```

2. **Gunicorn ile Çalıştırma**
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

3. **Systemd Service Oluşturma**
   `/etc/systemd/system/crm-app.service` dosyası oluşturun:
   ```ini
   [Unit]
   Description=CRM Flask Application
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/path/to/CRM
   Environment="PATH=/path/to/venv/bin"
   ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

4. **Nginx Reverse Proxy**
   `/etc/nginx/sites-available/crm` dosyası oluşturun:
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /static {
           alias /path/to/CRM/static;
       }
   }
   ```

5. **HTTPS (Let's Encrypt)**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

### 2. Docker ile Deployment

#### Dockerfile Oluşturma
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

#### Docker Compose (Önerilen)
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - ./uploads:/app/uploads
    depends_on:
      - db
  
  db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: Crandyx_CRM_DB
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
```

### 3. Cloud Platform Deployment

#### Railway.app
1. GitHub repository'yi bağlayın
2. Environment variables ekleyin
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn -w 4 -b 0.0.0.0:$PORT app:app`

#### Render.com
1. GitHub repository'yi bağlayın
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn -w 4 -b 0.0.0.0:$PORT app:app`
4. Environment variables ekleyin

#### DigitalOcean App Platform
1. GitHub repository'yi bağlayın
2. Python runtime seçin
3. Build command: `pip install -r requirements.txt`
4. Run command: `gunicorn -w 4 -b 0.0.0.0:$PORT app:app`

## 📋 Production Checklist

### Güvenlik
- [ ] `.env` dosyasında güçlü `SECRET_KEY` tanımlı
- [ ] `FLASK_DEBUG=False` production'da
- [ ] HTTPS aktif (SSL sertifikası)
- [ ] `SESSION_COOKIE_SECURE=True` (HTTPS için)
- [ ] Veritabanı şifreleri şifrelenmiş
- [ ] CSRF koruması aktif ✅

### Performans
- [ ] WSGI server kullanılıyor (Gunicorn/Waitress)
- [ ] Worker sayısı ayarlanmış (CPU sayısı * 2 + 1)
- [ ] Static dosyalar Nginx'ten servis ediliyor
- [ ] Database connection pooling aktif

### Monitoring
- [ ] Loglama yapılandırılmış
- [ ] Error tracking (Sentry gibi)
- [ ] Uptime monitoring

## 🔧 Production Ayarları

### .env Dosyası (Production)
```env
SECRET_KEY=your-very-strong-secret-key-here-min-32-chars
FLASK_DEBUG=False
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
SESSION_COOKIE_SECURE=True

# Veritabanı
DATABASE_URL=mysql+pymysql://user:password@host:3306/database?charset=utf8mb4
```

## 📝 Notlar

- Development server (`app.run()`) sadece geliştirme için kullanılmalı
- Production'da mutlaka WSGI server (Gunicorn/Waitress) kullanılmalı
- Static dosyalar için Nginx kullanılması önerilir
- Veritabanı bağlantıları için connection pooling önemli
- HTTPS kullanımı zorunludur (güvenlik için)







