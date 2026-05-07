"""
Kullanıcı ayarları yönetimi.

Ayarlar ~/.video-downloader/config.json dosyasında saklanır.
İlk açılışta default değerlerle oluşturulur.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from core.auth import CookieConfig

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".video-downloader"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    """Uygulama ayarları."""

    download_dir: str = str(Path.home() / "Downloads" / "VideoDownloader")
    default_quality: str = "720p"
    default_audio_format: str = "mp3"
    default_video_format: str = "mp4"
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    embed_subtitles: bool = False
    download_subtitles: bool = False
    subtitle_languages: list[str] = field(default_factory=lambda: ["en", "tr"])
    rate_limit: str | None = None
    max_concurrent_downloads: int = 2
    theme_mode: Literal["dark", "light", "system"] = "dark"
    cookies_mode: Literal["browser", "file", "none"] = "none"
    cookies_browser: str | None = None
    cookies_browser_profile: str | None = None
    cookies_file_path: str | None = None

    def get_cookie_config(self) -> CookieConfig:
        """AppConfig alanlarından CookieConfig nesnesi oluşturur."""
        return CookieConfig(
            mode=self.cookies_mode,
            browser=self.cookies_browser,  # type: ignore[arg-type]
            browser_profile=self.cookies_browser_profile,
            file_path=Path(self.cookies_file_path) if self.cookies_file_path else None,
        )

    @classmethod
    def load(cls) -> "AppConfig":
        """Config dosyasını yükler, yoksa default oluşturur."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Eksik anahtarları default ile doldur
                defaults = asdict(cls())
                defaults.update(data)
                config = cls(**{k: defaults[k] for k in cls.__dataclass_fields__})
                config._migrate()
                return config
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                logger.warning("Config okunamadı (%s), yedeklenip yenisi oluşturuluyor.", exc)
                backup = CONFIG_FILE.with_suffix(".json.bak")
                CONFIG_FILE.rename(backup)

        config = cls()
        config.save()
        return config

    def _migrate(self) -> None:
        """Eski config değerlerini düzelt."""
        changed = False
        # Migration: Firefox'ta "Default" profil ismi yanlıştı
        if self.cookies_browser == "firefox" and self.cookies_browser_profile == "Default":
            self.cookies_browser_profile = None
            changed = True
        if changed:
            self.save()

    def save(self) -> None:
        """Ayarları diske yazar."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        logger.debug("Config kaydedildi: %s", CONFIG_FILE)
