"""
Format seçimi ve filtreleme mantığı.

yt-dlp'nin verdiği ham format listesini sade ve kullanışlı
VideoFormat / AudioFormat yapılarına çevirir; format selector
string'i üretir.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VideoFormat:
    """Tek bir video formatını temsil eder."""

    format_id: str
    ext: str
    resolution: str          # örn. "1920x1080"
    fps: float | None
    vcodec: str | None
    filesize: int | None     # bayt, bilinmiyorsa None
    has_audio: bool
    has_video: bool

    @property
    def height(self) -> int | None:
        """Çözünürlükten piksel yüksekliğini döndürür."""
        if "x" in self.resolution:
            try:
                return int(self.resolution.split("x")[1])
            except (IndexError, ValueError):
                return None
        return None


@dataclass
class AudioFormat:
    """Tek bir ses formatını temsil eder."""

    format_id: str
    ext: str
    abr: float | None        # kbps cinsinden bit hızı
    acodec: str | None
    filesize: int | None     # bayt, bilinmiyorsa None


def parse_formats(
    info_dict: dict,
) -> tuple[list[VideoFormat], list[AudioFormat]]:
    """
    yt-dlp info dict'inden video ve ses formatlarını ayrıştırır.

    Args:
        info_dict: yt-dlp'nin döndürdüğü ham sözlük.

    Returns:
        (video_formats, audio_formats) ikilisi.
    """
    video_formats: list[VideoFormat] = []
    audio_formats: list[AudioFormat] = []

    for fmt in info_dict.get("formats", []):
        vcodec = fmt.get("vcodec") or "none"
        acodec = fmt.get("acodec") or "none"
        has_video = vcodec != "none"
        has_audio = acodec != "none"

        width: int | None = fmt.get("width")
        height: int | None = fmt.get("height")

        if width and height:
            resolution = f"{width}x{height}"
        elif height:
            resolution = f"?x{height}"
        else:
            resolution = "unknown"

        filesize: int | None = fmt.get("filesize") or fmt.get("filesize_approx")

        if has_video:
            video_formats.append(
                VideoFormat(
                    format_id=fmt.get("format_id", ""),
                    ext=fmt.get("ext", ""),
                    resolution=resolution,
                    fps=fmt.get("fps"),
                    vcodec=vcodec if vcodec != "none" else None,
                    filesize=filesize,
                    has_audio=has_audio,
                    has_video=True,
                )
            )
        elif has_audio:
            audio_formats.append(
                AudioFormat(
                    format_id=fmt.get("format_id", ""),
                    ext=fmt.get("ext", ""),
                    abr=fmt.get("abr"),
                    acodec=acodec if acodec != "none" else None,
                    filesize=filesize,
                )
            )

    return video_formats, audio_formats


def build_format_selector(quality: str, audio_only: bool = False) -> str:
    """
    yt-dlp format selector string'i üretir.

    Args:
        quality: "best", "1080p", "720p", "480p", "360p", "240p", "144p"
                 veya "audio".
        audio_only: True ise yalnızca ses indirilir.

    Returns:
        yt-dlp'ye geçirilecek format selector string'i.
    """
    if audio_only or quality == "audio":
        return "bestaudio/best"

    height_map = {
        "144p": 144,
        "240p": 240,
        "360p": 360,
        "480p": 480,
        "720p": 720,
        "1080p": 1080,
        "1440p": 1440,
        "2160p": 2160,
        "4k": 2160,
    }

    if quality == "best":
        return "bestvideo+bestaudio/best"

    h = height_map.get(quality.lower())
    if h:
        return (
            f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
        )

    # Tanınmayan değer → en iyiyi seç
    return "bestvideo+bestaudio/best"
