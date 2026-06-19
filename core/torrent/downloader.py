"""libtorrent wrapper - torrent indirme motoru."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal
import logging

logger = logging.getLogger(__name__)

_INVALID_WIN_CHARS = re.compile(r'[<>:"/\\|?*]')

RESUME_FILENAME = ".resume_data"
RESUME_SAVE_INTERVAL = 30  # saniye


def _safe_torrent_filename(url: str) -> str:
    """URL'den güvenli bir .torrent dosya adı türet."""
    name = url.split("/")[-1].split("?")[0]
    name = _INVALID_WIN_CHARS.sub("", name)
    name = name[:100]
    return name or "_tmp_download"


def _format_bytes(size: int) -> str:
    """Byte'ı okunabilir formata çevir."""
    if size <= 0:
        return "0 B"
    if size >= 1_000_000_000:
        return f"{size/1_000_000_000:.1f} GB"
    if size >= 1_000_000:
        return f"{size/1_000_000:.0f} MB"
    if size >= 1_000:
        return f"{size/1_000:.0f} KB"
    return f"{size} B"


@dataclass
class TorrentProgress:
    """Torrent indirme ilerleme bilgisi."""
    status: Literal["queued", "downloading", "paused", "seeding", "finished", "error"]
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

    def eta_formatted(self) -> str:
        """ETA'yı dakika:saniye formatında göster."""
        if self.eta_seconds is None:
            return "--:--"
        if self.eta_seconds <= 0:
            return "00:00"
        total_seconds = int(self.eta_seconds)
        if total_seconds >= 3600:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}sa {minutes:02d}dk"
        if total_seconds >= 60:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}dk {seconds:02d}sn"
        return f"{total_seconds}sn"

    def size_formatted(self) -> str:
        return _format_bytes(self.total_bytes)

    def downloaded_formatted(self) -> str:
        return _format_bytes(self.downloaded_bytes)

    def remaining_formatted(self) -> str:
        remaining = max(0, self.total_bytes - self.downloaded_bytes)
        return _format_bytes(remaining)


