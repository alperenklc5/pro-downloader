"""OpenSubtitles API ile altyazı arama ve indirme.

API key AppConfig üzerinden yönetilir; fonksiyonlara parametre olarak geçilir.
"""
from __future__ import annotations

from pathlib import Path

import requests

OPENSUBTITLES_BASE = "https://api.opensubtitles.com/api/v1"
REQUEST_TIMEOUT = 10


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Api-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "ProDownloader v1.0",
    }


def search_subtitle(
    title: str,
    api_key: str,
    year: int | None = None,
    imdb_id: str | None = None,
    language: str = "tr",
) -> list[dict]:
    """Altyazı ara.

    Returns: Bulunan altyazıların listesi (file_id, filename, download_count)
    """
    if not api_key:
        return []

    params: dict = {"languages": language, "type": "movie"}

    if imdb_id:
        params["imdb_id"] = imdb_id.replace("tt", "")
    else:
        params["query"] = title
        if year:
            params["year"] = year

    try:
        resp = requests.get(
            f"{OPENSUBTITLES_BASE}/subtitles",
            headers=_headers(api_key),
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

        return sorted(results, key=lambda x: x["downloads"], reverse=True)

    except Exception:
        return []


def download_subtitle(
    file_id: int,
    output_path: Path,
    api_key: str,
) -> bool:
    """Altyazıyı indir ve output_path'e kaydet.

    Returns: Başarılı mı?
    """
    if not api_key:
        return False

    try:
        resp = requests.post(
            f"{OPENSUBTITLES_BASE}/download",
            headers=_headers(api_key),
            json={"file_id": file_id},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        download_url = resp.json().get("link")

        if not download_url:
            return False

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
    api_key: str,
    year: int | None = None,
    imdb_id: str | None = None,
    languages: list[str] | None = None,
) -> list[Path]:
    """Film için altyazıları otomatik bul ve indir.

    Önce Türkçe, yoksa İngilizce dener.
    Returns: İndirilen altyazı dosyalarının listesi
    """
    if not api_key:
        return []

    if languages is None:
        languages = ["tr", "en"]

    downloaded: list[Path] = []
    video_stem = video_path.stem

    for lang in languages:
        subtitles = search_subtitle(title, api_key, year, imdb_id, lang)
        if not subtitles:
            continue

        best = subtitles[0]
        ext = Path(best["filename"]).suffix or ".srt"
        output_path = video_path.parent / f"{video_stem}.{lang}{ext}"

        success = download_subtitle(best["file_id"], output_path, api_key)
        if success:
            downloaded.append(output_path)

    return downloaded
