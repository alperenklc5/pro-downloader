# Faz 2.16: Mega.nz + Pixeldrain Limit Bypass İndirici

## Hedef
Mega.nz ve Pixeldrain linklerini IP limit kısıtlaması olmadan indirmek. 
PC IP → VPS IP → Ücretsiz Proxy rotasyonu ile limiti aşmak.

## Nasıl Çalışır

```
Mega/Pixeldrain link yapıştır
        ↓
Dosya bilgisi al (boyut, isim)
        ↓
İndirmeye başla (PC IP ile)
        ↓
Limit doldu? → VPS üzerinden devam et
        ↓
VPS limiti de doldu? → Proxy pool'dan sonraki IP ile devam
        ↓
Tüm IP'ler tükendi? → Bekleme modu (6 saat sonra otomatik devam)
        ↓
Dosya tamamlandı ✓
```

## Bağımlılıklar

```bash
pip install mega.py requests pysocks --break-system-packages
```

## Klasör Yapısı

```
core/
├── hosting/                    # ← Yeni modül
│   ├── __init__.py
│   ├── mega_downloader.py      # Mega.nz API + indirme
│   ├── pixeldrain_downloader.py # Pixeldrain API + indirme
│   ├── proxy_pool.py           # Ücretsiz proxy rotasyonu
│   └── smart_downloader.py     # Akıllı IP rotasyonu + parçalı indirme
```

## Görev 1: `core/hosting/__init__.py`

```python
from core.hosting.mega_downloader import MegaDownloader
from core.hosting.pixeldrain_downloader import PixeldrainDownloader
from core.hosting.smart_downloader import SmartDownloader
from core.hosting.proxy_pool import ProxyPool

__all__ = [
    "MegaDownloader",
    "PixeldrainDownloader", 
    "SmartDownloader",
    "ProxyPool",
]
```

## Görev 2: `core/hosting/proxy_pool.py` — Ücretsiz Proxy Havuzu

```python
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
```

## Görev 3: `core/hosting/mega_downloader.py` — Mega.nz İndirici

