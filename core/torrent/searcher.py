"""Jackett API üzerinden torrent arar.

Jackett VPS'te çalışır, 500+ torrent sitesini tek API'den sorgular.
Türkiye BTK engelinden etkilenmez.
API key AppConfig üzerinden yönetilir; fonksiyonlara parametre olarak geçilir.
"""
from __future__ import annotations

import requests
from dataclasses import dataclass

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
    source: str           # Indexer adı (1337x, RARBG, vb.)
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


def _jackett_search(
    query: str,
    categories: list[int],
    jackett_url: str,
    jackett_key: str,
) -> list[dict]:
    """Jackett API'ye ham sorgu at."""
    if not jackett_url or not jackett_key:
        return []

    try:
        resp = requests.get(
            f"{jackett_url}/api/v2.0/indexers/all/results",
            params={
                "apikey": jackett_key,
                "Query": query,
                "Category[]": categories,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("Results", [])

    except Exception:
        return []


def _parse_result(item: dict) -> TorrentResult:
    """Jackett sonucunu TorrentResult'a çevir."""
    title = item.get("Title", "")
    size = item.get("Size", 0) or 0
    seeds = item.get("Seeders", 0) or 0
    peers = item.get("Peers", 0) or 0
    magnet = item.get("MagnetUri", "") or ""
    torrent_url = item.get("Link", "") or ""
    source = item.get("Tracker", "Unknown")

    imdb_id = None
    if item.get("Imdb"):
        imdb_id = f"tt{item['Imdb']:07d}"

    year = None
    pub_date = item.get("PublishDate", "")
    if pub_date:
        try:
            year = int(pub_date[:4])
        except (ValueError, TypeError):
            pass

    # Category: Jackett bazen int, bazen list[int] döndürür — normalize et
    raw_cat = item.get("Category", [])
    if isinstance(raw_cat, int):
        item_cats = [raw_cat]
    elif isinstance(raw_cat, list):
        item_cats = raw_cat
    else:
        item_cats = []
    category = "movie" if any(c in CATEGORY_MOVIES for c in item_cats) else "series"

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
    jackett_url: str = "",
    jackett_key: str = "",
) -> list[TorrentResult]:
    """Film torrenti ara."""
    search_query = f"{query} {year}" if year else query
    items = _jackett_search(search_query, CATEGORY_MOVIES, jackett_url, jackett_key)
    results = [_parse_result(item) for item in items]
    results = [r for r in results if r.seeds > 0]
    return sorted(results, key=lambda r: r.seeds, reverse=True)[:100]


def search_series(
    query: str,
    season: int | None = None,
    episode: int | None = None,
    jackett_url: str = "",
    jackett_key: str = "",
) -> list[TorrentResult]:
    """Dizi torrenti ara."""
    search_query = query
    if season and episode:
        search_query += f" S{season:02d}E{episode:02d}"
    elif season:
        search_query += f" Season {season}"

    items = _jackett_search(search_query, CATEGORY_TV, jackett_url, jackett_key)
    results = [_parse_result(item) for item in items]
    results = [r for r in results if r.seeds > 0]
    return sorted(results, key=lambda r: r.seeds, reverse=True)[:100]


def search_all(
    query: str,
    year: int | None = None,
    season: int | None = None,
    episode: int | None = None,
    content_type: str = "unknown",
    jackett_url: str = "",
    jackett_key: str = "",
) -> list[TorrentResult]:
    """Film ve/veya dizi ara."""
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
        categories = CATEGORY_ALL
        search_query = f"{query} {year}" if year else query

    items = _jackett_search(search_query, categories, jackett_url, jackett_key)
    results = [_parse_result(item) for item in items]
    results = [r for r in results if r.seeds > 0]
    return sorted(results, key=lambda r: r.seeds, reverse=True)[:100]


def _detect_quality(title: str) -> str:
    """Torrent başlığından kalite bilgisini çıkar."""
    t = title.lower()
    for q in ["4k", "2160p", "1080p", "720p", "480p", "360p"]:
        if q in t:
            return q.upper() if q == "4k" else q
    if "bluray" in t or "blu-ray" in t:
        return "BluRay"
    if "webrip" in t or "web-rip" in t:
        return "WEBRip"
    if "webdl" in t or "web-dl" in t:
        return "WEB-DL"
    if "hdtv" in t:
        return "HDTV"
    return "?"
