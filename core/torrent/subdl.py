"""Subdl.com API ile altyazı arama ve indirme."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import requests

SUBDL_BASE = "https://api.subdl.com/api/v1"
SUBDL_DL_BASE = "https://dl.subdl.com"
REQUEST_TIMEOUT = 10


def search_subdl(
    title: str,
    api_key: str,
    imdb_id: str | None = None,
    season: int | None = None,
    episode: int | None = None,
    language: str = "TR",
    content_type: str = "movie",  # "movie" veya "tv"
) -> list[dict]:
    """Subdl API'de altyazı ara."""
    params: dict = {"api_key": api_key, "languages": language, "type": content_type}

    if imdb_id:
        params["imdb_id"] = imdb_id.replace("tt", "")
    else:
        params["film_name"] = title

    if season is not None:
        params["season_number"] = season
    if episode is not None:
        params["episode_number"] = episode

    try:
        r = requests.get(
            f"{SUBDL_BASE}/subtitles",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("subtitles", [])
    except Exception:
        return []


def download_subdl(
    subtitle_url: str,
    output_path: Path,
    season: int | None = None,
    episode: int | None = None,
) -> bool:
    """Subdl'den altyazıyı indir ve zip'ten doğru .srt çıkar."""
    try:
        url = f"{SUBDL_DL_BASE}{subtitle_url}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            srt_files = [n for n in z.namelist() if n.lower().endswith(".srt")]
            if not srt_files:
                return False

            if season and episode:
                pattern = f"S{season:02d}E{episode:02d}"
                matching = [n for n in srt_files if pattern.upper() in n.upper()]
                if not matching:
                    return False
                best = matching[0]
            else:
                best = max(srt_files, key=lambda n: z.getinfo(n).file_size)

            content = z.read(best).decode("utf-8", errors="ignore")

            # Özet/recap altyazısı doğrulaması
            content_lower = content[:500].lower()
            if any(kw in content_lower for kw in ["nceki b", "previously on", "recap", "last week"]):
                return False  # Özet altyazı, atla

            # Minimum altyazı kontrolü
            subtitle_count = content.count("-->")
            if subtitle_count < 30:
                return False

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content.encode("utf-8"))
            return True

    except Exception:
        return False


def parse_video_filename(filename: str) -> dict:
    """Video dosya adından title, season, episode çıkar.

    Örnekler:
    Game.of.Thrones.S03E07.1080p.mkv → {title: 'Game of Thrones', season: 3, episode: 7}
    Oppenheimer.2023.1080p.mkv → {title: 'Oppenheimer', year: 2023}
    """
    import re
    from pathlib import Path

    name = Path(filename).stem  # Uzantıyı kaldır

    # S03E07 pattern'i bul
    match = re.search(r'[Ss](\d+)[Ee](\d+)', name)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        title_part = name[:match.start()]
        title = re.sub(r'[._\-]', ' ', title_part).strip()
        title = re.sub(r'\s+', ' ', title).strip()
        return {
            'title': title,
            'season': season,
            'episode': episode,
            'content_type': 'tv',
        }

    # Yıl pattern'i bul (film)
    match = re.search(r'(19|20)\d{2}', name)
    if match:
        year = int(match.group())
        title_part = name[:match.start()]
        title = re.sub(r'[._\-]', ' ', title_part).strip()
        return {
            'title': title,
            'year': year,
            'content_type': 'movie',
        }

    # Hiçbiri yoksa tüm adı temizle
    title = re.sub(r'[._\-]', ' ', name).strip()
    return {'title': title, 'content_type': 'movie'}


def auto_subtitle_subdl(
    title: str,
    video_path: Path,
    api_key: str,
    imdb_id: str | None = None,
    season: int | None = None,
    episode: int | None = None,
    languages: list[str] | None = None,
    log_callback=None,
    content_type: str = "movie",  # "movie" veya "tv"
    opensubtitles_api_key: str = "",
) -> list[Path]:
    """Film/dizi için Subdl'den altyazı indir.

    log_callback: opsiyonel, str mesaj alır (UI log için)
    """
    if languages is None:
        languages = ["TR", "EN"]

    def log(msg: str):
        if log_callback:
            log_callback(msg)

    downloaded: list[Path] = []
    video_stem = video_path.stem

    for lang in languages:
        log(f"[Subdl] {lang} altyazı aranıyor: {title}")
        results = search_subdl(
            title=title,
            api_key=api_key,
            imdb_id=imdb_id,
            season=season,
            episode=episode,
            language=lang,
            content_type=content_type,
        )

        if not results:
            log(f"[Subdl] {lang} için altyazı bulunamadı")
            continue

        log(f"[Subdl] {len(results)} altyazı bulundu, deneniyor...")

        # Önce spesifik bölüm sonuçlarını, sonra diğerlerini sırala
        if season and episode:
            full_season = [r for r in results if r.get("full_season")]
            specific = [r for r in results if not r.get("full_season")]
            ordered = specific + full_season
        else:
            ordered = results

        output_path = video_path.parent / f"{video_stem}.{lang.lower()}.srt"
        lang_success = False

        for subtitle in ordered[:4]:
            subtitle_url = subtitle.get("url", "")
            if not subtitle_url:
                continue

            log(f"[Subdl] İndiriliyor: {output_path.name}")
            success = download_subdl(subtitle_url, output_path, season=season, episode=episode)

            if success:
                log(f"[Subdl] \u2713 {lang} altyazı indirildi: {output_path.name}")
                downloaded.append(output_path)
                lang_success = True
                break
            else:
                log(f"[Subdl] Bu altyazı uygun değil, sonraki deneniyor...")

        if not lang_success:
            log(f"[Subdl] \u2717 {lang} için uygun altyazı bulunamadı")

            # OpenSubtitles fallback
            if opensubtitles_api_key:
                from core.torrent.subtitle import search_subtitle, download_subtitle

                os_lang = lang.lower()  # "TR" → "tr"
                log(f"[OpenSubtitles] {lang} altyazı aranıyor: {title}")
                os_results = search_subtitle(
                    title=title,
                    api_key=opensubtitles_api_key,
                    imdb_id=imdb_id,
                    language=os_lang,
                )
                if os_results:
                    log(f"[OpenSubtitles] {len(os_results)} altyazı bulundu, deneniyor...")
                    for os_sub in os_results[:4]:
                        success = download_subtitle(
                            file_id=os_sub["file_id"],
                            output_path=output_path,
                            api_key=opensubtitles_api_key,
                        )
                        if success:
                            log(f"[OpenSubtitles] \u2713 {lang} altyazı indirildi: {output_path.name}")
                            downloaded.append(output_path)
                            break
                        else:
                            log(f"[OpenSubtitles] Bu altyazı uygun değil, sonraki deneniyor...")
                    else:
                        log(f"[OpenSubtitles] \u2717 {lang} için uygun altyazı bulunamadı")
                else:
                    log(f"[OpenSubtitles] {lang} için altyazı bulunamadı")

    return downloaded
