# Faz 1: Core Modül

## Hedef
Hem desktop hem backend tarafından kullanılacak ortak `core/` modülünü yazmak. Bu modül yt-dlp'yi sarmalayan, temiz bir Python API sunan bir paket olacak.

**Bu fazın sonunda elimizde:** CLI'dan test edilebilir, herhangi bir video URL'sinden bilgi çekip indirebilen bağımsız bir Python modülü.

## Klasör Yapısı

```
video-downloader/
├── core/
│   ├── __init__.py
│   ├── downloader.py
│   ├── extractor.py
│   ├── formats.py
│   ├── exceptions.py
│   └── progress.py
├── tests/
│   └── test_core.py
├── cli_test.py              # Manuel test için
├── requirements.txt
├── .gitignore
└── README.md
```

## Bağımlılıklar (`requirements.txt`)

```
yt-dlp>=2024.1.0
```

**Not:** ffmpeg sistem bağımlılığı, pip ile gelmez. Kurulum:
- Linux: `sudo apt install ffmpeg`
- Mac: `brew install ffmpeg`
- Windows: `winget install ffmpeg` veya https://ffmpeg.org

## Görevler

### 1. `core/exceptions.py`

Özel exception sınıfları tanımla. Generic exception'lar yerine spesifik hatalar fırlatacağız ki UI/API bunları yakalayıp anlamlı mesajlar gösterebilsin.

```python
class DownloaderError(Exception):
    """Tüm downloader hatalarının base sınıfı."""
    pass

class InvalidURLError(DownloaderError):
    """URL formatı geçersiz veya desteklenmiyor."""
    pass

class VideoUnavailableError(DownloaderError):
    """Video private, silinmiş veya bölgesel kısıtlamalı."""
    pass

class NetworkError(DownloaderError):
    """Ağ bağlantısı hatası."""
    pass

class FormatNotAvailableError(DownloaderError):
    """İstenen format/kalite bu video için mevcut değil."""
    pass

class DownloadCancelledError(DownloaderError):
    """Kullanıcı indirmeyi iptal etti."""
    pass
```

### 2. `core/formats.py`

Format seçimi ve filtreleme mantığı. yt-dlp'nin verdiği format listesini sade ve kullanışlı bir yapıya çevir.

Tanımlanacak yapılar:
- `VideoFormat` dataclass: format_id, ext, resolution, fps, vcodec, filesize, has_audio, has_video
- `AudioFormat` dataclass: format_id, ext, abr (bitrate), acodec, filesize
- `parse_formats(info_dict) -> tuple[list[VideoFormat], list[AudioFormat]]`: yt-dlp info dict'inden formatları ayrıştırır
- `build_format_selector(quality: str, audio_only: bool = False) -> str`: yt-dlp'nin format selector string'ini üretir
  - `quality` örnekleri: "best", "1080p", "720p", "480p", "360p", "audio"
  - Audio için: "bestaudio/best"
  - Video için: "bestvideo[height<=720]+bestaudio/best[height<=720]"

### 3. `core/progress.py`

İlerleme bildirim sistemi. yt-dlp'nin progress hook'larını dinler ve kullanılabilir bir formata çevirir.

```python
@dataclass
class ProgressInfo:
    status: Literal["downloading", "finished", "error"]
    downloaded_bytes: int
    total_bytes: int | None
    speed: float | None  # bytes/sec
    eta: int | None      # saniye
    percent: float       # 0-100
    filename: str
    
class ProgressTracker:
    """yt-dlp progress hook'ları için callback yöneticisi."""
    
    def __init__(self, callback: Callable[[ProgressInfo], None]):
        self.callback = callback
    
    def hook(self, d: dict) -> None:
        """yt-dlp tarafından çağrılan hook fonksiyonu."""
        # d['status'] = 'downloading' | 'finished' | 'error'
        # ProgressInfo'ya çevir, callback'i çağır
```

### 4. `core/extractor.py`

Video bilgisi çekme. İndirmeden önce videonun var olduğunu, formatlarını, başlığını öğrenmek için.

