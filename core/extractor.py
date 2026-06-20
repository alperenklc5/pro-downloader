"""
Video bilgisi Ã§ekme modÃ¼lÃ¼.

Ä°ndirme yapmadan URL'den baÅŸlÄ±k, sÃ¼re, mevcut formatlar gibi
meta verileri alÄ±r.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import yt_dlp

from core.auth import CookieConfig, parse_yt_dlp_error
from core.exceptions import (
    AuthenticationRequiredError,
    InvalidURLError,
    NetworkError,
    VideoUnavailableError,
)
from core.formats import AudioFormat, VideoFormat, parse_formats

logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    """Bir video veya playlist hakkÄ±ndaki meta veriler."""

    url: str
    title: str
    description: str | None
    duration: int | None        # saniye
    thumbnail: str | None
    uploader: str | None
    upload_date: str | None     # "YYYYMMDD"
    view_count: int | None
    video_formats: list[VideoFormat]
    audio_formats: list[AudioFormat]
    is_playlist: bool
    playlist_count: int | None
    extractor: str              # "youtube", "tiktok", vb.


def extract_info(
    url: str,
    timeout: int = 30,
    cookies: CookieConfig | None = None,
) -> VideoInfo:
    """
    URL'den video meta verilerini Ã§eker. Ä°ndirme yapmaz.

    Args:
        url: Desteklenen herhangi bir site URL'si.
        timeout: AÄŸ isteÄŸi zaman aÅŸÄ±mÄ± (saniye).
        cookies: Cookie yapÄ±landÄ±rmasÄ± (opsiyonel).

    Returns:
        VideoInfo nesnesi.

    Raises:
        InvalidURLError: URL geÃ§ersiz veya desteklenmiyor.
        VideoUnavailableError: Video private, silinmiÅŸ ya da kÄ±sÄ±tlÄ±.
        AuthenticationRequiredError: Login/cookie gerekiyor.
        NetworkError: AÄŸ baÄŸlantÄ±sÄ± sorunu.
    """
    ydl_opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "socket_timeout": timeout,
        "skip_download": True,
        "js_runtimes": {"node": {"path": "C:\\Program Files\\nodejs\\node.exe"}},
        "remote_components": ["ejs:github"],
    }
    if cookies:
        ydl_opts.update(cookies.to_ydl_opts())

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.debug("Bilgi Ã§ekiliyor: %s", url)
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        # Ã–nce auth gerektiriyor mu kontrol et
        exc_class = parse_yt_dlp_error(str(exc))
        if exc_class is AuthenticationRequiredError:
            raise AuthenticationRequiredError(str(exc)) from exc
        _raise_mapped_exception(str(exc))
    except Exception as exc:
        raise NetworkError(f"Beklenmeyen hata: {exc}") from exc

    if info is None:
        raise InvalidURLError(f"Bilgi alÄ±namadÄ±: {url}")

    video_formats, audio_formats = parse_formats(info)

    is_playlist = info.get("_type") == "playlist"
    playlist_count: int | None = info.get("playlist_count")

    return VideoInfo(
        url=url,
        title=info.get("title", ""),
        description=info.get("description"),
        duration=int(info["duration"]) if info.get("duration") is not None else None,
        thumbnail=info.get("thumbnail"),
        uploader=info.get("uploader"),
        upload_date=info.get("upload_date"),
        view_count=info.get("view_count"),
        video_formats=video_formats,
        audio_formats=audio_formats,
        is_playlist=is_playlist,
        playlist_count=playlist_count,
        extractor=info.get("extractor", "unknown"),
    )


# ---------------------------------------------------------------------------
# YardÄ±mcÄ± fonksiyonlar
# ---------------------------------------------------------------------------

def _raise_mapped_exception(message: str) -> None:
    """
    yt-dlp DownloadError mesajÄ±nÄ± uygun Ã¶zel exception'a Ã§evirir.

    Args:
        message: Ä°stisna mesajÄ±.

    Raises:
        InvalidURLError | VideoUnavailableError | NetworkError
    """
    msg_lower = message.lower()

    unavailable_keywords = (
        "private video",
        "video unavailable",
        "has been removed",
        "age-restricted",
        "not available",
        "blocked",
        "this video is not available",
    )
    network_keywords = (
        "connection",
        "timed out",
        "timeout",
        "network",
        "unable to connect",
        "name or service not known",
        "nodename nor servname",
    )
    invalid_keywords = (
        "unsupported url",
        "no video formats",
        "is not a valid url",
        "unable to extract",
        "no suitable",
    )

    if any(kw in msg_lower for kw in unavailable_keywords):
        raise VideoUnavailableError(message)
    if any(kw in msg_lower for kw in network_keywords):
        raise NetworkError(message)
    if any(kw in msg_lower for kw in invalid_keywords):
        raise InvalidURLError(message)

    # VarsayÄ±lan: URL desteklenmiyor kabul et
    raise InvalidURLError(message)

