# Faz 2.11: Torrent Modülü (Desktop)

## Hedef
Desktop uygulamasına akıllı torrent desteği eklemek. Kullanıcı bir URL yapıştırdığında:
1. yt-dlp ile indirmeyi dener
2. Başarısız olursa URL'den film/dizi adını çıkarır
3. YTS (film) ve EZTV (dizi) API'lerinden alternatif torrentler arar
4. Kullanıcıya seçenekleri gösterir
5. Seçilen torrenti indirir + Türkçe altyazıyı otomatik ekler

**Bu fazın sonunda elimizde:**
- `core/torrent/` modülü (searcher, downloader, subtitle)
- Desktop'ta akıllı fallback dialog'u
- Otomatik altyazı indirme
- libtorrent ile yerel torrent indirme

## Bağımlılıklar

```bash
pip install libtorrent requests tmdbv3api
```

**Not:** libtorrent Windows için binary wheel:
```bash
pip install libtorrent
```
Eğer hata alınırsa: https://github.com/arvidn/libtorrent/releases adresinden
Python versiyonuna uygun .whl dosyasını indir, `pip install dosya.whl` ile kur.

## Klasör Yapısı

```
video-downloader/
├── core/
│   ├── torrent/                    # ← Yeni modül
│   │   ├── __init__.py
│   │   ├── searcher.py             # YTS + EZTV API sorguları
│   │   ├── downloader.py           # libtorrent wrapper
│   │   ├── subtitle.py             # OpenSubtitles API
│   │   └── detector.py             # URL'den içerik adı çıkar
│   └── ...
├── desktop/
│   ├── ui/
│   │   ├── torrent_results.py      # ← Yeni: Torrent sonuçları dialog
│   │   └── ...
│   └── ...
└── ...
```

## Görev 1: `core/torrent/detector.py` — URL Analizi

URL'den film/dizi adını ve yılını çıkarır. Dizipal, Netflix benzeri sitelerin URL yapısını parse eder.

```python
"""URL'den içerik adı ve türünü çıkarır."""
from __future__ import annotations
import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ContentInfo:
    """URL'den çıkarılan içerik bilgisi."""
    name: str                    # Film/dizi adı
    year: int | None = None      # Yıl (varsa)
    season: int | None = None    # Sezon (dizi ise)
    episode: int | None = None   # Bölüm (dizi ise)
    content_type: str = "unknown" # "movie", "series", "unknown"
    original_url: str = ""


# Bilinen site pattern'leri
SITE_PATTERNS = [
    # Dizipal: /film/film-adi-2023/ veya /dizi/dizi-adi/sezon-1/
    {
        "domain": "dizipal",
        "movie": r"/film/([^/]+)",
        "series": r"/dizi/([^/]+)",
    },
    # FilmMakinesi, DiziBox benzeri genel pattern
    {
        "domain": "*",
        "movie": r"/(film|movie|izle)/([^/]+)",
        "series": r"/(dizi|series|sezon)/([^/]+)",
    },
]

# Temizlenecek pattern'ler (slug → isim)
CLEAN_PATTERNS = [
    (r"-(\d{4})(-|$)", r" \1"),   # -2023- → yıl ayır
    (r"-s(\d+)e(\d+)", ""),        # -s01e01 temizle
    (r"-sezon-(\d+)", ""),         # -sezon-1 temizle
    (r"-bolum-(\d+)", ""),         # -bolum-5 temizle
    (r"-izle$", ""),               # -izle suffix
    (r"-hd$|-full$|-türkçe$", ""), # kalite/dil suffix
    (r"-", " "),                   # kalan tire → boşluk
]


def detect_from_url(url: str) -> ContentInfo:
    """URL'den içerik bilgisi çıkar.

    Önce bilinen site pattern'lerini dener.
    Başarısız olursa genel URL slug çıkarma yapar.
    """
    parsed = urlparse(url)
    path = parsed.path.lower()
    domain = parsed.netloc.lower()

    info = ContentInfo(name="", original_url=url)

    # Film pattern kontrolü
    movie_match = re.search(
        r"/(film|movie|watch|izle)/([a-z0-9-]+)", path
    )
    if movie_match:
        info.content_type = "movie"
        raw_name = movie_match.group(2)
        info.name, info.year = _clean_slug(raw_name)
        return info

    # Dizi pattern kontrolü
    series_match = re.search(
        r"/(dizi|series|show|tv)/([a-z0-9-]+)", path
    )
    if series_match:
        info.content_type = "series"
        raw_name = series_match.group(2)

        # Sezon/bölüm bilgisi
        season_match = re.search(r"sezon[- ]?(\d+)|season[- ]?(\d+)|s(\d+)", path)
        ep_match = re.search(r"bolum[- ]?(\d+)|episode[- ]?(\d+)|e(\d+)", path)

        if season_match:
            info.season = int(next(g for g in season_match.groups() if g))
        if ep_match:
            info.episode = int(next(g for g in ep_match.groups() if g))

        info.name, info.year = _clean_slug(raw_name)
        return info

    # Genel fallback: path'in son anlamlı parçası
    parts = [p for p in path.split("/") if p and len(p) > 3]
    if parts:
        info.name, info.year = _clean_slug(parts[-1])
        info.content_type = "unknown"

    return info


def _clean_slug(slug: str) -> tuple[str, int | None]:
    """URL slug'ını okunabilir isme çevirir, yılı ayırır."""
    year = None

    # Yıl var mı?
    year_match = re.search(r"(\d{4})", slug)
    if year_match:
        year_val = int(year_match.group(1))
        if 1900 < year_val < 2030:
            year = year_val

    # Temizle
    name = slug
    for pattern, replacement in CLEAN_PATTERNS:
        name = re.sub(pattern, replacement, name)

    name = name.strip().title()
    return name, year
```

