# Faz 3: FastAPI Backend

## Hedef
Android uygulamasının arkada çalışacağı REST API'yi yazmak. VPS'te 7/24 çalışacak, Android'den gelen istekleri karşılayacak, video indirip telefona servis edecek.

**Bu fazın sonunda elimizde:**
- FastAPI tabanlı çalışan bir backend
- API key ile kimlik doğrulama
- Async görev kuyruğu (Celery + Redis)
- İndirme başlat / ilerleme sorgula / dosya indir endpoint'leri
- Otomatik dosya temizleme (disk şişmesin)
- Docker Compose ile tek komutla deploy edilebilir
- Yerel makinede test edilebilir (production'a alınmadan önce)

**Önemli:** Bu fazın çıktısı **henüz VPS'e deploy edilmiyor**. Önce yerel makinede çalıştırıp Postman/curl ile test edeceğiz. VPS deploy'u **PHASE_5**'te yapacağız (Caddy, HTTPS, domain).

## Genel Mimari

```
   Android App                Backend (VPS)
       │                          │
       │ POST /api/extract        │
       ├─────────────────────────>│
       │                          │── extract_info() [core kullanır]
       │ <─────────────────────── │
       │ {title, formats, ...}    │
       │                          │
       │ POST /api/download       │
       ├─────────────────────────>│── Celery task başlat
       │ {task_id}                │   │
       │ <─────────────────────── │   │
       │                          │   ▼
       │ GET /api/status/{id}     │   download() arka planda
       ├─────────────────────────>│   │
       │ {progress: 45%, ...}     │   │
       │ <─────────────────────── │   │
       │                          │   ▼
       │ GET /api/file/{id}       │   ✓ Tamamlandı
       ├─────────────────────────>│
       │ <══════ video.mp4 ══════ │── Stream dosya
       │                          │
                                  │── Cron: 24 saatten eski dosyaları sil
```

## Klasör Yapısı

```
video-downloader/
├── core/                    # Faz 1'den, dokunmuyoruz
│   └── ...
├── desktop/                 # Faz 2'den, dokunmuyoruz
│   └── ...
├── backend/                 # ← Bu fazda oluşturulacak
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Backend ayarları (env-based)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py        # Endpoint tanımları
│   │   ├── auth.py          # API key middleware
│   │   ├── schemas.py       # Pydantic models (request/response)
│   │   └── exceptions.py    # API-level error handling
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py    # Celery instance
│   │   └── download_task.py # Async download görevi
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── task_store.py    # Görev metadata yönetimi (Redis)
│   │   └── file_manager.py  # Dosya yaşam döngüsü
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── cleanup.py       # Eski dosyaları silme
│   │   └── logging_setup.py # Yapılandırılmış logging
│   ├── tests/
│   │   ├── test_api.py
│   │   └── test_tasks.py
│   ├── .env.example         # Yapılandırma örneği
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── README.md
└── ...
```

## Bağımlılıklar (`backend/requirements.txt`)

```
# Core (zaten var)
yt-dlp>=2024.1.0

# Web framework
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
pydantic>=2.6.0
pydantic-settings>=2.2.0

# Async görev kuyruğu
celery>=5.3.0
redis>=5.0.0

# HTTP client (health check, vb.)
httpx>=0.27.0

# Logging & monitoring
structlog>=24.1.0

# Test
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

## Görev 1: `backend/config.py` — Ayarlar

Tüm yapılandırma `.env` dosyasından okunacak. Hardcoded değer yok.

```python
"""Backend yapılandırması.

Tüm ayarlar environment variable'lardan okunur.
Geliştirme için .env dosyası kullanılır.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Uygulama ayarları."""
    
    # === API ===
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1  # Production'da 2-4
    
    # === Auth ===
    # API key'ler virgülle ayrılmış. Production'da ortam değişkeninden gelir.
    api_keys: str = "dev-key-change-me-in-production"
    
    # === Storage ===
    # İndirilen dosyaların kaydedildiği yer
    download_dir: Path = Path("/tmp/video-downloader/downloads")
    # Maksimum dosya saklama süresi (saat)
    file_retention_hours: int = 24
    # Maksimum toplam dosya boyutu (GB) — bu aşılırsa eski dosyalar silinir
    max_storage_gb: int = 50
    
    # === Celery / Redis ===
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    
    # === Limits ===
    # Eşzamanlı maksimum indirme sayısı
    max_concurrent_downloads: int = 3
    # Tek dosya için maksimum boyut (MB)
    max_file_size_mb: int = 2048  # 2 GB
    # Tek dosya için maksimum süre (saniye)
    max_video_duration_seconds: int = 7200  # 2 saat
    # İndirme hızı limiti (örn: "5M" = 5MB/s, None = limitsiz)
    download_rate_limit: str | None = None
    
    # === Logging ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    
    # === Cookies (Backend'de tarayıcı yok!) ===
    # Manuel cookies.txt dosyası yolu (varsa, login gerekli sitelerde kullanılır)
    cookies_file: Path | None = None
    
    # === CORS ===
    # Android'in bağlanabilmesi için. Production'da specific origin'ler
    cors_origins: str = "*"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    def get_api_keys(self) -> set[str]:
        """API key listesini set olarak döndür."""
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}
    
    def get_cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# Singleton
