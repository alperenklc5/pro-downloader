"""Background thread'de video indiren, iptal edilebilen worker."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from core import Downloader, DownloadOptions, ProgressInfo
from core.exceptions import DownloadCancelledError, DownloaderError

logger = logging.getLogger(__name__)


class DownloadWorker:
    """
    Background thread'de video indirir.

    İptal edilebilir: cancel() çağrısı aktif indirmeyi durdurur.
    """

    def __init__(
        self,
        url: str,
        options: DownloadOptions,
        on_progress: Callable[[ProgressInfo], None],
        on_complete: Callable[[Path], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        """
        Args:
            url: İndirilecek video URL'si.
            options: İndirme ayarları.
            on_progress: İlerleme güncellemelerinde çağrılır.
            on_complete: Başarılı tamamlanmada çağrılır.
            on_error: Hata durumunda çağrılır.
        """
        self.url = url
        self.options = options
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        self._downloader = Downloader(options)
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Worker thread'ini başlatır."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="DownloadWorker")
        self._thread.start()

    def cancel(self) -> None:
        """Aktif indirmeyi iptal eder."""
        self._downloader.cancel()

    def _run(self) -> None:
        logger.debug("İndirme başlıyor: %s", self.url)
        try:
            path = self._downloader.download(self.url, progress_callback=self.on_progress)
            self.on_complete(path)
        except DownloadCancelledError:
            logger.info("İndirme iptal edildi: %s", self.url)
        except DownloaderError as exc:
            logger.warning("İndirme hatası: %s", exc)
            self.on_error(exc)
        except Exception as exc:
            logger.exception("Beklenmeyen indirme hatası")
            self.on_error(exc)