## Görev 2: `core/torrent/searcher.py` — Torrent Arama

YTS (film) ve EZTV (dizi) API'lerine sorgu atar.

```python
"""YTS ve EZTV API'lerinden torrent arar."""
from __future__ import annotations

import requests
from dataclasses import dataclass, field

# Timeout
REQUEST_TIMEOUT = 10


@dataclass
class TorrentResult:
    """Tek bir torrent sonucu."""
    title: str
    quality: str          # "1080p", "720p", "4K", vb.
    size_bytes: int
    seeds: int
    peers: int
    magnet: str           # Magnet link
    torrent_url: str      # Direkt .torrent dosyası URL'si
    source: str           # "YTS", "EZTV"
    year: int | None = None
    imdb_id: str | None = None
    poster: str | None = None

    def size_formatted(self) -> str:
        """İnsan-okunur boyut."""
        gb = self.size_bytes / (1024 ** 3)
        if gb >= 1:
            return f"{gb:.1f} GB"
        mb = self.size_bytes / (1024 ** 2)
        return f"{mb:.0f} MB"


def search_movies(query: str, year: int | None = None) -> list[TorrentResult]:
    """YTS API'de film ara."""
    try:
        params = {
            "query_term": query,
            "limit": 10,
            "sort_by": "seeds",
            "order_by": "desc",
        }
        if year:
            params["query_term"] = f"{query} {year}"

        resp = requests.get(
            "https://yts.mx/api/v2/list_movies.json",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        movies = data.get("data", {}).get("movies", [])
        results: list[TorrentResult] = []

        for movie in movies:
            for torrent in movie.get("torrents", []):
                size_bytes = torrent.get("size_bytes", 0)
                # Magnet oluştur
                info_hash = torrent.get("hash", "")
                magnet = _build_magnet(info_hash, movie["title"])

                results.append(TorrentResult(
                    title=movie["title"],
                    quality=torrent.get("quality", "?"),
                    size_bytes=size_bytes,
                    seeds=torrent.get("seeds", 0),
                    peers=torrent.get("peers", 0),
                    magnet=magnet,
                    torrent_url=torrent.get("url", ""),
                    source="YTS",
                    year=movie.get("year"),
                    imdb_id=movie.get("imdb_code"),
                    poster=movie.get("medium_cover_image"),
                ))

        # Seed sayısına göre sırala
        return sorted(results, key=lambda r: r.seeds, reverse=True)

    except Exception as e:
        return []


def search_series(query: str, season: int | None = None,
                  episode: int | None = None) -> list[TorrentResult]:
    """EZTV API'de dizi ara."""
    try:
        resp = requests.get(
            "https://eztv.re/api/get-torrents",
            params={"limit": 30, "page": 1},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        torrents = data.get("torrents", [])
        query_lower = query.lower()

        results: list[TorrentResult] = []
        for t in torrents:
            title = t.get("title", "").lower()

            # İsim eşleşmesi
            if query_lower not in title:
                continue

            # Sezon/bölüm filtresi
            if season and episode:
                pattern = f"s{season:02d}e{episode:02d}"
                if pattern not in title:
                    continue
            elif season:
                if f"s{season:02d}" not in title:
                    continue

            size_bytes = int(t.get("size_bytes", 0))
            magnet = t.get("magnet_url", "")
            torrent_url = t.get("torrent_url", "")

            results.append(TorrentResult(
                title=t.get("title", ""),
                quality=_detect_quality(t.get("title", "")),
                size_bytes=size_bytes,
                seeds=t.get("seeds", 0),
                peers=t.get("peers", 0),
                magnet=magnet,
                torrent_url=torrent_url,
                source="EZTV",
            ))

        return sorted(results, key=lambda r: r.seeds, reverse=True)[:10]

    except Exception as e:
        return []


def search_all(query: str, year: int | None = None,
               season: int | None = None,
               episode: int | None = None,
               content_type: str = "unknown") -> list[TorrentResult]:
    """Film ve/veya dizi ara."""
    results: list[TorrentResult] = []

    if content_type in ("movie", "unknown"):
        results.extend(search_movies(query, year))

    if content_type in ("series", "unknown"):
        results.extend(search_series(query, season, episode))

    # Duplicate temizle ve sırala
    seen = set()
    unique = []
    for r in results:
        key = (r.title, r.quality)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return sorted(unique, key=lambda r: r.seeds, reverse=True)


def _build_magnet(info_hash: str, title: str) -> str:
    """Magnet URL oluştur."""
    trackers = [
        "udp://open.demonii.com:1337/announce",
        "udp://tracker.openbittorrent.com:80",
        "udp://tracker.coppersurfer.tk:6969",
        "udp://glotorrents.pw:6969/announce",
    ]
    tracker_str = "&tr=".join(requests.utils.quote(t) for t in trackers)
    return f"magnet:?xt=urn:btih:{info_hash}&dn={requests.utils.quote(title)}&tr={tracker_str}"


def _detect_quality(title: str) -> str:
    """Torrent başlığından kalite bilgisini çıkar."""
    title_lower = title.lower()
    for q in ["4k", "2160p", "1080p", "720p", "480p", "360p"]:
        if q in title_lower:
            return q.upper() if q == "4k" else q
    return "?"
```

