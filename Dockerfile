# Python 3.11 base image
FROM python:3.11-slim

# Çalışma dizini
WORKDIR /app

# Sistem paketlerini güncelle ve gerekli paketleri yükle
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıklarını kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production WSGI server ekle
RUN pip install --no-cache-dir gunicorn

# Uygulama dosyalarını kopyala
COPY . .

# Uploads klasörü oluştur
RUN mkdir -p uploads/excel_imports static/uploads/users

# Port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/')" || exit 1

# Production'da Gunicorn ile çalıştır
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]







