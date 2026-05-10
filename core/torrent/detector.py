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
