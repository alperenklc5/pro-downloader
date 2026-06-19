"""Pixeldrain dosya indirici — limit bypass desteği."""
from __future__ import annotations

import re
import time
import logging
from pathlib import Path
from typing import Callable

import requests

logger = logging.getLogger(__name__)

# Pixeldrain link pattern
PD_PATTERN = re.compile(r"https?://pixeldrain\.com/u/([a-zA-Z0-9]+)")
PD_LIST_PATTERN = re.compile(r"https?://pixeldrain\.com/l/([a-zA-Z0-9]+)")
PD_API = "https://pixeldrain.com/api"


class PixeldrainDownloader:
    """Pixeldrain dosya indirici."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self._cancel_flag = False
        self._pause_flag = False

    @staticmethod
    def is_pixeldrain_link(url: str) -> bool:
        return bool(PD_PATTERN.match(url) or PD_LIST_PATTERN.match(url))

    def get_file_info(self, url: str) -> dict | None:
        """Pixeldrain dosya bilgisi al."""
        match = PD_PATTERN.match(url)
        if not match:
            return None

        file_id = match.group(1)
        try:
            r = requests.get(f"{PD_API}/file/{file_id}/info", timeout=10)
            r.raise_for_status()
            data = r.json()
            return {
                "name": data.get("name", "unknown"),
                "size": data.get("size", 0),
                "file_id": file_id,
                "mime_type": data.get("mime_type", ""),
            }
        except Exception as e:
            logger.error(f"Pixeldrain info hatası: {e}")
            return None

    def download(
        self,
        url: str,
        progress_callback=None,
        proxy_pool=None,
        log_callback=None,
    ) -> Path | None:
        """Pixeldrain dosyasını indir — limit bypass ile."""
        def log(msg):
            if log_callback:
                log_callback(msg)

        match = PD_PATTERN.match(url)
        if not match:
            log("[Pixeldrain] Geçersiz URL")
            return None

        file_id = match.group(1)
        download_url = f"{PD_API}/file/{file_id}"

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Dosya bilgisi al
        info = self.get_file_info(url)
        if not info:
            log("[Pixeldrain] Dosya bilgisi alınamadı")
            return None

        filename = info["name"]
        total_size = info["size"]
        output_path = self.output_dir / filename

        log(f"[Pixeldrain] Dosya: {filename} ({self._format_size(total_size)})")

        # Adım 1: Direkt indir (PC IP)
        log("[Pixeldrain] İndirme başlıyor (PC IP)...")
        result = self._download_file(
            download_url, output_path, total_size,
            progress_callback, log, source="PC"
        )
        if result:
            return result

        # Adım 2: Proxy ile dene
        if proxy_pool:
            log("[Pixeldrain] Proxy rotasyonu başlıyor...")
            if proxy_pool.total_count == 0:
                proxy_pool.fetch_proxies(log_callback=log)

            for attempt in range(10):
                proxy = proxy_pool.get_next()
                if not proxy:
                    break

                log(f"[Pixeldrain] Proxy #{attempt+1} deneniyor...")
                result = self._download_file(
                    download_url, output_path, total_size,
                    progress_callback, log,
                    source=f"Proxy #{attempt+1}",
                    proxies=proxy.dict,
                )
                if result:
                    proxy_pool.mark_success(proxy)
                    return result
                else:
                    proxy_pool.mark_failed(proxy)

        log("[Pixeldrain] ⏳ Tüm IP'ler tükendi.")
        return None

    def _download_file(
        self, url, output_path, total_size,
        progress_callback, log, source="PC", proxies=None,
    ) -> Path | None:
        """Dosyayı indir, limit hatası varsa None dön."""
        try:
            # Range header ile kaldığı yerden devam
            downloaded = 0
            if output_path.exists():
                downloaded = output_path.stat().st_size
                if downloaded >= total_size:
                    log(f"[Pixeldrain] ✓ Dosya zaten tam: {output_path.name}")
                    return output_path

            headers = {}
            if downloaded > 0:
                headers["Range"] = f"bytes={downloaded}-"
                log(f"[Pixeldrain] Kaldığı yerden devam: {self._format_size(downloaded)}")

            r = requests.get(
                url, headers=headers, stream=True,
                proxies=proxies, timeout=30,
            )

            if r.status_code == 429:
                log(f"[Pixeldrain] {source} — rate limit!")
                return None

            if r.status_code == 403:
                log(f"[Pixeldrain] {source} — erişim engellendi!")
                return None

            r.raise_for_status()

            start_time = time.time()
            mode = "ab" if downloaded > 0 else "wb"

            with open(output_path, mode) as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if self._cancel_flag:
                        return None
                    while self._pause_flag:
                        time.sleep(1)

                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback:
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        eta = int((total_size - downloaded) / speed) if speed > 0 else None

                        from core.hosting.mega_downloader import DownloadProgress
                        progress_callback(DownloadProgress(
                            downloaded_bytes=downloaded,
                            total_bytes=total_size,
                            speed=speed,
                            eta_seconds=eta,
                            status="downloading",
                            current_ip_source=source,
                        ))

            log(f"[Pixeldrain] ✓ İndirme tamamlandı ({source})")
            return output_path

        except requests.exceptions.HTTPError as e:
            if "429" in str(e) or "403" in str(e):
                log(f"[Pixeldrain] {source} — limit/engel!")
                return None
            raise
        except Exception as e:
            log(f"[Pixeldrain] {source} — hata: {e}")
            return None

    def pause(self):
        self._pause_flag = True

    def resume(self):
        self._pause_flag = False

    def cancel(self):
        self._cancel_flag = True

    @staticmethod
    def _format_size(size: int) -> str:
        if size >= 1_000_000_000:
            return f"{size/1_000_000_000:.1f} GB"
        if size >= 1_000_000:
            return f"{size/1_000_000:.0f} MB"
        return f"{size/1_000:.0f} KB"
