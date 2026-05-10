"""libtorrent wrapper - torrent indirme motoru."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal
import logging

logger = logging.getLogger(__name__)


@dataclass
class TorrentProgress:
    """Torrent indirme ilerleme bilgisi."""
    status: Literal["queued", "downloading", "seeding", "finished", "error"]
    progress_percent: float      # 0-100
    download_speed: float        # bytes/sec
    upload_speed: float          # bytes/sec
    seeds: int
    peers: int
    eta_seconds: int | None
    name: str
    downloaded_bytes: int
    total_bytes: int

    def speed_formatted(self) -> str:
        speed = self.download_speed
        if speed > 1_000_000:
            return f"{speed/1_000_000:.1f} MB/s"
        if speed > 1_000:
            return f"{speed/1_000:.0f} KB/s"
        return f"{speed:.0f} B/s"


class TorrentDownloader:
    """libtorrent ile torrent indirir."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self._cancel_flag = False

    def download_magnet(
        self,
        magnet: str,
        progress_callback: Callable[[TorrentProgress], None] | None = None,
        seed_time: int = 0,
    ) -> Path | None:
        """Magnet URL ile torrent indir.

        Returns: İndirilen dosyanın yolu, hata varsa None
        """
        try:
            import libtorrent as lt
        except ImportError:
            logger.error("libtorrent kurulu değil. 'pip install libtorrent' çalıştır.")
            return None

        self.output_dir.mkdir(parents=True, exist_ok=True)

        ses = lt.session()
        ses.listen_on(6881, 6891)

        params = lt.parse_magnet_uri(magnet)
        params.save_path = str(self.output_dir)
        handle = ses.add_torrent(params)

        logger.info("Torrent metadata bekleniyor...")
        meta_timeout = 60
        elapsed = 0
        while not handle.has_metadata() and elapsed < meta_timeout:
            if self._cancel_flag:
                ses.remove_torrent(handle)
                return None
            time.sleep(1)
            elapsed += 1

        if not handle.has_metadata():
            logger.error("Metadata alınamadı")
            return None

        logger.info(f"İndirme başlıyor: {handle.name()}")

        while True:
            if self._cancel_flag:
                ses.remove_torrent(handle)
                return None

            s = handle.status()
            total = s.total_wanted
            downloaded = s.total_wanted_done
            percent = (downloaded / total * 100) if total > 0 else 0

            eta = None
            if s.download_rate > 0 and total > 0:
                remaining = total - downloaded
                eta = int(remaining / s.download_rate)

            progress = TorrentProgress(
                status="downloading" if s.state not in [
                    lt.torrent_status.seeding,
                    lt.torrent_status.finished
                ] else "seeding",
                progress_percent=percent,
                download_speed=s.download_rate,
                upload_speed=s.upload_rate,
                seeds=s.num_seeds,
                peers=s.num_peers,
                eta_seconds=eta,
                name=handle.name(),
                downloaded_bytes=downloaded,
                total_bytes=total,
            )

            if progress_callback:
                progress_callback(progress)

            if s.state in [lt.torrent_status.seeding, lt.torrent_status.finished]:
                if seed_time > 0:
                    time.sleep(seed_time)
                ses.remove_torrent(handle)
                break

            time.sleep(1)

        return self._find_downloaded_file(handle.name())

    def download_torrent_file(
        self,
        torrent_url: str,
        progress_callback: Callable[[TorrentProgress], None] | None = None,
    ) -> Path | None:
        """Direkt .torrent dosyası URL'si ile indir."""
        import requests
        try:
            import libtorrent as lt
        except ImportError:
            logger.error("libtorrent kurulu değil.")
            return None

        resp = requests.get(torrent_url, timeout=30)
        resp.raise_for_status()

        tmp_path = self.output_dir / "_tmp.torrent"
        tmp_path.write_bytes(resp.content)

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)

            ses = lt.session()
            ses.listen_on(6881, 6891)

            info = lt.torrent_info(str(tmp_path))
            handle = ses.add_torrent({
                "ti": info,
                "save_path": str(self.output_dir)
            })

            while True:
                if self._cancel_flag:
                    ses.remove_torrent(handle)
                    return None

                s = handle.status()
                total = s.total_wanted
                downloaded = s.total_wanted_done
                percent = (downloaded / total * 100) if total > 0 else 0

                eta = None
                if s.download_rate > 0 and total > 0:
                    eta = int((total - downloaded) / s.download_rate)

                progress = TorrentProgress(
                    status="downloading",
                    progress_percent=percent,
                    download_speed=s.download_rate,
                    upload_speed=s.upload_rate,
                    seeds=s.num_seeds,
                    peers=s.num_peers,
                    eta_seconds=eta,
                    name=info.name(),
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                )

                if progress_callback:
                    progress_callback(progress)

                if s.state in [lt.torrent_status.seeding, lt.torrent_status.finished]:
                    ses.remove_torrent(handle)
                    break

                time.sleep(1)

            return self._find_downloaded_file(info.name())

        finally:
            tmp_path.unlink(missing_ok=True)

    def cancel(self) -> None:
        """İndirmeyi iptal et."""
        self._cancel_flag = True

    def _find_downloaded_file(self, torrent_name: str) -> Path | None:
        """İndirilen ana video dosyasını bul."""
        torrent_dir = self.output_dir / torrent_name
        video_exts = {".mkv", ".mp4", ".avi", ".mov", ".wmv"}

        if torrent_dir.exists() and torrent_dir.is_dir():
            files = sorted(
                [f for f in torrent_dir.rglob("*") if f.suffix.lower() in video_exts],
                key=lambda f: f.stat().st_size,
                reverse=True
            )
            if files:
                return files[0]

        files = sorted(
            [f for f in self.output_dir.iterdir()
             if f.suffix.lower() in video_exts and f.name != "_tmp.torrent"],
            key=lambda f: f.stat().st_size,
            reverse=True
        )
        return files[0] if files else None
