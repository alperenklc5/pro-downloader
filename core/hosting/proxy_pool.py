"""Ücretsiz proxy havuzu — IP rotasyonu için."""
from __future__ import annotations

import random
import time
import logging
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
]

REQUEST_TIMEOUT = 5


@dataclass
class ProxyInfo:
    """Tek bir proxy bilgisi."""
    ip: str
    port: int
    protocol: str = "http"
    is_alive: bool = True
    last_used: float = 0
    fail_count: int = 0

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.ip}:{self.port}"

    @property
    def dict(self) -> dict:
        return {"http": self.url, "https": self.url}


class ProxyPool:
    """Ücretsiz proxy havuzu yöneticisi."""

    def __init__(self):
        self._proxies: list[ProxyInfo] = []
        self._current_index = 0
        self._last_fetch_time = 0
        self._fetch_interval = 3600  # 1 saat

    def fetch_proxies(self, log_callback=None) -> int:
        """Ücretsiz proxy listelerini indir."""
        def log(msg):
            if log_callback:
                log_callback(msg)

        all_proxies = set()
        for source in PROXY_SOURCES:
            try:
                log(f"[Proxy] Liste indiriliyor: {source.split('/')[-1]}")
                r = requests.get(source, timeout=10)
                r.raise_for_status()
                for line in r.text.strip().split("\n"):
                    line = line.strip()
                    if ":" in line:
                        parts = line.split(":")
                        if len(parts) == 2:
                            ip, port = parts
                            try:
                                all_proxies.add((ip.strip(), int(port.strip())))
                            except ValueError:
                                continue
            except Exception as e:
                log(f"[Proxy] Liste indirilemedi: {e}")
                continue

        self._proxies = [
            ProxyInfo(ip=ip, port=port)
            for ip, port in all_proxies
        ]
        random.shuffle(self._proxies)
        self._last_fetch_time = time.time()

        log(f"[Proxy] {len(self._proxies)} proxy bulundu")
        return len(self._proxies)

    def get_next(self) -> ProxyInfo | None:
        """Sonraki çalışan proxy'yi al."""
        if not self._proxies:
            return None

        # Maksimum 10 deneme
        for _ in range(min(10, len(self._proxies))):
            proxy = self._proxies[self._current_index % len(self._proxies)]
            self._current_index += 1

            if proxy.fail_count < 3:
                proxy.last_used = time.time()
                return proxy

        return None

    def mark_failed(self, proxy: ProxyInfo) -> None:
        """Proxy'yi başarısız olarak işaretle."""
        proxy.fail_count += 1
        if proxy.fail_count >= 3:
            proxy.is_alive = False

    def mark_success(self, proxy: ProxyInfo) -> None:
        """Proxy'yi başarılı olarak işaretle."""
        proxy.fail_count = 0
        proxy.is_alive = True

    def test_proxy(self, proxy: ProxyInfo) -> bool:
        """Proxy'nin çalışıp çalışmadığını test et."""
        try:
            r = requests.get(
                "https://httpbin.org/ip",
                proxies=proxy.dict,
                timeout=REQUEST_TIMEOUT,
            )
            return r.status_code == 200
        except Exception:
            self.mark_failed(proxy)
            return False

    @property
    def alive_count(self) -> int:
        return sum(1 for p in self._proxies if p.is_alive)

    @property
    def total_count(self) -> int:
        return len(self._proxies)
