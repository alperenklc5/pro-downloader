# Faz 2.11 Fix 1: Jackett Entegrasyonu

## Sorun
YTS ve EZTV API'leri Türkiye'de BTK tarafından engelli.
Jackett VPS'te kurulu ve çalışıyor (62 sonuç döndü test'te).

## Çözüm
`core/torrent/searcher.py` içindeki YTS/EZTV API'lerini Jackett API ile değiştir.

## Görev 1: `core/torrent/searcher.py` — Tamamen Değiştir

```python
"""Jackett API üzerinden torrent arar.

Jackett VPS'te çalışır (http://164.68.113.20:9117),
500+ torrent sitesini tek API'den sorgular.
Türkiye BTK engelinden etkilenmez.
"""
from __future__ import annotations

import os
import requests
from dataclasses import dataclass, field

REQUEST_TIMEOUT = 30

# Jackett kategorileri
CATEGORY_MOVIES = [2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060]
CATEGORY_TV = [5000, 5010, 5020, 5030, 5040, 5045, 5050, 5060, 5070, 5080]
CATEGORY_ALL = CATEGORY_MOVIES + CATEGORY_TV


@dataclass
class TorrentResult:
    """Tek bir torrent sonucu."""
    title: str
    quality: str
    size_bytes: int
    seeds: int
    peers: int
    magnet: str
    torrent_url: str
    source: str           # Indexer adı (YTS, 1337x, RARBG, vb.)
    year: int | None = None
    imdb_id: str | None = None
    poster: str | None = None
    category: str = "unknown"  # "movie" veya "series"

    def size_formatted(self) -> str:
        gb = self.size_bytes / (1024 ** 3)
        if gb >= 1:
            return f"{gb:.1f} GB"
        mb = self.size_bytes / (1024 ** 2)
        return f"{mb:.0f} MB"


def _get_jackett_config() -> tuple[str, str]:
    """Jackett URL ve API key'i al."""
    url = os.getenv("JACKETT_URL", "http://164.68.113.20:9117")
    key = os.getenv("JACKETT_API_KEY", "")
    return url, key


def _jackett_search(
    query: str,
    categories: list[int],
    jackett_url: str | None = None,
    jackett_key: str | None = None,
) -> list[dict]:
    """Jackett API'ye ham sorgu at."""
    if jackett_url is None or jackett_key is None:
        jackett_url, jackett_key = _get_jackett_config()

    if not jackett_key:
        return []

    try:
        params = {
            "apikey": jackett_key,
            "Query": query,
            "Category[]": categories,
        }

        resp = requests.get(
            f"{jackett_url}/api/v2.0/indexers/all/results",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("Results", [])

    except Exception as e:
        return []


def _parse_result(item: dict, category: str = "unknown") -> TorrentResult:
    """Jackett sonucunu TorrentResult'a çevir."""
    title = item.get("Title", "")
    size = item.get("Size", 0) or 0
    seeds = item.get("Seeders", 0) or 0
    peers = item.get("Peers", 0) or 0
    magnet = item.get("MagnetUri", "") or ""
    torrent_url = item.get("Link", "") or ""
    source = item.get("Tracker", "Unknown")

    # IMDB ID
    imdb_id = None
    if item.get("Imdb"):
        imdb_id = f"tt{item['Imdb']:07d}"

    # Yıl
    year = None
    pub_date = item.get("PublishDate", "")
    if pub_date:
        try:
            year = int(pub_date[:4])
        except (ValueError, TypeError):
            pass

    return TorrentResult(
        title=title,
        quality=_detect_quality(title),
        size_bytes=int(size),
        seeds=seeds,
        peers=peers,
        magnet=magnet,
        torrent_url=torrent_url,
        source=source,
        year=year,
        imdb_id=imdb_id,
        category=category,
    )


def search_movies(
    query: str,
    year: int | None = None,
    jackett_url: str | None = None,
    jackett_key: str | None = None,
) -> list[TorrentResult]:
    """Film torrenti ara."""
    search_query = f"{query} {year}" if year else query
    items = _jackett_search(
        search_query,
        CATEGORY_MOVIES,
        jackett_url,
        jackett_key,
    )

    results = [_parse_result(item, "movie") for item in items]
    # Seed sayısına göre sırala, en az 1 seed olanları al
    results = [r for r in results if r.seeds > 0]
    return sorted(results, key=lambda r: r.seeds, reverse=True)[:20]


def search_series(
    query: str,
    season: int | None = None,
    episode: int | None = None,
    jackett_url: str | None = None,
    jackett_key: str | None = None,
) -> list[TorrentResult]:
    """Dizi torrenti ara."""
    search_query = query
    if season and episode:
        search_query += f" S{season:02d}E{episode:02d}"
    elif season:
        search_query += f" Season {season}"

    items = _jackett_search(
        search_query,
        CATEGORY_TV,
        jackett_url,
        jackett_key,
    )

    results = [_parse_result(item, "series") for item in items]
    results = [r for r in results if r.seeds > 0]
    return sorted(results, key=lambda r: r.seeds, reverse=True)[:20]


def search_all(
    query: str,
    year: int | None = None,
    season: int | None = None,
    episode: int | None = None,
    content_type: str = "unknown",
    jackett_url: str | None = None,
    jackett_key: str | None = None,
) -> list[TorrentResult]:
    """Film ve/veya dizi ara."""
    # content_type'a göre hangi kategorilerde arama yapacağımızı belirle
    if content_type == "movie":
        categories = CATEGORY_MOVIES
        search_query = f"{query} {year}" if year else query
    elif content_type == "series":
        categories = CATEGORY_TV
        search_query = query
        if season and episode:
            search_query += f" S{season:02d}E{episode:02d}"
        elif season:
            search_query += f" Season {season}"
    else:
        # Bilinmiyor — her iki kategoride ara
        categories = CATEGORY_ALL
        search_query = f"{query} {year}" if year else query

    items = _jackett_search(
        search_query,
        categories,
        jackett_url,
        jackett_key,
    )

    results = []
    for item in items:
        cat = "movie" if any(
            item.get("Category", []) and c in CATEGORY_MOVIES
            for c in (item.get("Category") or [])
        ) else "series"
        results.append(_parse_result(item, cat))

    # Seed > 0, sırala
    results = [r for r in results if r.seeds > 0]
    return sorted(results, key=lambda r: r.seeds, reverse=True)[:20]


def _detect_quality(title: str) -> str:
    """Torrent başlığından kalite bilgisini çıkar."""
    title_lower = title.lower()
    for q in ["4k", "2160p", "1080p", "720p", "480p", "360p"]:
        if q in title_lower:
            return q.upper() if q == "4k" else q
    if "bluray" in title_lower or "blu-ray" in title_lower:
        return "BluRay"
    if "webrip" in title_lower or "web-rip" in title_lower:
        return "WEBRip"
    if "webdl" in title_lower or "web-dl" in title_lower:
        return "WEB-DL"
    if "hdtv" in title_lower:
        return "HDTV"
    return "?"
```

