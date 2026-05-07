"""
core — yt-dlp tabanlı video indirme paketi.

Hem desktop hem de backend tarafından kullanılan ortak modül.
"""

from core.auth import CookieConfig
from core.downloader import DownloadOptions, Downloader
from core.exceptions import (
    AuthenticationRequiredError,
    CookieError,
    DownloadCancelledError,
    DownloaderError,
    FormatNotAvailableError,
    InvalidURLError,
    NetworkError,
    VideoUnavailableError,
)
from core.extractor import VideoInfo, extract_info
from core.formats import AudioFormat, VideoFormat
from core.progress import ProgressInfo

__all__ = [
    "Downloader",
    "DownloadOptions",
    "CookieConfig",
    "extract_info",
    "VideoInfo",
    "VideoFormat",
    "AudioFormat",
    "ProgressInfo",
    "DownloaderError",
    "InvalidURLError",
    "VideoUnavailableError",
    "AuthenticationRequiredError",
    "CookieError",
    "NetworkError",
    "FormatNotAvailableError",
    "DownloadCancelledError",
]