```python
@dataclass
class VideoInfo:
    url: str
    title: str
    description: str | None
    duration: int | None  # saniye
    thumbnail: str | None
    uploader: str | None
    upload_date: str | None
    view_count: int | None
    video_formats: list[VideoFormat]
    audio_formats: list[AudioFormat]
    is_playlist: bool
    playlist_count: int | None
    extractor: str  # hangi site (youtube, tiktok, vb.)

def extract_info(url: str, timeout: int = 30) -> VideoInfo:
    """
    URL'den video bilgilerini çeker. İndirme yapmaz.
    
    Raises:
        InvalidURLError: URL desteklenmiyor
        VideoUnavailableError: Video erişilemez
        NetworkError: Bağlantı hatası
    """
```

**Önemli:** yt-dlp options:
- `quiet=True, no_warnings=True` (log spam'i engelle)
- `extract_flat=False` (tam bilgi al)
- `socket_timeout=timeout`

Hata yakalama:
- `yt_dlp.utils.DownloadError` mesajına göre uygun custom exception fırlat
- "Private video" → `VideoUnavailableError`
- "Unsupported URL" → `InvalidURLError`
- Network ile ilgili → `NetworkError`

### 5. `core/downloader.py`

Ana indirme sınıfı. Bu, modülün kullanıcılarının (desktop/backend) en çok etkileşeceği sınıf.

```python
@dataclass
class DownloadOptions:
    output_dir: Path
    quality: str = "best"          # "best", "1080p", "720p", vb.
    audio_only: bool = False
    audio_format: str = "mp3"      # "mp3", "m4a", "opus"
    video_format: str = "mp4"      # "mp4", "mkv", "webm"
    embed_subtitles: bool = False
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    download_subtitles: bool = False
    subtitle_languages: list[str] = field(default_factory=lambda: ["en", "tr"])
    rate_limit: str | None = None  # "1M", "500K", None
    filename_template: str = "%(title)s.%(ext)s"
    cookies_file: Path | None = None

class Downloader:
    def __init__(self, options: DownloadOptions):
        self.options = options
        self._cancel_flag = False
    
    def download(
        self,
        url: str,
        progress_callback: Callable[[ProgressInfo], None] | None = None,
    ) -> Path:
        """
        URL'yi indirir. İndirilen dosyanın yolunu döndürür.
        
        Raises:
            DownloaderError ve alt sınıfları
        """
    
    def cancel(self) -> None:
        """Aktif indirmeyi iptal eder."""
        self._cancel_flag = True
```

**yt-dlp options inşası:**
- `outtmpl` ← `filename_template` ve `output_dir`
- `format` ← `formats.build_format_selector()`
- `postprocessors` ← embed seçeneklerine göre:
  - Audio için: `FFmpegExtractAudio`
  - Thumbnail için: `EmbedThumbnail`
  - Metadata için: `FFmpegMetadata`
  - Subtitle için: `FFmpegEmbedSubtitle`
- `progress_hooks` ← `ProgressTracker.hook`
- `ratelimit` ← `rate_limit` (parse edilmiş bytes/sec)
- `cookiefile` ← `cookies_file`

**Cancel mekanizması:**
- Progress hook içinde `self._cancel_flag` kontrol et
- True ise `raise DownloadCancelledError()`

### 6. `core/__init__.py`

Public API'yi expose et:

```python
from core.downloader import Downloader, DownloadOptions
from core.extractor import extract_info, VideoInfo
from core.formats import VideoFormat, AudioFormat
from core.progress import ProgressInfo
from core.exceptions import (
    DownloaderError,
    InvalidURLError,
    VideoUnavailableError,
    NetworkError,
    FormatNotAvailableError,
    DownloadCancelledError,
)

__all__ = [
    "Downloader",
    "DownloadOptions",
    "extract_info",
    "VideoInfo",
    "VideoFormat",
    "AudioFormat",
    "ProgressInfo",
    "DownloaderError",
    "InvalidURLError",
    "VideoUnavailableError",
    "NetworkError",
    "FormatNotAvailableError",
    "DownloadCancelledError",
]
```

### 7. `cli_test.py` (Manuel Test Script)

Modülü hızlıca test etmek için CLI script:

```python
"""
Manuel test scripti.
Kullanım: python cli_test.py <url> [quality]
Örnek:    python cli_test.py https://youtu.be/dQw4w9WgXcQ 720p
"""
import sys
from pathlib import Path
from core import Downloader, DownloadOptions, extract_info, ProgressInfo

def progress_handler(info: ProgressInfo) -> None:
    if info.status == "downloading":
        print(f"\r{info.percent:.1f}% | {info.speed/1024/1024:.2f} MB/s | ETA: {info.eta}s", end="")
    elif info.status == "finished":
        print(f"\n✓ Tamamlandı: {info.filename}")

def main():
    if len(sys.argv) < 2:
        print("Kullanım: python cli_test.py <url> [quality]")
        sys.exit(1)
    
    url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else "best"
    
    print(f"Bilgi alınıyor: {url}")
    info = extract_info(url)
    print(f"Başlık: {info.title}")
    print(f"Süre: {info.duration}s")
    print(f"Kaynak: {info.extractor}")
    print(f"Mevcut format sayısı: {len(info.video_formats)}")
    
    options = DownloadOptions(
        output_dir=Path("./downloads"),
        quality=quality,
    )
    options.output_dir.mkdir(exist_ok=True)
    
    downloader = Downloader(options)
    print(f"\nİndirme başlıyor (kalite: {quality})...")
    path = downloader.download(url, progress_callback=progress_handler)
    print(f"\nDosya: {path}")

if __name__ == "__main__":
    main()
```

### 8. `tests/test_core.py`

pytest ile temel testler:

```python
import pytest
from core import extract_info, InvalidURLError, VideoUnavailableError

def test_extract_info_invalid_url():
    with pytest.raises(InvalidURLError):
        extract_info("not a url")

def test_extract_info_unsupported_site():
    with pytest.raises(InvalidURLError):
        extract_info("https://example.com/random-page")

# Gerçek YouTube URL'si ile test (network gerektirir, opsiyonel)
@pytest.mark.network
def test_extract_youtube():
    info = extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert info.title
    assert info.duration > 0
    assert len(info.video_formats) > 0
```

### 9. `.gitignore`

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
downloads/
*.log
.pytest_cache/
.vscode/
.idea/
```

### 10. `README.md`

Modülün nasıl kullanılacağına dair temel doküman:

```markdown
# Video Downloader Core

yt-dlp tabanlı video indirme modülü. Desktop ve backend uygulamaları tarafından paylaşılan ortak çekirdek.

## Kurulum

\`\`\`bash
pip install -r requirements.txt
# ffmpeg sistemde kurulu olmalı
\`\`\`

## Hızlı Kullanım

\`\`\`python
from pathlib import Path
from core import Downloader, DownloadOptions, extract_info

# Video bilgisi al
info = extract_info("https://youtu.be/...")
print(info.title, info.duration)

# İndir
options = DownloadOptions(output_dir=Path("./downloads"), quality="720p")
downloader = Downloader(options)
path = downloader.download("https://youtu.be/...")
\`\`\`

## Test

\`\`\`bash
python cli_test.py https://youtu.be/dQw4w9WgXcQ 720p
\`\`\`
```

## Kabul Kriterleri

Faz 1 tamamlandı sayılması için:

1. ✅ `pip install -r requirements.txt` hatasız çalışmalı
2. ✅ `python cli_test.py <youtube_url>` çalışmalı, video inmeli
3. ✅ `python cli_test.py <tiktok_url>` çalışmalı (yt-dlp TikTok'u destekler)
4. ✅ `python cli_test.py <instagram_url>` çalışmalı (public reel/post)
5. ✅ Geçersiz URL girildiğinde anlamlı hata mesajı
6. ✅ Audio-only indirme çalışmalı (`quality="audio"`)
7. ✅ Farklı kaliteler (`360p`, `720p`, `1080p`) çalışmalı
8. ✅ İlerleme callback'i düzgün tetikleniyor
9. ✅ `pytest tests/` çalışıyor (network testleri hariç)
10. ✅ Tüm fonksiyonlarda type hints ve docstring var

## Önemli Notlar

- **yt-dlp opsiyonları için referans:** https://github.com/yt-dlp/yt-dlp/blob/master/README.md#usage-and-options
- **YoutubeDL Python API:** https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp
- **postprocessor listesi:** https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/postprocessor/__init__.py
- Hata yakalarken `yt_dlp.utils.DownloadError`'un mesajını parse etmek gerekebilir, çünkü yt-dlp tek exception sınıfı kullanıyor.
- Test ederken **kısa videolar kullan** (Rick Roll uygundur).

## Bir Sonraki Faz

Faz 1 tamamlandığında `PHASE_2.md`'ye geç (Desktop App).
