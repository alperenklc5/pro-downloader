"""Mega.nz dosya indirici — direkt API + AES-128-CTR decrypt.

mega.py bağımlılığı yok. Sadece requests + pycryptodome kullanır.

Protokol:
  1. URL'den file_id ve key_b64 parse et
  2. https://g.api.mega.co.nz/cs endpoint'ine {"a":"g","g":1,"p":file_id} isteği at
  3. Dönen download URL + at (encrypted attrs) al
  4. key_b64'ten AES-128 key ve CTR IV türet
  5. Şifrelenmiş attrs'tan dosya adını çöz
  6. Dosyayı stream ile indir, chunk'ları decrypt ederek yaz
"""
from __future__ import annotations

import base64
import json
import logging
import random
import re
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

logger = logging.getLogger(__name__)

MEGA_API_URL = "https://g.api.mega.co.nz/cs"

MEGA_LINK_PATTERN = re.compile(
    r"https?://mega\.nz/(?:file|folder)/([a-zA-Z0-9_-]+)(?:#([a-zA-Z0-9_-]+))?"
)
MEGA_LINK_PATTERN_OLD = re.compile(
    r"https?://mega\.nz/#!([a-zA-Z0-9_-]+)(?:!([a-zA-Z0-9_-]+))?"
)


# ── Veri sınıfları ────────────────────────────────────────────────────────────

@dataclass
class MegaFileInfo:
    """Mega dosya bilgisi."""
    name: str
    size: int
    download_url: str
    key: str
    file_id: str

    def size_formatted(self) -> str:
        gb = self.size / (1024 ** 3)
        if gb >= 1:
            return f"{gb:.1f} GB"
        mb = self.size / (1024 ** 2)
        return f"{mb:.0f} MB"


