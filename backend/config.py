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
