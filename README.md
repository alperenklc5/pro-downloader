# Video Downloader Core

yt-dlp tabanlı video indirme modülü. Desktop ve backend uygulamaları tarafından paylaşılan ortak çekirdek.

## Kurulum

```bash
pip install -r requirements.txt
# ffmpeg sistemde kurulu olmalı
# Windows: winget install ffmpeg
# Linux:   sudo apt install ffmpeg
# Mac:     brew install ffmpeg
```

## Hızlı Kullanım

```python
from pathlib import Path
from core import Downloader, DownloadOptions, extract_info

# Video bilgisi al
info = extract_info("https://youtu.be/dQw4w9WgXcQ")
print(info.title, info.duration)

# İndir
options = DownloadOptions(output_dir=Path("./downloads"), quality="720p")
downloader = Downloader(options)
path = downloader.download("https://youtu.be/dQw4w9WgXcQ")
print(path)
```

## CLI ile Test

```bash
# Video indir
python cli_test.py https://youtu.be/dQw4w9WgXcQ 720p

# Sadece ses
python cli_test.py https://youtu.be/dQw4w9WgXcQ audio
```

## Testler

```bash
# Birim testleri (ağ gerekmez)
pytest tests/

# Ağ testleri dahil
pytest tests/ -m network
```

## Desteklenen Kaliteler

| Değer    | Açıklama                      |
|----------|-------------------------------|
| `best`   | Mevcut en iyi kalite          |
| `1080p`  | Full HD veya altı             |
| `720p`   | HD veya altı                  |
| `480p`   | SD veya altı                  |
| `360p`   | Düşük kalite                  |
| `audio`  | Yalnızca ses (mp3)            |

## Proje Yapısı

```
core/
├── __init__.py       # Public API
├── downloader.py     # Ana indirme sınıfı
├── extractor.py      # Video bilgisi çekme
├── formats.py        # Format seçim mantığı
├── progress.py       # İlerleme bildirimi
└── exceptions.py     # Özel hata sınıfları
```
