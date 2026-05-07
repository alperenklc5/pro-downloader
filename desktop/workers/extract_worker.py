"""Background thread'de video bilgisi çeken worker."""

from __future__ import annotations

import logging
import threading
from typing import Callable

from core import CookieConfig, VideoInfo, extract_info
from core.exceptions import DownloaderError

logger = logging.getLogger(__name__)


class ExtractWorker:
    """
    Background thread'de video meta verisi çeker.

    Thread-safe: on_success ve on_error callback'leri worker thread'inden
    çağrılır; UI güncellemeleri için run_on_ui ile sarmalanmalıdır.
    """

    def __init__(
        self,
        url: str,
        on_success: Callable[[VideoInfo], None],
        on_error: Callable[[Exception], None],
        cookies: CookieConfig | None = None,
    ) -> None:
        """
        Args:
            url: Bilgisi çekilecek video URL'si.
            on_success: Başarılı sonuçla çağrılır.
            on_error: Hata durumunda çağrılır.
            cookies: Cookie yapılandırması (opsiyonel).
        """
        self.url = url
        self.on_success = on_success
        self.on_error = on_error
        self.cookies = cookies
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Worker thread'ini başlatır."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="ExtractWorker")
        self._thread.start()

    def _run(self) -> None:
        logger.debug("Bilgi çekiliyor: %s", self.url)
        try:
            info = extract_info(self.url, cookies=self.cookies)
            self.on_success(info)
        except DownloaderError as exc:
            logger.warning("Bilgi çekme hatası: %s", exc)
            self.on_error(exc)
        except Exception as exc:
            logger.exception("Beklenmeyen hata")
            self.on_error(exc)