## Görev 3: `core/torrent/subtitle.py` — Altyazı İndirme

OpenSubtitles API ile Türkçe altyazı arama ve indirme.

```python
"""OpenSubtitles API ile altyazı arama ve indirme."""
from __future__ import annotations

import gzip
import os
import shutil
from pathlib import Path

import requests

# .env veya config'den alınacak
OPENSUBTITLES_API_KEY = os.getenv("OPENSUBTITLES_API_KEY", "")
OPENSUBTITLES_BASE = "https://api.opensubtitles.com/api/v1"
REQUEST_TIMEOUT = 10


def search_subtitle(
    title: str,
    year: int | None = None,
    imdb_id: str | None = None,
    language: str = "tr",  # Türkçe default
) -> list[dict]:
    """Altyazı ara.

    Returns: Bulunan altyazıların listesi (file_id, filename, download_count)
    """
    if not OPENSUBTITLES_API_KEY:
        return []

    headers = {
        "Api-Key": OPENSUBTITLES_API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "ProDownloader v1.0",
    }

    params = {
        "languages": language,
        "type": "movie",
    }

    if imdb_id:
        # IMDB ID ile arama (en doğru)
        params["imdb_id"] = imdb_id.replace("tt", "")
    else:
        # İsim ile arama
        params["query"] = title
        if year:
            params["year"] = year

    try:
        resp = requests.get(
            f"{OPENSUBTITLES_BASE}/subtitles",
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            files = attrs.get("files", [])
            if files:
                results.append({
                    "file_id": files[0]["file_id"],
                    "filename": files[0].get("file_name", f"{title}.srt"),
                    "downloads": attrs.get("download_count", 0),
                    "language": attrs.get("language", language),
                    "rating": attrs.get("ratings", 0),
                })

        # İndirme sayısına göre sırala
        return sorted(results, key=lambda x: x["downloads"], reverse=True)

    except Exception:
        return []


def download_subtitle(
    file_id: int,
    output_path: Path,
) -> bool:
    """Altyazıyı indir ve output_path'e kaydet.

    Returns: Başarılı mı?
    """
    if not OPENSUBTITLES_API_KEY:
        return False

    headers = {
        "Api-Key": OPENSUBTITLES_API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "ProDownloader v1.0",
    }

    try:
        # Download URL al
        resp = requests.post(
            f"{OPENSUBTITLES_BASE}/download",
            headers=headers,
            json={"file_id": file_id},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        download_url = resp.json().get("link")

        if not download_url:
            return False

        # Dosyayı indir
        file_resp = requests.get(download_url, timeout=30)
        file_resp.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(file_resp.content)
        return True

    except Exception:
        return False


def auto_subtitle(
    title: str,
    video_path: Path,
    year: int | None = None,
    imdb_id: str | None = None,
    languages: list[str] | None = None,
) -> list[Path]:
    """Film için altyazıları otomatik bul ve indir.

    Önce Türkçe, yoksa İngilizce dener.
    Returns: İndirilen altyazı dosyalarının listesi
    """
    if languages is None:
        languages = ["tr", "en"]

    downloaded: list[Path] = []
    video_stem = video_path.stem

    for lang in languages:
        subtitles = search_subtitle(title, year, imdb_id, lang)
        if not subtitles:
            continue

        # En iyi altyazıyı al (en çok indirilen)
        best = subtitles[0]
        ext = Path(best["filename"]).suffix or ".srt"
        output_path = video_path.parent / f"{video_stem}.{lang}{ext}"

        success = download_subtitle(best["file_id"], output_path)
        if success:
            downloaded.append(output_path)

    return downloaded
```