```python
"""Mega.nz dosya indirici — limit bypass desteği."""
from __future__ import annotations

import os
import re
import time
import hashlib
import logging
from pathlib import Path
from typing import Callable
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

# Mega API endpoints
MEGA_API_URL = "https://g.api.mega.co.nz"

# Mega link pattern
MEGA_LINK_PATTERN = re.compile(
    r"https?://mega\.nz/(?:file|folder)/([a-zA-Z0-9_-]+)(?:#([a-zA-Z0-9_-]+))?"
)
MEGA_LINK_PATTERN_OLD = re.compile(
    r"https?://mega\.nz/#!([a-zA-Z0-9_-]+)(?:!([a-zA-Z0-9_-]+))?"
)


@dataclass
class MegaFileInfo:
    """Mega dosya bilgisi."""
    name: str
    size: int
    download_url: str
    key: str
    file_id: str

    def size_formatted(self) -> str:
        gb = self.size / (1024**3)
        if gb >= 1:
            return f"{gb:.1f} GB"
        mb = self.size / (1024**2)
        return f"{mb:.0f} MB"


@dataclass
class DownloadProgress:
    """İndirme ilerleme bilgisi."""
    downloaded_bytes: int
    total_bytes: int
    speed: float  # bytes/sec
    eta_seconds: int | None
    status: str  # "downloading", "paused", "limit_reached", "switching_ip", "completed", "error"
    current_ip_source: str  # "PC", "VPS", "Proxy #3" gibi
    
    @property
    def percent(self) -> float:
        if self.total_bytes == 0:
            return 0
        return (self.downloaded_bytes / self.total_bytes) * 100


class MegaDownloader:
    """Mega.nz dosya indirici."""

    def __init__(self, output_dir: Path, vps_url: str | None = None):
        self.output_dir = output_dir
        self.vps_url = vps_url  # VPS backend URL (opsiyonel)
        self._cancel_flag = False
        self._pause_flag = False

    @staticmethod
    def is_mega_link(url: str) -> bool:
        """URL Mega linki mi kontrol et."""
        return bool(MEGA_LINK_PATTERN.match(url) or MEGA_LINK_PATTERN_OLD.match(url))

    def get_file_info(self, url: str) -> MegaFileInfo | None:
        """Mega linkinden dosya bilgisi al."""
        try:
            from mega import Mega
            mega = Mega()
            m = mega.login()  # Anonim giriş
            
            # Link'ten dosya bilgisi çıkar
            file_data = m.get_public_url_info(url)
            
            return MegaFileInfo(
                name=file_data.get("name", "unknown"),
                size=file_data.get("size", 0),
                download_url=url,
                key=file_data.get("key", ""),
                file_id=file_data.get("id", ""),
            )
        except Exception as e:
            logger.error(f"Mega dosya bilgisi alınamadı: {e}")
            return None

    def download(
        self,
        url: str,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
        proxy_pool=None,
        log_callback=None,
    ) -> Path | None:
        """Mega dosyasını indir — limit bypass ile."""
        def log(msg):
            if log_callback:
                log_callback(msg)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from mega import Mega

            log("[Mega] Dosya bilgisi alınıyor...")
            mega = Mega()
            m = mega.login()

            log("[Mega] İndirme başlıyor (PC IP)...")
            
            # Direkt indirme dene
            try:
                result = m.download_url(url, dest_path=str(self.output_dir))
                if result:
                    log(f"[Mega] ✓ İndirme tamamlandı: {result}")
                    return Path(result)
            except Exception as e:
                error_str = str(e).lower()
                if "quota" in error_str or "limit" in error_str or "bandwidth" in error_str:
                    log("[Mega] ⚠ PC IP limiti doldu!")
                    return self._download_with_rotation(
                        url, m, progress_callback, proxy_pool, log
                    )
                else:
                    raise

        except ImportError:
            log("[Mega] mega.py kütüphanesi kurulu değil. pip install mega.py")
            return None
        except Exception as e:
            log(f"[Mega] ✗ Hata: {e}")
            return None

    def _download_with_rotation(
        self,
        url: str,
        mega_client,
        progress_callback,
        proxy_pool,
        log,
    ) -> Path | None:
        """IP rotasyonu ile indirmeye devam et."""
        
        # Adım 1: VPS üzerinden dene
        if self.vps_url:
            log("[Mega] VPS IP ile deneniyor...")
            try:
                result = self._download_via_vps(url, log)
                if result:
                    return result
            except Exception as e:
                log(f"[Mega] VPS ile başarısız: {e}")

        # Adım 2: Proxy pool ile dene
        if proxy_pool:
            log("[Mega] Proxy rotasyonu başlıyor...")
            if proxy_pool.total_count == 0:
                proxy_pool.fetch_proxies(log_callback=log)

            for attempt in range(10):  # Maks 10 proxy dene
                proxy = proxy_pool.get_next()
                if not proxy:
                    log("[Mega] ✗ Çalışan proxy kalmadı")
                    break

                log(f"[Mega] Proxy #{attempt+1} deneniyor: {proxy.ip}:{proxy.port}")

                try:
                    os.environ["HTTPS_PROXY"] = proxy.url
                    os.environ["HTTP_PROXY"] = proxy.url

                    from mega import Mega
                    m = Mega()
                    m_client = m.login()
                    result = m_client.download_url(url, dest_path=str(self.output_dir))

                    if result:
                        proxy_pool.mark_success(proxy)
                        log(f"[Mega] ✓ Proxy ile indirme tamamlandı")
                        return Path(result)

                except Exception as e:
                    error_str = str(e).lower()
                    if "quota" in error_str or "limit" in error_str:
                        log(f"[Mega] Proxy #{attempt+1} limiti de dolmuş, sonraki...")
                        proxy_pool.mark_failed(proxy)
                    else:
                        log(f"[Mega] Proxy #{attempt+1} hatası: {e}")
                        proxy_pool.mark_failed(proxy)
                finally:
                    os.environ.pop("HTTPS_PROXY", None)
                    os.environ.pop("HTTP_PROXY", None)

        # Adım 3: Bekleme modu
        log("[Mega] ⏳ Tüm IP'ler tükendi. 6 saat sonra limit sıfırlanacak.")
        log("[Mega] İndirme duraklatıldı — otomatik devam edecek.")
        
        return None

    def _download_via_vps(self, url: str, log) -> Path | None:
        """VPS backend üzerinden Mega dosyasını indir."""
        if not self.vps_url:
            return None

        try:
            # VPS'e indirme isteği gönder
            api_url = f"{self.vps_url}/api/mega/download"
            r = requests.post(
                api_url,
                json={"url": url},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            
            if data.get("success"):
                # VPS'ten dosyayı PC'ye aktar
                file_url = data.get("file_url")
                filename = data.get("filename", "mega_file")
                
                output_path = self.output_dir / filename
                log(f"[Mega] VPS'ten dosya aktarılıyor: {filename}")
                
                file_r = requests.get(file_url, stream=True, timeout=300)
                file_r.raise_for_status()
                
                with open(output_path, "wb") as f:
                    for chunk in file_r.iter_content(chunk_size=8192):
                        if self._cancel_flag:
                            return None
                        f.write(chunk)
                
                return output_path
            
            return None
        except Exception as e:
            log(f"[Mega] VPS hatası: {e}")
            return None

    def pause(self):
        self._pause_flag = True

    def resume(self):
        self._pause_flag = False

    def cancel(self):
        self._cancel_flag = True
```