settings = Settings()
```

## Görev 2: `backend/.env.example`

Geliştirici için örnek `.env` dosyası:

```bash
# === API ===
API_HOST=0.0.0.0
API_PORT=8000

# === Auth ===
# Production'da bu değiştirilmeli! Birden fazla key virgülle ayrılır.
API_KEYS=my-secret-android-key,my-secret-test-key

# === Storage ===
DOWNLOAD_DIR=/tmp/video-downloader/downloads
FILE_RETENTION_HOURS=24
MAX_STORAGE_GB=50

# === Redis ===
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# === Limits ===
MAX_CONCURRENT_DOWNLOADS=3
MAX_FILE_SIZE_MB=2048
MAX_VIDEO_DURATION_SECONDS=7200
DOWNLOAD_RATE_LIMIT=

# === Logging ===
LOG_LEVEL=INFO

# === Cookies ===
# Login gerekli siteler için manuel cookies.txt yolu
# COOKIES_FILE=/var/lib/video-downloader/cookies.txt

# === CORS ===
CORS_ORIGINS=*
```

## Görev 3: `backend/api/schemas.py` — Pydantic Modelleri

Request/response veri yapıları. FastAPI bunlarla otomatik validation ve dokümantasyon yapar.

```python
"""API request/response şemaları."""
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from typing import Literal


# === Request Schemas ===

class ExtractRequest(BaseModel):
    """Video bilgisi çekme isteği."""
    url: str = Field(..., description="Video URL'si", examples=["https://youtu.be/dQw4w9WgXcQ"])


class DownloadRequest(BaseModel):
    """İndirme başlatma isteği."""
    url: str = Field(..., description="Video URL'si")
    quality: str = Field("720p", description="Kalite: best, 1080p, 720p, 480p, 360p, audio")
    audio_only: bool = Field(False, description="Sadece ses indir")
    audio_format: Literal["mp3", "m4a", "opus"] = Field("mp3")
    video_format: Literal["mp4", "mkv", "webm"] = Field("mp4")
    embed_thumbnail: bool = Field(True)
    embed_metadata: bool = Field(True)
    embed_subtitles: bool = Field(False)
    subtitle_languages: list[str] = Field(default_factory=lambda: ["en", "tr"])


# === Response Schemas ===

class FormatInfo(BaseModel):
    """Tek bir format bilgisi."""
    format_id: str
    ext: str
    resolution: str | None = None
    fps: int | None = None
    filesize: int | None = None
    has_audio: bool
    has_video: bool


class VideoInfoResponse(BaseModel):
    """Video bilgisi."""
    url: str
    title: str
    description: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    uploader: str | None = None
    upload_date: str | None = None
    view_count: int | None = None
    extractor: str
    is_playlist: bool = False
    playlist_count: int | None = None
    video_formats: list[FormatInfo] = Field(default_factory=list)
    audio_formats: list[FormatInfo] = Field(default_factory=list)


class DownloadStartResponse(BaseModel):
    """İndirme başlatma yanıtı."""
    task_id: str = Field(..., description="Görev takibi için ID")
    status: str = "queued"
    message: str = "İndirme kuyruğa alındı"


class TaskProgressResponse(BaseModel):
    """Görev ilerleme bilgisi."""
    task_id: str
    status: Literal["queued", "downloading", "completed", "failed", "cancelled"]
    progress_percent: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    speed_bytes_per_sec: float | None = None
    eta_seconds: int | None = None
    title: str | None = None
    filename: str | None = None
    file_size_bytes: int | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    download_url: str | None = None  # Tamamlandığında dolu


class ErrorResponse(BaseModel):
    """Standart hata yanıtı."""
    error: str
    detail: str
    category: str = "generic"


class HealthResponse(BaseModel):
    """Health check yanıtı."""
    status: Literal["ok", "degraded", "error"]
    version: str
    yt_dlp_version: str
    redis_connected: bool
    celery_workers: int
    disk_free_gb: float
```

## Görev 4: `backend/api/auth.py` — API Key Auth

Her istekte `Authorization: Bearer <key>` header'ı kontrol edilecek.

```python
"""API key tabanlı kimlik doğrulama."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import settings


security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """API key'i doğrula. Geçersiz ise 401 fırlat.
    
    Returns: Geçerli API key
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header eksik. 'Bearer <api_key>' kullanın.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    valid_keys = settings.get_api_keys()
    if credentials.credentials not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return credentials.credentials