## Görev 4: `core/torrent/downloader.py` — Torrent İndirici

libtorrent ile torrent indirme. Progress callback desteği.

```python
"""libtorrent wrapper - torrent indirme motoru."""
from __future__ import annotations

import time
import threading
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
        seed_time: int = 0,  # İndirme bittikten kaç saniye seed et
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

        # Session oluştur
        ses = lt.session()
        ses.listen_on(6881, 6891)

        # Magnet ekle
        params = lt.parse_magnet_uri(magnet)
        params.save_path = str(self.output_dir)
        handle = ses.add_torrent(params)

        # Metadata bekle (magnet için gerekli)
        logger.info("Torrent metadata bekleniyor...")
        meta_timeout = 60  # 60 saniye
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

        # İndirme döngüsü
        while True:
            if self._cancel_flag:
                ses.remove_torrent(handle)
                return None

            s = handle.status()

            # Progress hesapla
            total = s.total_wanted
            downloaded = s.total_wanted_done
            percent = (downloaded / total * 100) if total > 0 else 0

            # ETA hesapla
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

            # Bitti mi?
            if s.state in [lt.torrent_status.seeding, lt.torrent_status.finished]:
                if seed_time > 0:
                    time.sleep(seed_time)
                ses.remove_torrent(handle)
                break

            time.sleep(1)

        # İndirilen dosyayı bul
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

        # .torrent dosyasını indir
        resp = requests.get(torrent_url, timeout=30)
        resp.raise_for_status()

        # Geçici dosyaya yaz
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

            # İndirme döngüsü (magnet ile aynı mantık)
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

        # Video uzantıları
        video_exts = {".mkv", ".mp4", ".avi", ".mov", ".wmv"}

        # Önce torrent klasörüne bak
        if torrent_dir.exists() and torrent_dir.is_dir():
            files = sorted(
                [f for f in torrent_dir.rglob("*") if f.suffix.lower() in video_exts],
                key=lambda f: f.stat().st_size,
                reverse=True
            )
            if files:
                return files[0]

        # Sonra output_dir'e bak
        files = sorted(
            [f for f in self.output_dir.iterdir()
             if f.suffix.lower() in video_exts and f.name != "_tmp.torrent"],
            key=lambda f: f.stat().st_size,
            reverse=True
        )
        return files[0] if files else None
```

## Görev 5: `core/torrent/__init__.py`

