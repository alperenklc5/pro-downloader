"""Tarayıcı cookie'lerini cache'leyen modül.

Tarayıcı açıkken cookie DB lock olur ve okuyamayız. Bu modül
cookie'leri bir kez okuyup Netscape cookies.txt formatında
cache klasörüne yazar. Sonraki indirmeler bu dosyayı kullanır.
"""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from core.auth import BrowserName
from core.exceptions import CookieError

logger = logging.getLogger(__name__)

# Cache dizini
CACHE_DIR = Path.home() / ".video-downloader" / "cookies_cache"
CACHE_META_FILE = CACHE_DIR / "meta.json"
CACHE_COOKIES_FILE = CACHE_DIR / "cookies.txt"

# Cache "stale" sayılan süre
STALE_AFTER = timedelta(days=7)


@dataclass
class CacheMetadata:
    """Cache hakkında bilgi."""
    browser: str
    profile: str | None
    synced_at: str  # ISO format datetime
    cookie_count: int

    def synced_datetime(self) -> datetime:
        return datetime.fromisoformat(self.synced_at)

    def is_stale(self) -> bool:
        return datetime.now() - self.synced_datetime() > STALE_AFTER

    def age_human(self) -> str:
        """'2 saat önce', '3 gün önce' gibi insan-okunur süre."""
        delta = datetime.now() - self.synced_datetime()
        if delta < timedelta(minutes=1):
            return "az önce"
        if delta < timedelta(hours=1):
            return f"{int(delta.total_seconds() / 60)} dakika önce"
        if delta < timedelta(days=1):
            return f"{int(delta.total_seconds() / 3600)} saat önce"
        return f"{delta.days} gün önce"


def get_metadata() -> CacheMetadata | None:
    """Mevcut cache metadata'sını oku. Yoksa None."""
    if not CACHE_META_FILE.exists():
        return None
    try:
        with open(CACHE_META_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CacheMetadata(**data)
    except (json.JSONDecodeError, TypeError, OSError):
        return None


def _normalize_profile(profile: str | None) -> str | None:
    """None, "" ve "Default" hepsini None'a normalize et."""
    if profile in (None, "", "Default"):
        return None
    return profile


def is_cache_valid(browser: str, profile: str | None) -> bool:
    """Cache var mı, doğru tarayıcı için mi, dosya gerçekten duruyor mu?"""
    meta = get_metadata()
    if meta is None:
        return False
    if meta.browser != browser:
        return False
    # Profil karşılaştırma: None/""/Default hepsi denk sayılır
    if _normalize_profile(meta.profile) != _normalize_profile(profile):
        return False
    if not CACHE_COOKIES_FILE.exists():
        return False
    return True


def get_cached_cookies_path() -> Path | None:
    """Eğer cache dosyası varsa yolunu döndür, yoksa None."""
    if CACHE_COOKIES_FILE.exists():
        return CACHE_COOKIES_FILE
    return None


def sync_from_browser(
    browser: BrowserName,
    profile: str | None = None,
) -> CacheMetadata:
    """Tarayıcıdan cookie'leri oku, cache'e yaz.

    yt-dlp'nin extract_cookies_from_browser fonksiyonu ile cookie jar alır,
    Netscape format cookies.txt olarak diske yazar.

    Raises:
        CookieError: Cookie okunamadı veya yazılamadı.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # "Default" → None'a normalize (Firefox için kritik)
    profile = _normalize_profile(profile)

    try:
        from yt_dlp.cookies import extract_cookies_from_browser
        cookiejar = extract_cookies_from_browser(
            browser_name=browser,
            profile=profile,
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "locked" in error_msg or "database is locked" in error_msg:
            raise CookieError(
                f"{browser} tarayıcısı açık görünüyor. "
                f"Lütfen tarayıcıyı tamamen kapatıp tekrar deneyin."
            ) from e
        if "dpapi" in error_msg:
            raise CookieError(
                f"{browser} cookie'leri DPAPI ile şifrelenmiş ve okunamıyor. "
                f"Firefox veya manuel cookies.txt kullanmayı deneyin."
            ) from e
        raise CookieError(
            f"Tarayıcıdan cookie okunamadı: {e}"
        ) from e

    # Cookiejar'ı Netscape formatına yaz
    try:
        cookiejar.save(
            filename=str(CACHE_COOKIES_FILE),
            ignore_discard=True,
            ignore_expires=True,
        )
    except Exception as e:
        raise CookieError(f"Cookie dosyası yazılamadı: {e}") from e

    cookie_count = sum(1 for _ in cookiejar)

    # Metadata yaz
    meta = CacheMetadata(
        browser=browser,
        profile=profile,
        synced_at=datetime.now().isoformat(),
        cookie_count=cookie_count,
    )
    with open(CACHE_META_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(meta), f, indent=2, ensure_ascii=False)

    logger.info("Cookie cache güncellendi: %s, %d cookie", browser, cookie_count)
    return meta


def clear_cache() -> None:
    """Cache'i tamamen sil."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