```

## Görev 5: `backend/storage/task_store.py` — Görev Metadata

İndirme görevlerinin durumunu Redis'te tutuyoruz. Celery'nin kendi result backend'i var ama biz **kendi metadata** yapımızı tutmak istiyoruz (progress yüzdesi, hız, ETA gibi şeyler için).

```python
"""Görev metadata yönetimi (Redis tabanlı)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import redis

from backend.config import settings


# Redis client (singleton)
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


# Key prefix'leri
TASK_KEY_PREFIX = "vd:task:"
TASK_TTL_SECONDS = settings.file_retention_hours * 3600 + 3600  # Dosya süresinden 1 saat fazla


class TaskStore:
    """Görev metadata'sını Redis'te saklayan class."""
    
    @staticmethod
    def _key(task_id: str) -> str:
        return f"{TASK_KEY_PREFIX}{task_id}"
    
    @classmethod
    def create(cls, task_id: str, url: str, options: dict) -> dict:
        """Yeni görev oluştur."""
        data = {
            "task_id": task_id,
            "status": "queued",
            "url": url,
            "options": options,
            "progress_percent": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": None,
            "speed_bytes_per_sec": None,
            "eta_seconds": None,
            "title": None,
            "filename": None,
            "file_size_bytes": None,
            "error_message": None,
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }
        cls._save(task_id, data)
        return data
    
    @classmethod
    def get(cls, task_id: str) -> dict | None:
        """Görev bilgisini al."""
        raw = get_redis().get(cls._key(task_id))
        if raw is None:
            return None
        return json.loads(raw)
    
    @classmethod
    def update(cls, task_id: str, **updates: Any) -> dict | None:
        """Görev bilgisini güncelle (kısmi update)."""
        data = cls.get(task_id)
        if data is None:
            return None
        data.update(updates)
        cls._save(task_id, data)
        return data
    
    @classmethod
    def delete(cls, task_id: str) -> bool:
        """Görevi sil."""
        return bool(get_redis().delete(cls._key(task_id)))
    
    @classmethod
    def _save(cls, task_id: str, data: dict) -> None:
        """Internal: Redis'e yaz."""
        get_redis().setex(
            cls._key(task_id),
            TASK_TTL_SECONDS,
            json.dumps(data, default=str),
        )
    
    @classmethod
    def list_active(cls) -> list[dict]:
        """Aktif (henüz tamamlanmamış) görevleri listele."""
        keys = get_redis().keys(f"{TASK_KEY_PREFIX}*")
        results = []
        for key in keys:
            raw = get_redis().get(key)
            if raw:
                data = json.loads(raw)
                if data.get("status") in ("queued", "downloading"):
                    results.append(data)
        return results