## Görev 4: `core/hosting/pixeldrain_downloader.py` — Pixeldrain İndirici

```python
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
```

## Görev 5: `core/hosting/smart_downloader.py` — Akıllı İndirici

```python
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
```

## Görev 6: `desktop/app.py` — URL Analizi Güncelle

VideoPage'deki `_on_fetch` fonksiyonuna Mega/Pixeldrain kontrolü ekle:

```python
from core.hosting import SmartDownloader

def _on_fetch(self, url: str) -> None:
    """URL analiz et — video mu, torrent mu, mega/pixeldrain mı?"""
    url = url.strip()
    
    if not url:
        return
    
    # Mega/Pixeldrain link kontrolü
    if SmartDownloader.is_supported(url):
        service = SmartDownloader.detect_service(url)
        self._log(f"{'Mega' if service == 'mega' else 'Pixeldrain'} linki algılandı", "info")
        self._start_hosting_download(url)
        return
    
    # URL değilse (http ile başlamıyorsa) torrent ara
    if not url.startswith("http://") and not url.startswith("https://"):
        # ... mevcut torrent arama kodu ...
        return
    
    # Normal URL — yt-dlp ile dene
    # ... mevcut yt-dlp kodu ...


def _start_hosting_download(self, url: str) -> None:
    """Mega/Pixeldrain indirme başlat."""
    import re
    import uuid
    
    service = SmartDownloader.detect_service(url)
    safe_name = f"{service}_{uuid.uuid4().hex[:8]}"
    output_dir = Path(self.config_obj.download_dir) / "hosting" / safe_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    downloader = SmartDownloader(
        output_dir=output_dir,
        vps_url=self.config_obj.api_base_url if hasattr(self.config_obj, 'api_base_url') else None,
    )
    
    item = DownloadItem(
        self.download_list,
        title=f"[{service.capitalize()}] İndiriliyor...",
        on_cancel=downloader.cancel,
        on_pause=downloader.pause,
        on_resume=downloader.resume,
    )
    self.download_list.add_item(item)
    
    def on_progress(progress):
        from core.torrent.downloader import TorrentProgress
        # DownloadProgress → TorrentProgress dönüştür (UI uyumu)
        tp = TorrentProgress(
            status=progress.status,
            progress_percent=progress.percent,
            download_speed=progress.speed,
            upload_speed=0,
            seeds=0,
            peers=0,
            eta_seconds=progress.eta_seconds,
            name=progress.current_ip_source,
            downloaded_bytes=progress.downloaded_bytes,
            total_bytes=progress.total_bytes,
        )
        run_on_ui(self, item.update_torrent_progress, tp)
    
    def task():
        from core.torrent.power_manager import prevent_sleep, allow_sleep
        prevent_sleep()
        try:
            self._log(f"İndirme başlıyor: {url[:50]}...", "info")
            self.log_window.show()
            
            result = downloader.download(
                url,
                progress_callback=on_progress,
                log_callback=lambda msg: self._log(msg, "info"),
            )
            
            if result:
                self._log(f"✓ İndirme tamamlandı: {result.name}", "success")
                run_on_ui(self, item.mark_complete, result)
            else:
                self._log("✗ İndirme başarısız", "error")
                run_on_ui(self, item.mark_error, Exception("İndirme başarısız"))
        except Exception as e:
            self._log(f"✗ Hata: {e}", "error")
            run_on_ui(self, item.mark_error, e)
        finally:
            allow_sleep()
    
    threading.Thread(target=task, daemon=True).start()
```

## Görev 7: UI'da Hosting Sekmesi (Sidebar'a Ekle)

Sidebar'a yeni öğe ekle:

```python
# sidebar.py nav_items'a ekle
("hosting", "☁", "Mega / Pixeldrain"),
```

`desktop/ui/pages/hosting_page.py`:

```python
"""Mega.nz ve Pixeldrain indirme sekmesi."""
import customtkinter as ctk
from desktop.ui import theme


class HostingPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PADDING_XL, pady=(theme.PADDING_XL, theme.PADDING_LARGE))

        ctk.CTkLabel(
            header,
            text="☁ Mega.nz / Pixeldrain",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # Desteklenen siteler bilgisi
        info_card = ctk.CTkFrame(
            self,
            fg_color=theme.BG_SECONDARY,
            corner_radius=theme.CORNER_RADIUS_LARGE,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
        )
        info_card.pack(fill="x", padx=theme.PADDING_XL, pady=(0, theme.PADDING_MEDIUM))

        ctk.CTkLabel(
            info_card,
            text=(
                "Desteklenen siteler:\n"
                "• Mega.nz — Dosya ve klasör linkleri\n"
                "• Pixeldrain — Dosya linkleri\n\n"
                "IP limiti aşıldığında otomatik olarak VPS ve proxy rotasyonu yapılır."
            ),
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_SECONDARY,
            justify="left",
        ).pack(padx=theme.PADDING_LARGE, pady=theme.PADDING_MEDIUM)

        # URL Input
        card = ctk.CTkFrame(
            self,
            fg_color=theme.BG_SECONDARY,
            corner_radius=theme.CORNER_RADIUS_LARGE,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
        )
        card.pack(fill="x", padx=theme.PADDING_XL, pady=(0, theme.PADDING_LARGE))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=theme.PADDING_LARGE, pady=theme.PADDING_LARGE)

        self.url_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Mega.nz veya Pixeldrain linki yapıştır...",
            font=theme.FONT_BODY,
            height=44,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_DEFAULT,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.CORNER_RADIUS,
        )
        self.url_entry.pack(fill="x", pady=(0, theme.PADDING_MEDIUM))
        self.url_entry.bind("<Return>", lambda e: self._download())

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        ctk.CTkButton(
            btn_row,
            text="📋 Yapıştır",
            font=theme.FONT_BODY,
            width=120,
            height=38,
            fg_color=theme.BG_TERTIARY,
            hover_color=theme.BG_ELEVATED,
            command=self._paste,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="⬇ İndir",
            font=theme.FONT_BODY_BOLD,
            width=140,
            height=38,
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._download,
        ).pack(side="left")

        # İndirme listesi
        ctk.CTkLabel(
            self,
            text="İndirmeler",
            font=theme.FONT_SUBTITLE,
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=theme.PADDING_XL, pady=(theme.PADDING_LARGE, theme.PADDING_SMALL))

        self.download_list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.download_list.pack(
            fill="both", expand=True,
            padx=theme.PADDING_XL, pady=(0, theme.PADDING_MEDIUM)
        )

    def _paste(self):
        try:
            text = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text)
        except Exception:
            pass

    def _download(self):
        url = self.url_entry.get().strip()
        if url:
            self.app._start_hosting_download(url)
```

## Bağımlılık Kurulumu

```bash
pip install mega.py pysocks --break-system-packages
```

**Not:** `mega.py` paketi bazen `mega` olarak da bulunur:
```bash
pip install mega.py
# veya
pip install megapy
```

## Kabul Kriterleri

1. ✅ Mega.nz linki yapıştır → dosya bilgisi görünür → indirme başlar
2. ✅ Pixeldrain linki yapıştır → indirme başlar
3. ✅ Limit dolunca "⚠ PC IP limiti doldu!" log'da görünür
4. ✅ Otomatik VPS IP'ye geçer (VPS URL ayarlıysa)
5. ✅ VPS limiti de dolunca proxy rotasyonu başlar
6. ✅ Proxy ile indirme devam eder
7. ✅ Progress bar + hız + ETA + indirilen/toplam boyut görünür
8. ✅ Duraklat/Devam/İptal butonları çalışır
9. ✅ Log penceresinde detaylı bilgi (hangi IP kullanılıyor, proxy numarası)
10. ✅ Sidebar'da ☁ Mega/Pixeldrain sekmesi var

## Test Senaryoları

**Test 1 — Küçük Mega dosyası (< 5 GB):**
- Mega linki yapıştır → direkt iner, limit sorunsuz

**Test 2 — Pixeldrain dosyası:**
- Pixeldrain linki yapıştır → iner

**Test 3 — Büyük Mega dosyası (> 5 GB):**
- İndirmeye başlar → limit dolur → log: "PC IP limiti doldu"
- Proxy ile devam eder → tamamlanır

**Test 4 — Geçersiz link:**
- "xxx" yapıştır → "Desteklenmeyen URL" hatası
