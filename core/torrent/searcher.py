"""YTS ve EZTV API'lerinden torrent arar."""
from __future__ import annotations

import requests
from dataclasses import dataclass, field

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

        return sorted(results, key=lambda r: r.seeds, reverse=True)

    except Exception:
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

            if query_lower not in title:
                continue

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

    except Exception:
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