```python
from core.torrent.searcher import search_all, search_movies, search_series, TorrentResult
from core.torrent.downloader import TorrentDownloader, TorrentProgress
from core.torrent.subtitle import auto_subtitle, search_subtitle
from core.torrent.detector import detect_from_url, ContentInfo

__all__ = [
    "search_all", "search_movies", "search_series", "TorrentResult",
    "TorrentDownloader", "TorrentProgress",
    "auto_subtitle", "search_subtitle",
    "detect_from_url", "ContentInfo",
]
```

## Görev 6: `desktop/ui/torrent_results.py` — Sonuçlar Dialog'u

yt-dlp başarısız olduğunda çıkan torrent alternatifleri penceresi.

```python
"""Torrent arama sonuçları dialog'u."""
from __future__ import annotations

import threading
import customtkinter as ctk
from typing import Callable
from core.torrent import TorrentResult, search_all, ContentInfo
from desktop.ui import theme


class TorrentResultsDialog(ctk.CTkToplevel):
    """yt-dlp başarısız olduğunda torrent alternatifleri gösterir."""

    def __init__(
        self,
        master,
        content_info: ContentInfo,
        on_download: Callable[[TorrentResult], None],
    ):
        super().__init__(master)
        self.content_info = content_info
        self.on_download = on_download
        self._results: list[TorrentResult] = []

        self.title("Torrent Alternatifleri")
        self.geometry("600x500")
        self.transient(master)
        self.grab_set()

        self._build()
        self._search()

        # Merkez
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - 600) // 2
        y = master.winfo_y() + (master.winfo_height() - 500) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self) -> None:
        # Başlık
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text="🔍 Torrent Alternatifleri",
            font=theme.FONT_SUBTITLE,
        ).pack(side="left")

        # İçerik bilgisi
        info_text = self.content_info.name
        if self.content_info.year:
            info_text += f" ({self.content_info.year})"
        ctk.CTkLabel(
            self,
            text=f"Aranan: {info_text}",
            font=theme.FONT_BODY,
            text_color=theme.COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 5))

        ctk.CTkLabel(
            self,
            text=(
                "ℹ Bu içerik doğrudan indirilemedi.\n"
                "Aşağıdaki torrent alternatifleri bulundu:"
            ),
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_WARNING,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Loading
        self.loading_label = ctk.CTkLabel(
            self, text="⏳ Aranıyor...", font=theme.FONT_BODY
        )
        self.loading_label.pack(pady=20)

        self.progress_bar = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress_bar.pack(padx=20, fill="x")
        self.progress_bar.start()

        # Sonuç listesi (başta gizli)
        self.results_frame = ctk.CTkScrollableFrame(self, label_text="Sonuçlar")
        # pack() sonradan çağrılacak

        # Butonlar
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(10, 20), side="bottom")
        ctk.CTkButton(btn_frame, text="Kapat", command=self.destroy).pack(side="right")

    def _search(self) -> None:
        """Background'da torrent ara."""
        def task():
            results = search_all(
                query=self.content_info.name,
                year=self.content_info.year,
                season=self.content_info.season,
                episode=self.content_info.episode,
                content_type=self.content_info.content_type,
            )
            self.after(0, lambda: self._show_results(results))

        threading.Thread(target=task, daemon=True).start()

    def _show_results(self, results: list[TorrentResult]) -> None:
        """Sonuçları göster."""
        self.loading_label.destroy()
        self.progress_bar.stop()
        self.progress_bar.destroy()

        if not results:
            ctk.CTkLabel(
                self,
                text="❌ Torrent bulunamadı.\nFarklı bir arama terimi deneyin.",
                font=theme.FONT_BODY,
                text_color=theme.COLOR_ERROR,
            ).pack(pady=20)
            return

        self.results_frame.pack(
            fill="both", expand=True, padx=20, pady=(0, 10)
        )

        for result in results:
            self._add_result_row(result)

    def _add_result_row(self, result: TorrentResult) -> None:
        """Tek bir torrent sonucu satırı."""
        row = ctk.CTkFrame(
            self.results_frame,
            fg_color=theme.COLOR_BG_SECONDARY,
            corner_radius=theme.CORNER_RADIUS,
        )
        row.pack(fill="x", padx=5, pady=4)

        # Sol: Bilgiler
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        # Başlık
        title_short = result.title[:50] + "..." if len(result.title) > 50 else result.title
        ctk.CTkLabel(
            info, text=title_short,
            font=theme.FONT_BODY,
            anchor="w",
        ).pack(anchor="w")

        # Meta
        meta_parts = [
            f"🎬 {result.quality}",
            f"💾 {result.size_formatted()}",
            f"🌱 {result.seeds} seed",
            f"[{result.source}]",
        ]
        ctk.CTkLabel(
            info,
            text="  ".join(meta_parts),
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

        # Sağ: İndir butonu
        ctk.CTkButton(
            row,
            text="⬇ İndir",
            width=80,
            command=lambda r=result: self._start_download(r),
            fg_color=theme.COLOR_ACCENT,
            hover_color=theme.COLOR_ACCENT_HOVER,
        ).pack(side="right", padx=10, pady=8)

    def _start_download(self, result: TorrentResult) -> None:
        """İndirme başlat."""
        self.destroy()
        self.on_download(result)
```

