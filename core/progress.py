"""
İlerleme bildirimi sistemi.

yt-dlp'nin ham progress hook sözlüklerini ProgressInfo dataclass'ına
çevirir ve kullanıcı tarafından sağlanan callback'i tetikler.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal


@dataclass
class ProgressInfo:
    """Anlık indirme ilerleme bilgisi."""

    status: Literal["downloading", "finished", "error"]
    downloaded_bytes: int
    total_bytes: int | None
    speed: float | None      # bytes/sn
    eta: int | None          # saniye
    percent: float           # 0.0 – 100.0
    filename: str


class ProgressTracker:
    """yt-dlp progress hook'ları için callback yöneticisi."""

    def __init__(self, callback: Callable[[ProgressInfo], None]) -> None:
        """
        Args:
            callback: Her ilerleme güncellemesinde çağrılacak fonksiyon.
        """
        self.callback = callback

    def hook(self, d: dict) -> None:
        """
        yt-dlp tarafından çağrılan progress hook fonksiyonu.

        Args:
            d: yt-dlp'nin sağladığı ham sözlük.
        """
        status = d.get("status", "")
        if status not in ("downloading", "finished", "error"):
            return

        downloaded = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        speed = d.get("speed")
        eta = d.get("eta")
        filename = d.get("filename", "")

        if total and total > 0:
            percent = downloaded / total * 100
        else:
            percent = 0.0

        info = ProgressInfo(
            status=status,  # type: ignore[arg-type]
            downloaded_bytes=downloaded,
            total_bytes=total,
            speed=speed,
            eta=eta,
            percent=percent,
            filename=filename,
        )

        self.callback(info)
