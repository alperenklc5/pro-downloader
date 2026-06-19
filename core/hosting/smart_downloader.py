"""Akıllı indirici — Mega ve Pixeldrain linklerini otomatik algıla ve indir."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from core.hosting.mega_downloader import MegaDownloader, DownloadProgress
from core.hosting.pixeldrain_downloader import PixeldrainDownloader
from core.hosting.proxy_pool import ProxyPool

logger = logging.getLogger(__name__)


class SmartDownloader:
    """URL'yi analiz et, doğru indiriciyi seç, limit bypass ile indir."""

    def __init__(
        self,
        output_dir: Path,
        vps_url: str | None = None,
    ):
        self.output_dir = output_dir
        self.vps_url = vps_url
        self.proxy_pool = ProxyPool()
        self._current_downloader = None

    @staticmethod
    def is_supported(url: str) -> bool:
        """URL desteklenen hosting sitesi mi?"""
        return (
            MegaDownloader.is_mega_link(url)
            or PixeldrainDownloader.is_pixeldrain_link(url)
        )

    @staticmethod
    def detect_service(url: str) -> str | None:
        """URL hangi servis?"""
        if MegaDownloader.is_mega_link(url):
            return "mega"
        if PixeldrainDownloader.is_pixeldrain_link(url):
            return "pixeldrain"
        return None

    def download(
        self,
        url: str,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
        log_callback=None,
    ) -> Path | None:
        """URL'yi analiz et ve indir."""
        def log(msg):
            if log_callback:
                log_callback(msg)

        service = self.detect_service(url)

        if service == "mega":
            log("[Smart] Mega.nz linki algılandı")
            downloader = MegaDownloader(self.output_dir, self.vps_url)
            self._current_downloader = downloader
            return downloader.download(
                url,
                progress_callback=progress_callback,
                proxy_pool=self.proxy_pool,
                log_callback=log_callback,
            )

        elif service == "pixeldrain":
            log("[Smart] Pixeldrain linki algılandı")
            downloader = PixeldrainDownloader(self.output_dir)
            self._current_downloader = downloader
            return downloader.download(
                url,
                progress_callback=progress_callback,
                proxy_pool=self.proxy_pool,
                log_callback=log_callback,
            )

        else:
            log(f"[Smart] Desteklenmeyen URL: {url}")
            return None

    def pause(self):
        if self._current_downloader:
            self._current_downloader.pause()

    def resume(self):
        if self._current_downloader:
            self._current_downloader.resume()

    def cancel(self):
        if self._current_downloader:
            self._current_downloader.cancel()
