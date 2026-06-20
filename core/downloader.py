"""
Ana indirme sınıfı.

Desktop ve backend katmanlarının en çok etkileşeceği bileşen.
yt-dlp'yi yapılandırıp indirmeyi başlatır, ilerleme callback'ini
çağırır ve iptal mekanizmasını yönetir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yt_dlp

from core.auth import CookieConfig
from core.exceptions import (
    DownloadCancelledError,
    DownloaderError,
)
from core.extractor import _raise_mapped_exception
from core.formats import build_format_selector
from core.progress import ProgressInfo, ProgressTracker

logger = logging.getLogger(__name__)


@dataclass
class DownloadOptions:
    """İndirme işlemi için tüm yapılandırma seçenekleri."""

    output_dir: Path
    quality: str = "best"               # "best", "1080p", "720p", …
    audio_only: bool = False
    audio_format: str = "mp3"           # "mp3", "m4a", "opus"
    video_format: str = "mp4"           # "mp4", "mkv", "webm"
    embed_subtitles: bool = False
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    download_subtitles: bool = False
    subtitle_languages: list[str] = field(default_factory=lambda: ["en", "tr"])
    rate_limit: str | None = None       # "1M", "500K", None
    filename_template: str = "%(title)s.%(ext)s"
    cookies: CookieConfig = field(default_factory=CookieConfig)


class Downloader:
    """yt-dlp tabanlı video indirici."""

    def __init__(self, options: DownloadOptions) -> None:
        """
        Args:
            options: İndirme ayarları.
        """
        self.options = options
        self._cancel_flag: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(
        self,
        url: str,
        progress_callback: Callable[[ProgressInfo], None] | None = None,
    ) -> Path:
        """
        Verilen URL'yi indirir.

        Args:
            url: İndirilecek video/ses URL'si.
            progress_callback: İlerleme güncellemelerinde çağrılır.

        Returns:
            İndirilen dosyanın tam yolu.

        Raises:
            DownloadCancelledError: Kullanıcı iptal ettiyse.
            DownloaderError ve alt sınıfları: Diğer hatalar.
        """
        self._cancel_flag = False
        ydl_opts = self._build_ydl_opts(progress_callback)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("İndirme başlıyor: %s", url)
                info = ydl.extract_info(url, download=True)
        except DownloadCancelledError:
            raise
        except yt_dlp.utils.DownloadError as exc:
            err_str = str(exc)
            if "Requested format is not available" in err_str:
                logger.warning("İstenen format mevcut değil, format 18 ile tekrar deneniyor...")
                info = self._download_with_fallback(url, ydl_opts, progress_callback)
            else:
                _raise_mapped_exception(err_str)
                raise  # unreachable; mypy için
        except Exception as exc:
            raise DownloaderError(f"İndirme hatası: {exc}") from exc

        if info is None:
            raise DownloaderError("İndirme bilgisi alınamadı.")

        return self._resolve_output_path(info)

    def cancel(self) -> None:
        """Aktif indirmeyi iptal eder."""
        self._cancel_flag = True
        logger.info("İndirme iptali istendi.")

    # ------------------------------------------------------------------
    # Yardımcı metotlar
    # ------------------------------------------------------------------

    def _build_ydl_opts(
        self,
        progress_callback: Callable[[ProgressInfo], None] | None,
    ) -> dict:
        """yt-dlp seçenekleri sözlüğünü oluşturur."""
        opts = self.options
        output_template = str(
            opts.output_dir / opts.filename_template
        )

        format_selector = build_format_selector(
            opts.quality, audio_only=opts.audio_only
        )

        postprocessors: list[dict] = []

        if opts.audio_only:
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": opts.audio_format,
                    "preferredquality": "192",
                }
            )

        if opts.embed_thumbnail:
            postprocessors.append({"key": "EmbedThumbnail"})

        if opts.embed_metadata:
            postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})

        if opts.embed_subtitles and not opts.audio_only:
            postprocessors.append({"key": "FFmpegEmbedSubtitle"})

        hooks: list[Callable] = []
        if progress_callback is not None:
            tracker = ProgressTracker(self._wrap_callback(progress_callback))
            hooks.append(tracker.hook)

        ydl_opts: dict = {
            "outtmpl": output_template,
            "format": format_selector,
            "postprocessors": postprocessors,
            "progress_hooks": hooks,
            "quiet": True,
            "extractor_args": {
            "youtube": {
                "js_runtime": ["node:C:\\Program Files\\nodejs\\node.exe"],
            },
        },
        "remote_components": "ejs:github",
            "no_warnings": True,
            "js_runtimes": {"node": {"path": "C:\\Program Files\\nodejs\\node.exe"}},
        "remote_components": ["ejs:github"],
            "merge_output_format": opts.video_format if not opts.audio_only else None,
            "extractor_args": {
                "youtube": {
                    "js_runtime": ["node:C:\\Program Files\\nodejs\\node.exe"],
                },
            },
            "remote_components": "ejs:github",
        }

        if opts.download_subtitles:
            ydl_opts["writesubtitles"] = True
            ydl_opts["writeautomaticsub"] = True
            ydl_opts["subtitleslangs"] = opts.subtitle_languages

        if opts.rate_limit:
            ydl_opts["ratelimit"] = _parse_rate_limit(opts.rate_limit)

        ydl_opts.update(opts.cookies.to_ydl_opts())

        return ydl_opts

    def _download_with_fallback(
        self,
        url: str,
        base_opts: dict,
        progress_callback: Callable[[ProgressInfo], None] | None,
    ) -> dict:
        """Format mevcut değilse format 18 (360p ses+video birleşik) ile dene."""
        fallback_opts = dict(base_opts)
        fallback_opts["format"] = "18/best[height<=360]/best"
        try:
            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                info = ydl.extract_info(url, download=True)
            if info is None:
                raise DownloaderError("Format 18 fallback: indirme bilgisi alınamadı.")
            return info
        except DownloadCancelledError:
            raise
        except yt_dlp.utils.DownloadError as exc:
            _raise_mapped_exception(str(exc))
            raise
        except Exception as exc:
            raise DownloaderError(f"Fallback indirme hatası: {exc}") from exc

    def _wrap_callback(
        self, callback: Callable[[ProgressInfo], None]
    ) -> Callable[[ProgressInfo], None]:
        """Callback'i cancel flag kontrolü ile sarar."""

        def wrapped(info: ProgressInfo) -> None:
            if self._cancel_flag:
                raise DownloadCancelledError("İndirme kullanıcı tarafından iptal edildi.")
            callback(info)

        return wrapped

    @staticmethod
    def _resolve_output_path(info: dict) -> Path:
        """
        yt-dlp info dict'inden indirilen dosyanın yolunu çıkarır.

        Önce 'requested_downloads', sonra 'filepath', son olarak
        'filename' anahtarlarına bakar.
        """
        requested = info.get("requested_downloads")
        if requested:
            return Path(requested[0].get("filepath", requested[0].get("filename", "")))

        filepath = info.get("filepath") or info.get("filename", "")
        return Path(filepath)


# ---------------------------------------------------------------------------
# Modül düzeyinde yardımcı
# ---------------------------------------------------------------------------

def _parse_rate_limit(rate_str: str) -> int:
    """
    "1M", "500K" gibi string hız limitlerini bytes/sn'ye çevirir.

    Args:
        rate_str: "1M", "500K", "2G" gibi string.

    Returns:
        bytes/sn cinsinden integer.
    """
    rate_str = rate_str.strip().upper()
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3}
    for suffix, mult in multipliers.items():
        if rate_str.endswith(suffix):
            return int(float(rate_str[:-1]) * mult)
    return int(rate_str)