## Görev 7: `desktop/app.py` — Akıllı Fallback Entegrasyonu

`_on_fetch` ve `_on_download` metodlarını güncelle.

### `_on_extract_error` güncelleme:

```python
from core.torrent import detect_from_url, search_all
from core.exceptions import InvalidURLError, VideoUnavailableError
from desktop.ui.torrent_results import TorrentResultsDialog
from desktop.workers.download_worker import TorrentDownloadWorker

def _on_extract_error(self, error: Exception, url: str) -> None:
    """Bilgi alma hatası — torrent alternatifi öner."""
    friendly = humanize_error(str(error))

    # URL'yi analiz et
    content_info = detect_from_url(url)

    if content_info.name:
        # İçerik adı bulunduysa torrent dialog'u göster
        def on_torrent_download(result):
            self._start_torrent_download(result, content_info)

        dialog = TorrentResultsDialog(
            self,
            content_info=content_info,
            on_download=on_torrent_download,
        )
    else:
        # İçerik adı bulunamadıysa normal hata göster
        from desktop.ui.error_dialog import ErrorDialog
        ErrorDialog(self, friendly, on_open_settings=self._open_cookies_settings)
```

### `_start_torrent_download` yeni metod:

```python
def _start_torrent_download(
    self,
    result: TorrentResult,
    content_info: ContentInfo,
) -> None:
    """Torrent indirme başlat."""
    from pathlib import Path
    from core.torrent import TorrentDownloader, TorrentProgress, auto_subtitle
    from desktop.ui.download_item import DownloadItem
    from desktop.utils.threading_helper import run_on_ui
    import threading

    output_dir = Path(self.config_obj.download_dir) / "torrents"
    downloader = TorrentDownloader(output_dir)

    # İndirme item oluştur
    item = DownloadItem(
        self.download_list,
        title=f"[Torrent] {result.title} {result.quality}",
        on_cancel=downloader.cancel,
    )
    self.download_list.add_item(item)

    def on_progress(progress: TorrentProgress) -> None:
        run_on_ui(self, lambda: item.update_torrent_progress(progress))

    def task():
        try:
            # Torrenti indir
            magnet = result.magnet or ""
            torrent_url = result.torrent_url or ""

            if magnet:
                video_path = downloader.download_magnet(magnet, on_progress)
            elif torrent_url:
                video_path = downloader.download_torrent_file(torrent_url, on_progress)
            else:
                raise Exception("Magnet veya torrent URL bulunamadı")

            if video_path is None:
                raise Exception("İndirme başarısız")

            # Altyazı indir
            run_on_ui(self, lambda: item.set_status_text("Altyazı aranıyor..."))
            subtitles = auto_subtitle(
                title=content_info.name,
                video_path=video_path,
                year=content_info.year,
                imdb_id=result.imdb_id,
                languages=self.config_obj.subtitle_languages,
            )

            run_on_ui(self, lambda: item.mark_complete(video_path))

            if subtitles:
                run_on_ui(self, lambda: item.set_status_text(
                    f"✓ Tamamlandı + {len(subtitles)} altyazı"
                ))
        except Exception as e:
            run_on_ui(self, lambda: item.mark_error(e))

    threading.Thread(target=task, daemon=True).start()
```

## Görev 8: `desktop/config.py` — API Key Ekle

```python
@dataclass
class AppConfig:
    # ... mevcut alanlar ...
    opensubtitles_api_key: str = ""  # ← YENİ
    tmdb_api_key: str = ""           # ← YENİ (ilerisi için)
```