@dataclass
class DownloadProgress:
    """İndirme ilerleme bilgisi."""
    downloaded_bytes: int
    total_bytes: int
    speed: float          # bytes/sec
    eta_seconds: int | None
    status: str           # "downloading" | "completed" | "error" | "limit_reached"
    current_ip_source: str  # "PC" | "VPS" | "Proxy #3" gibi

    @property
    def percent(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return (self.downloaded_bytes / self.total_bytes) * 100.0


# ── Crypto yardımcıları ───────────────────────────────────────────────────────

def _b64_decode(s: str) -> bytes:
    """Base64url → bytes (padding otomatik eklenir)."""
    s = s.replace("-", "+").replace("_", "/")
    s += "=" * ((-len(s)) % 4)
    return base64.b64decode(s)


def _parse_url(url: str) -> tuple[str, str | None]:
    """URL'den (file_id, key_b64) döndür."""
    for pat in (MEGA_LINK_PATTERN, MEGA_LINK_PATTERN_OLD):
        m = pat.match(url)
        if m:
            return m.group(1), m.group(2)
    return "", None


def _derive_aes(key_b64: str) -> tuple[bytes, bytes]:
    """
    URL key fragment'ından AES anahtarı ve CTR IV türet.

    key_b64 → 32 byte (8 uint32 big-endian): [w0..w7]
    AES key  = XOR(w0..w3, w4..w7) → 16 byte
    CTR IV   = [w4, w5, 0, 0]      → 16 byte  (nonce üst 8 byte, sayaç 0'dan başlar)
    """
    raw = _b64_decode(key_b64)
    if len(raw) < 32:
        raw = raw + b"\x00" * (32 - len(raw))
    w = struct.unpack(">8I", raw[:32])
    aes_key = struct.pack(">4I", w[0] ^ w[4], w[1] ^ w[5], w[2] ^ w[6], w[3] ^ w[7])
    ctr_iv  = struct.pack(">4I", w[4], w[5], 0, 0)
    return aes_key, ctr_iv


def _decrypt_attrs(at_b64: str, aes_key: bytes) -> dict:
    """
    Şifrelenmiş dosya özelliklerini çöz → {"n": "dosyaadı", ...}

    Mega attrs formatı: AES-128-CBC, IV=0, içerik "MEGA{json}" ile başlar.
    """
    try:
        from Crypto.Cipher import AES as _AES

        raw = _b64_decode(at_b64)
        # 16'nın katına tamamla
        if len(raw) % 16:
            raw += b"\x00" * (16 - len(raw) % 16)

        cipher = _AES.new(aes_key, _AES.MODE_CBC, b"\x00" * 16)
        dec = cipher.decrypt(raw)

        # "MEGA{...}" → JSON kısmını bul
        idx = dec.find(b"{")
        end = dec.rfind(b"}")
        if idx >= 0 and end >= idx:
            return json.loads(dec[idx : end + 1].decode("utf-8", errors="replace"))
    except Exception as e:
        logger.debug("Attrs decrypt başarısız: %s", e)
    return {}


def _api_request(payload: list, proxies: dict | None = None) -> list:
    """Mega /cs API'sine istek at."""
    req_id = random.randint(100_000_000, 999_999_999)
    r = requests.post(
        f"{MEGA_API_URL}?id={req_id}",
        json=payload,
        timeout=30,
        proxies=proxies,
    )
    r.raise_for_status()
    return r.json()


# ── İndirici ──────────────────────────────────────────────────────────────────

class MegaDownloader:
    """Mega.nz dosya indirici — mega.py gerektirmez."""

    def __init__(self, output_dir: Path, vps_url: str | None = None):
        self.output_dir = output_dir
        self.vps_url = vps_url
        self._cancel_flag = False
        self._pause_flag = False

    # ── Statik yardımcılar ────────────────────────────────────────────────────

    @staticmethod
    def is_mega_link(url: str) -> bool:
        return bool(MEGA_LINK_PATTERN.match(url) or MEGA_LINK_PATTERN_OLD.match(url))

    # ── Dosya bilgisi ─────────────────────────────────────────────────────────

    def get_file_info(self, url: str) -> MegaFileInfo | None:
        file_id, key_b64 = _parse_url(url)
        if not file_id or not key_b64:
            return None
        try:
            data = _api_request([{"a": "g", "g": 1, "p": file_id}])
            info = data[0] if isinstance(data, list) and data else {}
            if not isinstance(info, dict) or "g" not in info:
                return None
            aes_key, _ = _derive_aes(key_b64)
            attrs = _decrypt_attrs(info.get("at", ""), aes_key)
            return MegaFileInfo(
                name=attrs.get("n", file_id),
                size=info.get("s", 0),
                download_url=info["g"],
                key=key_b64,
                file_id=file_id,
            )
        except Exception as e:
            logger.error("Mega dosya bilgisi alınamadı: %s", e)
            return None

    # ── Ana indirme metodu ────────────────────────────────────────────────────

    def download(
        self,
        url: str,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
        proxy_pool=None,
        log_callback=None,
    ) -> Path | None:
        """Mega dosyasını indir — limit bypass ile."""
        def log(msg: str) -> None:
            if log_callback:
                log_callback(msg)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 1) URL parse
        file_id, key_b64 = _parse_url(url)
        if not file_id:
            log("[Mega] ✗ Geçersiz Mega URL formatı")
            return None
        if not key_b64:
            log("[Mega] ✗ URL'de şifreleme anahtarı bulunamadı (#key eksik)")
            return None

        # 2) API'den download URL + meta al
        log("[Mega] Dosya bilgisi alınıyor...")
        try:
            data = _api_request([{"a": "g", "g": 1, "p": file_id}])
        except Exception as e:
            log(f"[Mega] ✗ API hatası: {e}")
            return None

        info = data[0] if isinstance(data, list) and data else data
        if not isinstance(info, dict) or "g" not in info:
            # Mega hata kodları: -18 = dosya yok, -9 = içerik yok
            code = info if isinstance(info, int) else (info.get("e") if isinstance(info, dict) else "?")
            if code in (-18, -9):
                log("[Mega] ⚠ Dosya bulunamadı veya silinmiş")
            else:
                log(f"[Mega] ✗ API geçersiz yanıt: {info}")
            return None

        download_url = info["g"]
        total_size   = info.get("s", 0)

        # 3) Anahtar türet, dosya adını çöz
        aes_key, ctr_iv = _derive_aes(key_b64)
        attrs    = _decrypt_attrs(info.get("at", ""), aes_key)
        filename = attrs.get("n") or f"mega_{file_id}"

        log(f"[Mega] Dosya: {filename} ({_fmt_size(total_size)})")
        log("[Mega] İndirme başlıyor (PC IP)...")

        # 4) Direkt indir
        output_path = self.output_dir / filename
        result = self._stream_decrypt(
            download_url, output_path, total_size,
            aes_key, ctr_iv, progress_callback, log, source="PC",
        )
        if result:
            return result

        # 5) Limit/hata → rotasyon
        return self._download_with_rotation(
            download_url, filename, total_size,
            aes_key, ctr_iv, progress_callback, proxy_pool, log,
        )

    # ── Stream + decrypt ──────────────────────────────────────────────────────

    def _stream_decrypt(
        self,
        download_url: str,
        output_path: Path,
        total_size: int,
        aes_key: bytes,
        ctr_iv: bytes,
        progress_callback,
        log,
        source: str = "PC",
        proxies: dict | None = None,
    ) -> Path | None:
        """HTTP stream indir, AES-128-CTR ile decrypt ederek diske yaz."""
        try:
            from Crypto.Cipher import AES
            from Crypto.Util import Counter

            r = requests.get(
                download_url,
                stream=True,
                timeout=60,
                proxies=proxies,
            )

            if r.status_code == 509:
                log(f"[Mega] {source} — bant genişliği limiti doldu (509)!")
                return None
            if r.status_code == 403:
                log(f"[Mega] {source} — erişim engellendi (403)!")
                return None
            r.raise_for_status()

            # CTR sayacını IV'ten başlat
            iv_int = int.from_bytes(ctr_iv, "big")
            ctr    = Counter.new(128, initial_value=iv_int)
            cipher = AES.new(aes_key, AES.MODE_CTR, counter=ctr)

            downloaded = 0
            start_time = time.time()

            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if self._cancel_flag:
                        log("[Mega] İndirme iptal edildi")
                        return None
                    while self._pause_flag:
                        time.sleep(0.5)

                    f.write(cipher.decrypt(chunk))
                    downloaded += len(chunk)

                    if progress_callback:
                        elapsed = time.time() - start_time
                        speed   = downloaded / elapsed if elapsed > 0 else 0
                        eta     = int((total_size - downloaded) / speed) if speed > 0 and total_size > downloaded else None
                        progress_callback(DownloadProgress(
                            downloaded_bytes=downloaded,
                            total_bytes=total_size,
                            speed=speed,
                            eta_seconds=eta,
                            status="downloading",
                            current_ip_source=source,
                        ))

            log(f"[Mega] ✓ İndirme tamamlandı ({source}): {output_path.name}")
            return output_path

        except requests.exceptions.HTTPError as e:
            if "509" in str(e):
                log(f"[Mega] {source} — bant genişliği limiti doldu!")
                return None
            log(f"[Mega] {source} — HTTP hatası: {e}")
            return None
        except Exception as e:
            log(f"[Mega] {source} — hata: {e}")
            logger.exception("_stream_decrypt hatası")
            return None

    # ── IP rotasyonu ──────────────────────────────────────────────────────────

    def _download_with_rotation(
        self,
        download_url: str,
        filename: str,
        total_size: int,
        aes_key: bytes,
        ctr_iv: bytes,
        progress_callback,
        proxy_pool,
        log,
    ) -> Path | None:
        """VPS → proxy rotasyonu ile indirmeyi dene."""

        # Adım 1: VPS
        if self.vps_url:
            log("[Mega] VPS IP ile deneniyor...")
            result = self._download_via_vps(download_url, filename, log)
            if result:
                return result
            log("[Mega] VPS başarısız, proxy deneniyor...")

        # Adım 2: Proxy
        if not proxy_pool:
            log("[Mega] ⏳ Limit aşıldı, proxy havuzu tanımsız.")
            return None

        log("[Mega] Proxy rotasyonu başlıyor...")
        if proxy_pool.total_count == 0:
            proxy_pool.fetch_proxies(log_callback=log)

        output_path = self.output_dir / filename
        for attempt in range(10):
            proxy = proxy_pool.get_next()
            if not proxy:
                log("[Mega] ✗ Çalışan proxy kalmadı")
                break

            log(f"[Mega] Proxy #{attempt + 1} deneniyor: {proxy.ip}:{proxy.port}")

            # Proxy üzerinden önce API'den taze download URL al
            try:
                api_data = _api_request(
                    [{"a": "g", "g": 1}],  # mevcut download_url'yi yenile — basit ping
                    proxies=proxy.dict,
                )
            except Exception:
                pass  # API erişimi olmasa da download URL denenebilir

            result = self._stream_decrypt(
                download_url, output_path, total_size,
                aes_key, ctr_iv, progress_callback, log,
                source=f"Proxy #{attempt + 1}",
                proxies=proxy.dict,
            )
            if result:
                proxy_pool.mark_success(proxy)
                return result
            proxy_pool.mark_failed(proxy)

        log("[Mega] ⏳ Tüm IP'ler tükendi. 6 saat sonra limit sıfırlanacak.")
        log("[Mega] İndirme duraklatıldı — tekrar dene veya bekleme modunda bekle.")
        return None

    def _download_via_vps(self, download_url: str, filename: str, log) -> Path | None:
        """VPS proxy'si üzerinden zaten-şifresi-çözülmüş dosyayı indir."""
        if not self.vps_url:
            return None
        try:
            api_url = f"{self.vps_url}/api/mega/download"
            r = requests.post(api_url, json={"url": download_url}, timeout=30)
            r.raise_for_status()
            data = r.json()
            if not data.get("success"):
                return None

            file_url = data.get("file_url")
            remote_name = data.get("filename", filename)
            out = self.output_dir / remote_name
            log(f"[Mega] VPS'ten dosya aktarılıyor: {remote_name}")

            file_r = requests.get(file_url, stream=True, timeout=300)
            file_r.raise_for_status()
            with open(out, "wb") as f:
                for chunk in file_r.iter_content(chunk_size=65536):
                    if self._cancel_flag:
                        return None
                    f.write(chunk)
            return out
        except Exception as e:
            log(f"[Mega] VPS hatası: {e}")
            return None

    # ── Kontrol ───────────────────────────────────────────────────────────────

    def pause(self)  -> None: self._pause_flag  = True
    def resume(self) -> None: self._pause_flag  = False
    def cancel(self) -> None: self._cancel_flag = True


# ── Yardımcı ─────────────────────────────────────────────────────────────────

def _fmt_size(size: int) -> str:
    if size >= 1_000_000_000:
        return f"{size / 1_000_000_000:.1f} GB"
    if size >= 1_000_000:
        return f"{size / 1_000_000:.0f} MB"
    return f"{size / 1_000:.0f} KB"