## Görev 2: `desktop/config.py` — Jackett Ayarları Ekle

```python
@dataclass
class AppConfig:
    # ... mevcut alanlar ...
    opensubtitles_api_key: str = ""
    tmdb_api_key: str = ""
    jackett_url: str = "http://164.68.113.20:9117"   # ← YENİ
    jackett_api_key: str = ""                          # ← YENİ
```

## Görev 3: `desktop/app.py` — Environment Variables Set Et

App başlatılırken Jackett config'i environment'a yaz:

```python
# App.__init__ içinde
import os
os.environ["JACKETT_URL"] = self.config_obj.jackett_url
os.environ["JACKETT_API_KEY"] = self.config_obj.jackett_api_key
os.environ["OPENSUBTITLES_API_KEY"] = self.config_obj.opensubtitles_api_key
```

## Görev 4: `desktop/ui/settings_window.py` — Jackett Ayarları UI

"Torrent & Altyazı" sekmesine Jackett ayarları ekle:

```python
def _build_torrent_tab(self, parent) -> None:
    # Jackett bölümü
    ctk.CTkLabel(
        parent,
        text="Jackett Ayarları",
        font=theme.FONT_SUBTITLE,
    ).pack(anchor="w", padx=10, pady=(15, 5))

    ctk.CTkLabel(parent, text="Jackett URL:").pack(anchor="w", padx=10, pady=(5, 2))
    self.jackett_url_entry = ctk.CTkEntry(
        parent, placeholder_text="http://164.68.113.20:9117"
    )
    self.jackett_url_entry.pack(fill="x", padx=10, pady=(0, 8))
    self.jackett_url_entry.insert(0, self.config_obj.jackett_url)

    ctk.CTkLabel(parent, text="Jackett API Key:").pack(anchor="w", padx=10, pady=(5, 2))
    self.jackett_key_entry = ctk.CTkEntry(
        parent, placeholder_text="Jackett API key..."
    )
    self.jackett_key_entry.pack(fill="x", padx=10, pady=(0, 8))
    self.jackett_key_entry.insert(0, self.config_obj.jackett_api_key)

    # Separator
    ctk.CTkFrame(parent, height=1, fg_color=theme.COLOR_TEXT_MUTED).pack(
        fill="x", padx=10, pady=10
    )

    # OpenSubtitles bölümü
    ctk.CTkLabel(
        parent,
        text="Altyazı Ayarları",
        font=theme.FONT_SUBTITLE,
    ).pack(anchor="w", padx=10, pady=(5, 5))

    ctk.CTkLabel(parent, text="OpenSubtitles API Key:").pack(
        anchor="w", padx=10, pady=(5, 2)
    )
    self.os_key_entry = ctk.CTkEntry(
        parent, placeholder_text="OpenSubtitles API Key..."
    )
    self.os_key_entry.pack(fill="x", padx=10, pady=(0, 8))
    self.os_key_entry.insert(0, self.config_obj.opensubtitles_api_key)

    ctk.CTkLabel(
        parent,
        text=(
            "ℹ OpenSubtitles: https://www.opensubtitles.com/en/consumers\n"
            "ℹ Jackett: VPS'te http://164.68.113.20:9117 adresinden API Key al"
        ),
        font=theme.FONT_SMALL,
        text_color=theme.COLOR_TEXT_MUTED,
        justify="left",
    ).pack(anchor="w", padx=10, pady=(0, 10))

# _save() metoduna ekle:
def _save(self) -> None:
    # ... mevcut kaydetmeler ...
    self.config_obj.jackett_url = self.jackett_url_entry.get()
    self.config_obj.jackett_api_key = self.jackett_key_entry.get()
    self.config_obj.opensubtitles_api_key = self.os_key_entry.get()
    self.config_obj.save()
    self.on_save()
    self.destroy()
```