Ve `desktop/ui/settings_window.py`'a yeni sekme:

```python
# "Genel", "İndirme", "Cookies & Login", "Torrent & Altyazı"
self.tabs.add("Torrent & Altyazı")
self._build_torrent_tab(self.tabs.tab("Torrent & Altyazı"))

def _build_torrent_tab(self, parent) -> None:
    ctk.CTkLabel(parent, text="OpenSubtitles API Key:").pack(anchor="w", padx=10, pady=(10,2))
    self.os_key_entry = ctk.CTkEntry(parent, placeholder_text="API Key girin...")
    self.os_key_entry.pack(fill="x", padx=10, pady=(0,10))
    self.os_key_entry.insert(0, self.config_obj.opensubtitles_api_key)
    
    ctk.CTkLabel(
        parent,
        text="ℹ OpenSubtitles API Key için: https://www.opensubtitles.com/en/consumers",
        font=theme.FONT_SMALL,
        text_color=theme.COLOR_TEXT_MUTED,
    ).pack(anchor="w", padx=10)
```

## Görev 9: `core/torrent/` için Environment Variable

`backend/.env` veya sistem environment'a ekle:

```bash
OPENSUBTITLES_API_KEY=senin_key_buraya
```

Desktop için ise config üzerinden `AppConfig.opensubtitles_api_key` → `os.environ`'a set edilir.

`desktop/app.py` başına ekle:

```python
# OpenSubtitles key'ini environment'a set et
import os
os.environ["OPENSUBTITLES_API_KEY"] = self.config_obj.opensubtitles_api_key
```

## Kabul Kriterleri

1. ✅ Dizipal URL'si yapıştırınca yt-dlp dener, başarısız olunca torrent dialog'u açılır
2. ✅ Dialog'da film adı doğru çıkarılmış görünür
3. ✅ YTS'den film sonuçları gelir (seed sayısı, boyut, kalite)
4. ✅ EZTV'den dizi sonuçları gelir
5. ✅ "İndir" butonuna basınca indirme listesine eklenir, progress görünür
6. ✅ İndirme bittikten sonra aynı klasörde `.tr.srt` veya `.en.srt` altyazı var
7. ✅ İptal butonu çalışır (torrent durdurulur)
8. ✅ OpenSubtitles API key ayarlar sekmesinden girilebilir
9. ✅ Normal URL'ler (Twitter, TikTok) hâlâ eskisi gibi çalışır (regression yok)

## Test Senaryoları

**Test 1 — Dizipal film URL'si:**
- `https://dizipal.com/film/oppenheimer-2023/` yapıştır
- Bilgi Al → torrent dialog açılır
- Film adı "Oppenheimer" görünür, YTS sonuçları gelir

**Test 2 — Dizi URL'si:**
- `https://dizipal.com/dizi/breaking-bad/sezon-1/bolum-1/` yapıştır
- EZTV'den dizi sonuçları gelir

**Test 3 — Altyazı:**
- Test 1'deki indirme bittikten sonra
- `~/Downloads/VideoDownloader/torrents/Oppenheimer.*/` klasörüne bak
- `.tr.srt` veya `.en.srt` dosyası var mı?

**Test 4 — Desteklenen URL (regression):**
- Twitter URL'si yapıştır → normal gibi çalışmalı, torrent dialog çıkmamalı

## Önemli Notlar

**libtorrent kurulum sorunu:**
Windows'ta bazen pip ile kurulmaz. Bu durumda:
1. https://www.lfd.uci.edu/~gohlke/pythonlibs/#libtorrent
2. Python versiyonuna uygun .whl indir
3. `pip install indirilendosya.whl`

**YTS sadece film:** EZTV sadece dizi. İkisi birden olunca `content_type="unknown"` için her ikisinde de arar.

**Seed sayısı 0 ise:** Torrent ölü olabilir. Kullanıcıya uyarı ver.

**OpenSubtitles rate limit:** Ücretsiz tier günde 20 indirme. Aşılırsa "Altyazı indirilemedi" göster, devam et.

**Altyazı senkron sorunu:** Torrent altyazıları genelde video ile senkronize. Sorun yaşanırsa `SubEdit` veya `Subtitle Edit` gibi araç önerilebilir.