```

## Görev 6: `backend/storage/file_manager.py` — Dosya Yönetimi

İndirilen dosyaların yaşam döngüsü.

```python
"""İndirilen dosya yaşam döngüsü."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from backend.config import settings


class FileManager:
    """Dosya saklama ve temizleme."""
    
    @classmethod
    def get_download_dir(cls) -> Path:
        """İndirme dizinini döndür, yoksa oluştur."""
        path = settings.download_dir
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @classmethod
    def get_task_dir(cls, task_id: str) -> Path:
        """Belirli bir görev için izole klasör (dosya çakışması olmasın)."""
        path = cls.get_download_dir() / task_id
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @classmethod
    def get_task_file(cls, task_id: str) -> Path | None:
        """Görev klasöründeki dosyayı bul (genelde tek dosya olur)."""
        task_dir = cls.get_task_dir(task_id)
        files = [f for f in task_dir.iterdir() if f.is_file()]
        if not files:
            return None
        # En büyük dosyayı al (video, partial dosyaları değil)
        return max(files, key=lambda f: f.stat().st_size)
    
    @classmethod
    def cleanup_task(cls, task_id: str) -> None:
        """Bir görevin tüm dosyalarını sil."""
        task_dir = cls.get_download_dir() / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)
    
    @classmethod
    def cleanup_old_files(cls) -> dict:
        """Eski dosyaları temizle. Çağrılma sıklığı: cron ile saatte bir.
        
        Strateji:
        1. file_retention_hours'tan eski dosyaları sil
        2. Toplam boyut max_storage_gb'i aşıyorsa, en eski dosyalardan başlayarak sil
        
        Returns: İstatistik dict
        """
        download_dir = cls.get_download_dir()
        if not download_dir.exists():
            return {"deleted_count": 0, "freed_bytes": 0}
        
        cutoff_time = datetime.now() - timedelta(hours=settings.file_retention_hours)
        deleted_count = 0
        freed_bytes = 0
        
        # 1) Yaş bazlı temizlik
        for task_dir in download_dir.iterdir():
            if not task_dir.is_dir():
                continue
            try:
                mtime = datetime.fromtimestamp(task_dir.stat().st_mtime)
                if mtime < cutoff_time:
                    size = sum(f.stat().st_size for f in task_dir.rglob("*") if f.is_file())
                    shutil.rmtree(task_dir, ignore_errors=True)
                    deleted_count += 1
                    freed_bytes += size
            except OSError:
                continue
        
        # 2) Boyut bazlı temizlik (eskiden yeniye)
        max_bytes = settings.max_storage_gb * 1024 * 1024 * 1024
        total_size = sum(
            f.stat().st_size for f in download_dir.rglob("*") if f.is_file()
        )
        
        if total_size > max_bytes:
            task_dirs = sorted(
                [d for d in download_dir.iterdir() if d.is_dir()],
                key=lambda d: d.stat().st_mtime,
            )
            for task_dir in task_dirs:
                if total_size <= max_bytes:
                    break
                try:
                    size = sum(f.stat().st_size for f in task_dir.rglob("*") if f.is_file())
                    shutil.rmtree(task_dir, ignore_errors=True)
                    total_size -= size
                    deleted_count += 1
                    freed_bytes += size
                except OSError:
                    continue
        
        return {
            "deleted_count": deleted_count,
            "freed_bytes": freed_bytes,
            "remaining_size_bytes": total_size,
        }
    
    @classmethod
    def get_disk_usage(cls) -> dict:
        """Disk kullanımı bilgisi."""
        download_dir = cls.get_download_dir()
        usage = shutil.disk_usage(str(download_dir))
        
        total_used = 0
        if download_dir.exists():
            total_used = sum(
                f.stat().st_size for f in download_dir.rglob("*") if f.is_file()
            )
        
        return {
            "downloads_used_bytes": total_used,
            "disk_free_bytes": usage.free,
            "disk_total_bytes": usage.total,
        }
```

## Görev 7: `backend/tasks/celery_app.py` — Celery Setup

```python
"""Celery uygulama yapılandırması."""
from celery import Celery

from backend.config import settings


celery_app = Celery(
    "video_downloader",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.tasks.download_task"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Concurrency
    worker_concurrency=settings.max_concurrent_downloads,
    worker_prefetch_multiplier=1,
    
    # Görev timeout (uzun videolar için 1 saat)
    task_soft_time_limit=3600,
    task_time_limit=3900,
    
    # Sonuçlar 24 saat sonra silinsin
    result_expires=86400,
    
    # Periyodik görevler
    beat_schedule={
        "cleanup-old-files": {
            "task": "backend.tasks.download_task.cleanup_task",
            "schedule": 3600.0,  # Her saat
        },
    },
)
```

## Görev 8: `backend/tasks/download_task.py` — Async Download

```python
"""Asenkron indirme görevi."""
from pathlib import Path
from datetime import datetime
import logging

from backend.tasks.celery_app import celery_app
from backend.storage.task_store import TaskStore
from backend.storage.file_manager import FileManager
from backend.config import settings
from core import Downloader, DownloadOptions, ProgressInfo
from core.auth import CookieConfig
from core.exceptions import DownloaderError, AuthenticationRequiredError
from core.error_messages import humanize_error


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="backend.tasks.download_task.download_video")
def download_video(self, task_id: str, url: str, options_dict: dict) -> dict:
    """Video indirme görevi.
    
    Args:
        task_id: Görev ID'si (TaskStore key)
        url: Video URL'si
        options_dict: DownloadRequest'ten gelen opsiyonlar
    
    Returns:
        Sonuç dict (TaskStore'da da güncel tutulur)
    """
    logger.info(f"İndirme başlıyor: task_id={task_id}, url={url}")
    
    # Görev metadata güncelle
    TaskStore.update(task_id, status="downloading")
    
    # Cookie config (sadece manuel dosya, browser yok)
    cookies = CookieConfig()
    if settings.cookies_file and settings.cookies_file.exists():
        cookies = CookieConfig(
            mode="file",
            file_path=settings.cookies_file,
        )
    
    # Download options
    options = DownloadOptions(
        output_dir=FileManager.get_task_dir(task_id),
        quality=options_dict.get("quality", "720p"),
        audio_only=options_dict.get("audio_only", False),
        audio_format=options_dict.get("audio_format", "mp3"),
        video_format=options_dict.get("video_format", "mp4"),
        embed_thumbnail=options_dict.get("embed_thumbnail", True),
        embed_metadata=options_dict.get("embed_metadata", True),
        embed_subtitles=options_dict.get("embed_subtitles", False),
        subtitle_languages=options_dict.get("subtitle_languages", ["en", "tr"]),
        rate_limit=settings.download_rate_limit,
        cookies=cookies,
    )
    
    # Progress callback (Redis'e yaz)
    def progress_callback(info: ProgressInfo) -> None:
        TaskStore.update(
            task_id,
            progress_percent=info.percent,
            downloaded_bytes=info.downloaded_bytes,
            total_bytes=info.total_bytes,
            speed_bytes_per_sec=info.speed,
            eta_seconds=info.eta,
            filename=info.filename,
        )
    
    try:
        downloader = Downloader(options)
        downloaded_path = downloader.download(url, progress_callback=progress_callback)
        
        # Başarılı
        file_size = downloaded_path.stat().st_size
        TaskStore.update(
            task_id,
            status="completed",
            progress_percent=100.0,
            filename=downloaded_path.name,
            file_size_bytes=file_size,
            completed_at=datetime.now().isoformat(),
        )
        
        logger.info(f"İndirme tamamlandı: task_id={task_id}, size={file_size}")
        return {"success": True, "task_id": task_id, "filename": downloaded_path.name}
        
    except DownloaderError as e:
        friendly = humanize_error(str(e))
        error_msg = f"{friendly.title}: {friendly.message}"
        TaskStore.update(
            task_id,
            status="failed",
            error_message=error_msg,
            completed_at=datetime.now().isoformat(),
        )
        FileManager.cleanup_task(task_id)
        logger.error(f"İndirme başarısız: task_id={task_id}, error={error_msg}")
        return {"success": False, "task_id": task_id, "error": error_msg}
    
    except Exception as e:
        TaskStore.update(
            task_id,
            status="failed",
            error_message=f"Beklenmeyen hata: {e}",
            completed_at=datetime.now().isoformat(),
        )
        FileManager.cleanup_task(task_id)
        logger.exception(f"İndirme'de beklenmeyen hata: task_id={task_id}")
        return {"success": False, "task_id": task_id, "error": str(e)}


@celery_app.task(name="backend.tasks.download_task.cleanup_task")
def cleanup_task() -> dict:
    """Periyodik dosya temizleme."""
    result = FileManager.cleanup_old_files()
    logger.info(f"Cleanup tamamlandı: {result}")
    return result
```

## Görev 9: `backend/api/routes.py` — Endpoint'ler

```python
"""API endpoint tanımları."""
import uuid
from pathlib import Path
import logging

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse

from backend.api.auth import verify_api_key
from backend.api.schemas import (
    ExtractRequest, DownloadRequest,
    VideoInfoResponse, FormatInfo,
    DownloadStartResponse, TaskProgressResponse,
    ErrorResponse, HealthResponse,
)
from backend.config import settings
from backend.storage.task_store import TaskStore
from backend.storage.file_manager import FileManager
from backend.tasks.celery_app import celery_app
from backend.tasks.download_task import download_video
from core import extract_info
from core.auth import CookieConfig
from core.exceptions import (
    DownloaderError, AuthenticationRequiredError,
    InvalidURLError, VideoUnavailableError, NetworkError,
)
from core.error_messages import humanize_error


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])


# === Health ===

@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Sistem sağlık kontrolü."""
    import yt_dlp
    import redis
    
    # Redis kontrolü
    redis_ok = False
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        redis_ok = True
    except Exception:
        pass
    
    # Celery worker sayısı
    worker_count = 0
    try:
        inspect = celery_app.control.inspect(timeout=2)
        active = inspect.active()
        if active:
            worker_count = len(active)
    except Exception:
        pass
    
    # Disk
    usage = FileManager.get_disk_usage()
    disk_free_gb = usage["disk_free_bytes"] / (1024 ** 3)
    
    overall = "ok" if (redis_ok and worker_count > 0) else "degraded"
    
    return HealthResponse(
        status=overall,
        version="1.0.0",
        yt_dlp_version=yt_dlp.version.__version__,
        redis_connected=redis_ok,
        celery_workers=worker_count,
        disk_free_gb=round(disk_free_gb, 2),
    )


# === Extract Info ===

@router.post(
    "/extract",
    response_model=VideoInfoResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def extract(
    req: ExtractRequest,
    api_key: str = Depends(verify_api_key),
):
    """Video bilgisi çek (indirmeden önce kullanılır)."""
    cookies = CookieConfig()
    if settings.cookies_file and settings.cookies_file.exists():
        cookies = CookieConfig(mode="file", file_path=settings.cookies_file)
    
    try:
        info = extract_info(req.url, cookies=cookies)
        
        return VideoInfoResponse(
            url=info.url,
            title=info.title,
            description=info.description,
            duration=info.duration,
            thumbnail=info.thumbnail,
            uploader=info.uploader,
            upload_date=info.upload_date,
            view_count=info.view_count,
            extractor=info.extractor,
            is_playlist=info.is_playlist,
            playlist_count=info.playlist_count,
            video_formats=[
                FormatInfo(
                    format_id=f.format_id,
                    ext=f.ext,
                    resolution=f.resolution,
                    fps=f.fps,
                    filesize=f.filesize,
                    has_audio=f.has_audio,
                    has_video=f.has_video,
                ) for f in info.video_formats
            ],
            audio_formats=[
                FormatInfo(
                    format_id=f.format_id,
                    ext=f.ext,
                    resolution=None,
                    fps=None,
                    filesize=f.filesize,
                    has_audio=True,
                    has_video=False,
                ) for f in info.audio_formats
            ],
        )
    except InvalidURLError:
        raise HTTPException(status_code=400, detail="Geçersiz veya desteklenmeyen URL.")
    except VideoUnavailableError as e:
        raise HTTPException(status_code=404, detail=f"Video erişilemez: {e}")
    except AuthenticationRequiredError as e:
        raise HTTPException(status_code=401, detail=f"Login gerekli: {e}")
    except NetworkError as e:
        raise HTTPException(status_code=502, detail=f"Ağ hatası: {e}")
    except DownloaderError as e:
        friendly = humanize_error(str(e))
        raise HTTPException(status_code=500, detail=friendly.message)


# === Download Start ===

@router.post(
    "/download",
    response_model=DownloadStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_download(
    req: DownloadRequest,
    api_key: str = Depends(verify_api_key),
):
    """İndirme görevi başlat. Asenkron — task_id döner."""
    task_id = uuid.uuid4().hex
    
    # Önce video info çek (validation), beklemeden
    # Bu adım atılabilir ama erken hata yakalama için iyi
    cookies = CookieConfig()
    if settings.cookies_file and settings.cookies_file.exists():
        cookies = CookieConfig(mode="file", file_path=settings.cookies_file)
    
    try:
        info = extract_info(req.url, cookies=cookies, timeout=15)
        
        # Süre limiti kontrolü
        if info.duration and info.duration > settings.max_video_duration_seconds:
            raise HTTPException(
                status_code=400,
                detail=f"Video çok uzun ({info.duration}s). Max: {settings.max_video_duration_seconds}s",
            )
        
        title = info.title
    except HTTPException:
        raise
    except (InvalidURLError, VideoUnavailableError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DownloaderError as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Görev oluştur
    TaskStore.create(
        task_id=task_id,
        url=req.url,
        options=req.model_dump(),
    )
    TaskStore.update(task_id, title=title)
    
    # Celery'e at
    download_video.apply_async(
        args=[task_id, req.url, req.model_dump()],
        task_id=task_id,
    )
    
    logger.info(f"Görev kuyruğa alındı: task_id={task_id}, url={req.url}")
    
    return DownloadStartResponse(
        task_id=task_id,
        status="queued",
        message=f"İndirme kuyruğa alındı: {title}",
    )


# === Task Status ===

@router.get(
    "/status/{task_id}",
    response_model=TaskProgressResponse,
)
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Görev durumunu sorgula."""
    data = TaskStore.get(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")
    
    download_url = None
    if data["status"] == "completed":
        download_url = f"/api/file/{task_id}"
    
    return TaskProgressResponse(
        task_id=data["task_id"],
        status=data["status"],
        progress_percent=data.get("progress_percent", 0.0),
        downloaded_bytes=data.get("downloaded_bytes", 0),
        total_bytes=data.get("total_bytes"),
        speed_bytes_per_sec=data.get("speed_bytes_per_sec"),
        eta_seconds=data.get("eta_seconds"),
        title=data.get("title"),
        filename=data.get("filename"),
        file_size_bytes=data.get("file_size_bytes"),
        error_message=data.get("error_message"),
        created_at=data["created_at"],
        completed_at=data.get("completed_at"),
        download_url=download_url,
    )


# === File Download ===

@router.get("/file/{task_id}")
async def download_file(
    task_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Tamamlanmış görevin dosyasını indir."""
    data = TaskStore.get(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")
    
    if data["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Görev henüz tamamlanmadı (status={data['status']}).",
        )
    
    file_path = FileManager.get_task_file(task_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı (silinmiş olabilir).")
    
    # Dosyayı stream et
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


# === Cancel ===

@router.delete("/task/{task_id}")
async def cancel_task(
    task_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Görevi iptal et ve dosyalarını sil."""
    data = TaskStore.get(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")
    
    # Celery'de revoke
    celery_app.control.revoke(task_id, terminate=True)
    
    # Status güncelle
    TaskStore.update(task_id, status="cancelled")
    
    # Dosyaları sil
    FileManager.cleanup_task(task_id)
    
    return {"task_id": task_id, "status": "cancelled"}


# === List Tasks (debug için) ===

@router.get("/tasks/active")
async def list_active_tasks(api_key: str = Depends(verify_api_key)):
    """Aktif görevleri listele."""
    return TaskStore.list_active()
```

## Görev 10: `backend/main.py` — FastAPI App

```python
"""FastAPI uygulaması — entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api.routes import router
from backend.utils.logging_setup import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup ve shutdown hook'ları."""
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("Video Downloader Backend başlıyor")
    logger.info(f"Download dir: {settings.download_dir}")
    logger.info(f"Redis: {settings.redis_url}")
    logger.info(f"Max concurrent: {settings.max_concurrent_downloads}")
    logger.info("=" * 50)
    
    # Download dir oluştur
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    
    yield
    
    logger.info("Backend kapanıyor")


app = FastAPI(
    title="Video Downloader API",
    description="Çok platformlu video indirme sistemi (1800+ site desteği)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'lar
app.include_router(router)


@app.get("/")
async def root():
    return {
        "name": "Video Downloader API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
```

## Görev 11: `backend/utils/logging_setup.py`

```python
"""Logging yapılandırması."""
import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Tüm loglar için ortak yapılandırma."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Eski handler'ları temizle
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)
    
    # Çok gürültülü logger'ları sustur
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)
```

## Görev 12: `backend/Dockerfile`

```dockerfile
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
```

## Görev 13: `backend/docker-compose.yml`

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
  
  api:
    build:
      context: ..
      dockerfile: backend/Dockerfile
    restart: unless-stopped
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - downloads_data:/tmp/video-downloader/downloads
    depends_on:
      redis:
        condition: service_healthy
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000
  
  worker:
    build:
      context: ..
      dockerfile: backend/Dockerfile
    restart: unless-stopped
    env_file: .env
    volumes:
      - downloads_data:/tmp/video-downloader/downloads
    depends_on:
      redis:
        condition: service_healthy
    command: celery -A backend.tasks.celery_app worker --loglevel=info --concurrency=3
  
  beat:
    build:
      context: ..
      dockerfile: backend/Dockerfile
    restart: unless-stopped
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
    command: celery -A backend.tasks.celery_app beat --loglevel=info

volumes:
  redis_data:
  downloads_data:
```

## Görev 14: `backend/README.md`

```markdown
# Video Downloader Backend

Android uygulaması için REST API + asenkron indirme sistemi.

## Yerel Geliştirme

### Gereksinimler
- Python 3.12+
- Redis (Docker veya yerel)
- ffmpeg

### Kurulum
\`\`\`bash
# Bağımlılıklar
pip install -r requirements.txt

# Environment
cp .env.example .env
# .env dosyasını düzenle, API_KEYS değiştir

# Redis (Docker ile)
docker run -d -p 6379:6379 --name vd-redis redis:7-alpine
\`\`\`

### Çalıştırma (3 ayrı terminal)

Terminal 1 — API:
\`\`\`bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
\`\`\`

Terminal 2 — Worker:
\`\`\`bash
celery -A backend.tasks.celery_app worker --loglevel=info --concurrency=3
\`\`\`

Terminal 3 — Beat (cleanup cron):
\`\`\`bash
celery -A backend.tasks.celery_app beat --loglevel=info
\`\`\`

### API Dokümantasyon
Tarayıcıda aç: http://localhost:8000/docs

### Hızlı Test
\`\`\`bash
# Health check
curl http://localhost:8000/api/health

# Video bilgisi
curl -X POST http://localhost:8000/api/extract \\
  -H "Authorization: Bearer dev-key-change-me-in-production" \\
  -H "Content-Type: application/json" \\
  -d '{"url": "https://youtu.be/jNQXAC9IVRw"}'

# İndirme başlat
curl -X POST http://localhost:8000/api/download \\
  -H "Authorization: Bearer dev-key-change-me-in-production" \\
  -H "Content-Type: application/json" \\
  -d '{"url": "https://youtu.be/jNQXAC9IVRw", "quality": "360p"}'

# Status sorgula
curl http://localhost:8000/api/status/<task_id> \\
  -H "Authorization: Bearer dev-key-change-me-in-production"

# Dosyayı indir
curl -O -J http://localhost:8000/api/file/<task_id> \\
  -H "Authorization: Bearer dev-key-change-me-in-production"
\`\`\`

## Docker ile Çalıştırma

\`\`\`bash
docker-compose up --build
\`\`\`

Tüm servisler ayağa kalkar (api + worker + beat + redis).

## Dosya Saklama Politikası
- İndirilen dosyalar `FILE_RETENTION_HOURS` (default 24) saat saklanır
- Toplam boyut `MAX_STORAGE_GB` (default 50GB) aşarsa eski dosyalar silinir
- Otomatik cleanup saatte bir çalışır (Celery Beat)
```

## Görev 15: `backend/tests/test_api.py`

```python
"""API endpoint testleri."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer dev-key-change-me-in-production"}


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "name" in r.json()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "yt_dlp_version" in data


def test_extract_no_auth(client):
    r = client.post("/api/extract", json={"url": "https://youtu.be/test"})
    assert r.status_code == 401


def test_extract_invalid_key(client):
    r = client.post(
        "/api/extract",
        json={"url": "https://youtu.be/test"},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert r.status_code == 401


def test_extract_bad_url(client, auth_headers):
    r = client.post(
        "/api/extract",
        json={"url": "not a url"},
        headers=auth_headers,
    )
    assert r.status_code in (400, 500)


@pytest.mark.network
def test_extract_youtube(client, auth_headers):
    r = client.post(
        "/api/extract",
        json={"url": "https://youtu.be/jNQXAC9IVRw"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["title"]
    assert data["duration"] > 0
```

## Kabul Kriterleri

1. ✅ `uvicorn backend.main:app --reload` çalışıyor, http://localhost:8000/docs açılıyor
2. ✅ Redis bağlantısı kuruluyor (`/api/health` redis_connected=True)
3. ✅ Celery worker çalışıyor (`/api/health` celery_workers > 0)
4. ✅ `POST /api/extract` ile YouTube videosu bilgisi geliyor
5. ✅ Auth eksik/yanlışsa 401 dönüyor
6. ✅ `POST /api/download` 202 dönüyor, task_id veriyor
7. ✅ `GET /api/status/{task_id}` progress takip edilebiliyor
8. ✅ İndirme bittiğinde `GET /api/file/{task_id}` dosyayı veriyor
9. ✅ `DELETE /api/task/{task_id}` görev iptal ediyor, dosya siliniyor
10. ✅ Docker compose ile tüm sistem ayağa kalkıyor
11. ✅ Cleanup task çalışıyor (eski dosyalar siliniyor)
12. ✅ Cookie file ile login gerekli sitelerden indirme yapılabiliyor
13. ✅ Aynı anda 3 paralel indirme çalışabiliyor

## Test Senaryoları

**Senaryo 1 — Basic Flow:**
```bash
# 1. Bilgi al
TASK=$(curl -s -X POST http://localhost:8000/api/download \
  -H "Authorization: Bearer dev-key-change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/jNQXAC9IVRw", "quality": "360p"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['task_id'])")

echo "Task: $TASK"

# 2. Status sorgula (polling)
while true; do
  STATUS=$(curl -s http://localhost:8000/api/status/$TASK \
    -H "Authorization: Bearer dev-key-change-me-in-production" \
    | python -c "import json,sys; d=json.load(sys.stdin); print(d['status'], d['progress_percent'])")
  echo "$STATUS"
  if [[ "$STATUS" == "completed"* ]] || [[ "$STATUS" == "failed"* ]]; then break; fi
  sleep 2
done

# 3. Dosyayı indir
curl -O -J http://localhost:8000/api/file/$TASK \
  -H "Authorization: Bearer dev-key-change-me-in-production"
```

**Senaryo 2 — Concurrent Downloads:**
3-4 indirmeyi paralel başlat, hepsi `downloading` statüsünde olmalı, sırayla `completed`'e geçmeli.

**Senaryo 3 — Cleanup:**
- `FILE_RETENTION_HOURS=0` ile çalıştır (test için)
- İndirme yap, dosya gelsin
- 1 dakika bekle, cleanup_task tetiklensin
- `/api/file/{task_id}` 404 dönmeli

## Önemli Notlar

**Cookies Backend'de:**
Backend'de tarayıcı yok. Sadece **manuel cookies.txt** desteği var. VPS'e cookies.txt dosyasını manuel upload edersin (örn: `/var/lib/video-downloader/cookies.txt`), `.env`'de `COOKIES_FILE=...` ile path veririz.

PHASE_4'te Android uygulamasında **WebView ile login** yapıp cookie'leri backend'e gönderme özelliğini ekleyeceğiz. Bu daha kullanıcı dostu olacak.

**Streaming Response:**
`FileResponse` küçük dosyalar için tamam ama 1GB+ videolar için `StreamingResponse` daha verimli. İlerde optimize edilebilir, şimdilik FileResponse yeterli.

**Rate Limiting:**
Production'da API rate limit eklenmeli (DDoS koruması). `slowapi` kütüphanesi kolay. PHASE_5'te ekleriz.

**Security Notes:**
- `API_KEYS` mutlaka değiştirilmeli production'da
- `CORS_ORIGINS=*` development için, production'da specific origin'ler
- `dev-key-change-me-in-production` adından da belli, **kullanma!**

**Disk Yönetimi:**
8GB RAM'in olsa da disk önemli. `MAX_STORAGE_GB=50` makul. VPS'inde 50GB+ boş alan varsa rahat çalışır. Yetmezse `FILE_RETENTION_HOURS=6` gibi kısaltabilirsin.

## Bir Sonraki Adım

Faz 3 başarıyla tamamlandığında:
- Backend yerel makinede çalışıyor ✓
- API testleri geçiyor ✓
- Docker compose ile bütün sistem ayağa kalkıyor ✓

Sıradaki: **PHASE_4.md** — Android Uygulaması (Kotlin + Jetpack Compose)
- Backend'in URL'sini ayarlardan al
- API key kaydet
- Paylaş menüsünden URL al (TikTok, YouTube vs. paylaş → uygulamamıza düşsün)
- İndirme listesi, ilerleme bildirimi
- Telefonun Downloads/ klasörüne kaydet
