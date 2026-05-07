FROM python:3.12-slim

# ffmpeg kurulumu (yt-dlp için zorunlu)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bağımlılıklar
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Kod
COPY core /app/core
COPY backend /app/backend

# Çalışma kullanıcısı (security)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Volume için klasör
RUN mkdir -p /tmp/video-downloader/downloads

EXPOSE 8000

# Default command (docker-compose'da override edilecek)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