## Görev 5: `desktop/app.py` — Torrent Search'e Jackett Config Geçir

`_on_extract_error` içinde TorrentResultsDialog'a jackett config geçir:

```python
def _on_extract_error(self, error: Exception, url: str) -> None:
    friendly = humanize_error(str(error))
    content_info = detect_from_url(url)

    if content_info.name:
        def on_torrent_download(result):
            self._start_torrent_download(result, content_info)

        dialog = TorrentResultsDialog(
            self,
            content_info=content_info,
            on_download=on_torrent_download,
            jackett_url=self.config_obj.jackett_url,      # ← YENİ
            jackett_key=self.config_obj.jackett_api_key,  # ← YENİ
        )
    else:
        from desktop.ui.error_dialog import ErrorDialog
        ErrorDialog(self, friendly, on_open_settings=self._open_cookies_settings)
```

## Görev 6: `desktop/ui/torrent_results.py` — Jackett Config Al

```python
class TorrentResultsDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        content_info: ContentInfo,
        on_download: Callable[[TorrentResult], None],
        jackett_url: str = "",    # ← YENİ
        jackett_key: str = "",    # ← YENİ
    ):
        super().__init__(master)
        self.content_info = content_info
        self.on_download = on_download
        self.jackett_url = jackett_url  # ← YENİ
        self.jackett_key = jackett_key  # ← YENİ
        # ...

    def _search(self) -> None:
        def task():
            results = search_all(
                query=self.content_info.name,
                year=self.content_info.year,
                season=self.content_info.season,
                episode=self.content_info.episode,
                content_type=self.content_info.content_type,
                jackett_url=self.jackett_url,  # ← YENİ
                jackett_key=self.jackett_key,  # ← YENİ
            )
            self.after(0, lambda: self._show_results(results))

        threading.Thread(target=task, daemon=True).start()
```

## Kabul Kriterleri

1. ✅ Ayarlar → Torrent & Altyazı → Jackett URL ve Key girilebiliyor
2. ✅ Dizipal URL yapıştırınca torrent dialog açılıyor
3. ✅ Dialog'da Jackett sonuçları geliyor (seed sayısı, boyut, kaynak)
4. ✅ "İndir" basınca libtorrent ile indirme başlıyor
5. ✅ İndirme bitince altyazı otomatik ekleniyor

## Test

Uygulamayı başlatmadan önce Jackett key'ini ayarlara gir:
- **Jackett URL:** `http://164.68.113.20:9117`
- **Jackett API Key:** (Jackett arayüzünden al)
- **OpenSubtitles API Key:** `PmXAGNbhYtkH2qITQxIzRwouYDsjXXqm`

Kaydet → Uygulamayı yeniden başlat → Dizipal URL dene.