class TorrentDownloader:
    """libtorrent ile torrent indirir."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self._cancel_flag = False
        self._pause_flag = False
        self._handle = None
        self._session = None

    # ------------------------------------------------------------------
    # Public kontrol
    # ------------------------------------------------------------------

    def pause(self) -> None:
        """İndirmeyi duraklat ve resume data kaydet."""
        self._pause_flag = True
        if self._handle:
            try:
                import libtorrent as lt
                self._handle.pause()
                self._handle.unset_flags(lt.torrent_flags.auto_managed)
            except Exception:
                pass
        # Durumu diske kaydet ki uygulama kapanınca da kalıcı olsun
        self._save_resume_json_if_possible()

    def resume(self) -> None:
        """İndirmeye devam et."""
        self._pause_flag = False
        if self._handle:
            try:
                import libtorrent as lt
                self._handle.set_flags(lt.torrent_flags.auto_managed)
                self._handle.resume()
            except Exception:
                pass

    def cancel(self) -> None:
        """İndirmeyi iptal et ve resume data'yı temizle (temiz çıkış)."""
        self._cancel_flag = True
        if self._handle:
            try:
                self._handle.pause()
            except Exception:
                pass
        # İptal = kasıtlı durdurma, bir sonraki açılışta devam etme
        self._delete_resume_file()

    # ------------------------------------------------------------------
    # İndirme metodları
    # ------------------------------------------------------------------

    def download_magnet(
        self,
        magnet: str,
        progress_callback: Callable[[TorrentProgress], None] | None = None,
        seed_time: int = 0,
    ) -> Path | None:
        """Magnet URL ile torrent indir."""
        if not magnet.startswith("magnet:?xt=urn:btih:"):
            raise ValueError(f"Geçersiz magnet URL: {magnet!r}")

        try:
            import libtorrent as lt
        except ImportError:
            logger.error("libtorrent kurulu değil. 'pip install libtorrent' çalıştır.")
            return None

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Resume var mı?
        resuming = self._has_resume_data()
        if resuming:
            logger.info(f"Resume data bulundu — kaldığı yerden devam ediliyor: {self.output_dir}")
        else:
            logger.info(f"Magnet indirme başlatılıyor. output_dir={self.output_dir}")

        ses = lt.session()
        ses.listen_on(6881, 6891)
        self._session = ses

        params = lt.parse_magnet_uri(magnet)
        params.save_path = str(self.output_dir)
        handle = ses.add_torrent(params)
        self._handle = handle

        # İlk kayıt
        self._save_resume_json(magnet, "magnet")

        logger.info("Torrent metadata bekleniyor...")
        meta_timeout = 60
        elapsed = 0
        while not handle.has_metadata() and elapsed < meta_timeout:
            if self._cancel_flag:
                logger.warning(f"_cancel_flag — metadata aşamasında iptal (elapsed={elapsed}s).")
                ses.remove_torrent(handle)
                return None
            time.sleep(1)
            elapsed += 1

        if not handle.has_metadata():
            logger.error(f"Metadata alınamadı — {meta_timeout}s zaman aşımı doldu.")
            return None

        torrent_name = handle.name()
        logger.info(f"Metadata alındı: {torrent_name!r}")

        last_save = time.time()

        while True:
            if self._cancel_flag:
                logger.warning(f"_cancel_flag — indirme döngüsünde iptal ({torrent_name!r}).")
                ses.remove_torrent(handle)
                return None

            if self._pause_flag:
                s = handle.status()
                total = s.total_wanted
                downloaded = s.total_wanted_done
                percent = (downloaded / total * 100) if total > 0 else 0
                if progress_callback:
                    progress_callback(TorrentProgress(
                        status="paused",
                        progress_percent=percent,
                        download_speed=0,
                        upload_speed=0,
                        seeds=s.num_seeds,
                        peers=s.num_peers,
                        eta_seconds=None,
                        name=torrent_name,
                        downloaded_bytes=downloaded,
                        total_bytes=total,
                    ))
                time.sleep(1)
                continue

            s = handle.status()
            total = s.total_wanted
            downloaded = s.total_wanted_done
            percent = (downloaded / total * 100) if total > 0 else 0

            eta = None
            if s.download_rate > 0 and total > 0:
                eta = int((total - downloaded) / s.download_rate)

            logger.debug(
                f"[magnet] state={s.state}, seeds={s.num_seeds}, peers={s.num_peers}, "
                f"rate={s.download_rate:.0f}B/s, progress={percent:.1f}%, eta={eta}s"
            )

            status = "seeding" if s.state in [
                lt.torrent_status.seeding, lt.torrent_status.finished
            ] else "downloading"

            progress = TorrentProgress(
                status=status,
                progress_percent=percent,
                download_speed=s.download_rate,
                upload_speed=s.upload_rate,
                seeds=s.num_seeds,
                peers=s.num_peers,
                eta_seconds=eta,
                name=torrent_name,
                downloaded_bytes=downloaded,
                total_bytes=total,
            )

            if progress_callback:
                progress_callback(progress)

            # Periyodik kayıt
            now = time.time()
            if now - last_save >= RESUME_SAVE_INTERVAL:
                self._save_resume_json(magnet, "magnet")
                last_save = now

            if s.state in [lt.torrent_status.seeding, lt.torrent_status.finished]:
                logger.info(f"İndirme tamamlandı ({s.state}): {torrent_name!r}")
                self._delete_resume_file()
                if seed_time > 0:
                    time.sleep(seed_time)
                ses.remove_torrent(handle)
                break

            time.sleep(1)

        logger.info(f"_find_downloaded_file çağrıldı: torrent_name={torrent_name!r}")
        result = self._find_downloaded_file(torrent_name)
        if result is None:
            logger.error(f"_find_downloaded_file None döndü (torrent_name={torrent_name!r}).")
        else:
            logger.info(f"Video dosyası bulundu: {result}")
        return result

    def download_torrent_file(
        self,
        torrent_url: str,
        progress_callback: Callable[[TorrentProgress], None] | None = None,
    ) -> Path | None:
        """Direkt .torrent dosyası URL'si ile indir."""
        if not (torrent_url.startswith("http://") or torrent_url.startswith("https://")):
            raise ValueError(f"Geçersiz torrent URL: {torrent_url!r}")

        import requests
        try:
            import libtorrent as lt
        except ImportError:
            logger.error("libtorrent kurulu değil.")
            return None

        logger.info(f"Torrent URL indiriliyor: {torrent_url}")
        resp = requests.get(torrent_url, timeout=30, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location", "")
            logger.info(f"Redirect alındı ({resp.status_code}): {location!r}")
            if location.startswith("magnet:"):
                logger.info("Redirect magnet'e → download_magnet'e devrediliyor.")
                return self.download_magnet(location, progress_callback)
            logger.info(f"HTTP redirect takip ediliyor: {location!r}")
            resp = requests.get(location, timeout=30)
        resp.raise_for_status()
        logger.info(f".torrent dosyası indirildi: {len(resp.content)} byte")

        tmp_path = self.output_dir / "_tmp_download.torrent"
        tmp_path.write_bytes(resp.content)
        logger.info(f"Geçici .torrent yazıldı: {tmp_path}")

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Resume var mı?
            resuming = self._has_resume_data()
            if resuming:
                logger.info(f"Resume data bulundu — kaldığı yerden devam: {self.output_dir}")

            ses = lt.session()
            ses.listen_on(6881, 6891)
            self._session = ses

            info = lt.torrent_info(str(tmp_path))
            torrent_name = info.name()
            logger.info(f".torrent parse: {torrent_name!r}, files={info.num_files()}")

            handle = ses.add_torrent({"ti": info, "save_path": str(self.output_dir)})
            self._handle = handle
            logger.info(f"Session'a eklendi: {torrent_name!r}")

            # İlk kayıt
            self._save_resume_json(torrent_url, "torrent_url")

            last_save = time.time()

            while True:
                if self._cancel_flag:
                    logger.warning(f"_cancel_flag — döngüde iptal ({torrent_name!r}).")
                    ses.remove_torrent(handle)
                    return None

                if self._pause_flag:
                    s = handle.status()
                    total = s.total_wanted
                    downloaded = s.total_wanted_done
                    percent = (downloaded / total * 100) if total > 0 else 0
                    if progress_callback:
                        progress_callback(TorrentProgress(
                            status="paused",
                            progress_percent=percent,
                            download_speed=0,
                            upload_speed=0,
                            seeds=s.num_seeds,
                            peers=s.num_peers,
                            eta_seconds=None,
                            name=torrent_name,
                            downloaded_bytes=downloaded,
                            total_bytes=total,
                        ))
                    time.sleep(1)
                    continue

                s = handle.status()
                total = s.total_wanted
                downloaded = s.total_wanted_done
                percent = (downloaded / total * 100) if total > 0 else 0

                eta = None
                if s.download_rate > 0 and total > 0:
                    eta = int((total - downloaded) / s.download_rate)

                logger.debug(
                    f"[torrent_file] state={s.state}, seeds={s.num_seeds}, peers={s.num_peers}, "
                    f"rate={s.download_rate:.0f}B/s, progress={percent:.1f}%, eta={eta}s"
                )

                progress = TorrentProgress(
                    status="downloading",
                    progress_percent=percent,
                    download_speed=s.download_rate,
                    upload_speed=s.upload_rate,
                    seeds=s.num_seeds,
                    peers=s.num_peers,
                    eta_seconds=eta,
                    name=torrent_name,
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                )

                if progress_callback:
                    progress_callback(progress)

                now = time.time()
                if now - last_save >= RESUME_SAVE_INTERVAL:
                    self._save_resume_json(torrent_url, "torrent_url")
                    last_save = now

                if s.state in [lt.torrent_status.seeding, lt.torrent_status.finished]:
                    logger.info(f"İndirme tamamlandı ({s.state}): {torrent_name!r}")
                    self._delete_resume_file()
                    ses.remove_torrent(handle)
                    break

                time.sleep(1)

            logger.info(f"_find_downloaded_file çağrıldı: torrent_name={torrent_name!r}")
            result = self._find_downloaded_file(torrent_name)
            if result is None:
                logger.error(f"_find_downloaded_file None döndü (torrent_name={torrent_name!r}).")
            else:
                logger.info(f"Video dosyası bulundu: {result}")
            return result

        finally:
            tmp_path.unlink(missing_ok=True)

    def download(
        self,
        magnet: str = "",
        torrent_url: str = "",
        progress_callback: Callable[[TorrentProgress], None] | None = None,
        seed_time: int = 0,
    ) -> Path | None:
        """torrent_url varsa önce onu dene, yoksa magnet'e düş."""
        url_valid = torrent_url.startswith("http://") or torrent_url.startswith("https://")
        magnet_valid = magnet.startswith("magnet:?xt=urn:btih:")

        if url_valid:
            return self.download_torrent_file(torrent_url, progress_callback)
        if magnet_valid:
            return self.download_magnet(magnet, progress_callback, seed_time)
        raise ValueError("Geçerli bir torrent URL veya magnet bulunamadı")

    # ------------------------------------------------------------------
    # Resume helpers
    # ------------------------------------------------------------------

    def _get_resume_file(self) -> Path:
        return self.output_dir / RESUME_FILENAME

    def _has_resume_data(self) -> bool:
        return self._get_resume_file().exists()

    def _save_resume_json(self, source: str, source_type: str) -> None:
        """Kaynak bilgisini JSON olarak diske yaz.

        libtorrent aynı save_path'e aynı torrent'i ekleyince
        var olan piece dosyalarını otomatik kontrol eder ve kaldığı
        yerden devam eder — biz sadece kaynağı saklıyoruz.
        """
        data = {
            "source": source,
            "source_type": source_type,  # "magnet" | "torrent_url"
            "saved_at": time.time(),
        }
        try:
            resume_file = self._get_resume_file()
            resume_file.parent.mkdir(parents=True, exist_ok=True)
            resume_file.write_text(json.dumps(data), encoding="utf-8")
            logger.debug(f"Resume data kaydedildi: {resume_file}")
        except Exception as e:
            logger.warning(f"Resume data yazılamadı: {e}")

    def _save_resume_json_if_possible(self) -> None:
        """Eğer kaynak bilgisi zaten diskte varsa, timestamp'i güncelle."""
        resume_file = self._get_resume_file()
        if resume_file.exists():
            try:
                data = json.loads(resume_file.read_text(encoding="utf-8"))
                data["saved_at"] = time.time()
                resume_file.write_text(json.dumps(data), encoding="utf-8")
            except Exception:
                pass

    def load_resume_json(self) -> dict | None:
        """Kaydedilmiş resume bilgisini döndür (yoksa None)."""
        resume_file = self._get_resume_file()
        if not resume_file.exists():
            return None
        try:
            return json.loads(resume_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _delete_resume_file(self) -> None:
        """İndirme bitince veya iptal edilince resume dosyasını sil."""
        try:
            self._get_resume_file().unlink(missing_ok=True)
            logger.info("Resume data silindi.")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Dosya bul
    # ------------------------------------------------------------------

    def _find_downloaded_file(self, torrent_name: str) -> Path | None:
        """İndirilen ana dosyayı veya klasörü bul (output_dir altında recursive tarama).

        FitGirl gibi repack'ler birden fazla zip parçası olarak gelir; bu durumda
        tek tek dosya yerine içeren klasörün kendisini döndürür.
        """
        media_exts = {
            # Video
            ".mkv", ".mp4", ".avi", ".mov", ".wmv",
            # Oyun
            ".iso", ".exe", ".zip", ".rar", ".7z",
            # Disk image
            ".bin", ".img",
        }
        archive_exts = {".zip", ".rar", ".7z"}

        candidates: list[tuple[Path, int]] = []

        try:
            for f in self.output_dir.rglob("*"):
                try:
                    if f.is_file() and f.suffix.lower() in media_exts and f.name != "_tmp_download.torrent":
                        candidates.append((f, f.stat().st_size))
                except (FileNotFoundError, OSError):
                    continue
        except Exception as e:
            logger.error(f"rglob hatası: {e}")
            return None

        if not candidates:
            logger.error(f"output_dir içinde medya dosyası bulunamadı: {self.output_dir}")
            return None

        # Arşiv dosyalarını klasöre göre grupla; birden fazla parça içeren
        # klasör FitGirl/repack yapısıdır — klasörün kendisini döndür.
        archive_dir_counts: dict[Path, int] = {}
        archive_dir_sizes: dict[Path, int] = {}
        for f, size in candidates:
            if f.suffix.lower() in archive_exts:
                parent = f.parent
                archive_dir_counts[parent] = archive_dir_counts.get(parent, 0) + 1
                archive_dir_sizes[parent] = archive_dir_sizes.get(parent, 0) + size

        multi_part_dirs = [
            (d, archive_dir_sizes[d])
            for d, count in archive_dir_counts.items()
            if count > 1
        ]
        if multi_part_dirs:
            best_dir = max(multi_part_dirs, key=lambda x: x[1])[0]
            logger.info(
                f"Çok parçalı arşiv klasörü bulundu "
                f"({archive_dir_counts[best_dir]} dosya): {best_dir}"
            )
            return best_dir

        # Tek dosya — en büyüğünü döndür
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
