"""
Manuel test scripti.

Kullanım: python cli_test.py <url> [quality]
Örnek:    python cli_test.py https://youtu.be/dQw4w9WgXcQ 720p
          python cli_test.py https://youtu.be/dQw4w9WgXcQ audio
"""

import logging
import sys
from pathlib import Path

from core import Downloader, DownloadOptions, ProgressInfo, extract_info
from core.exceptions import DownloaderError

logging.basicConfig(level=logging.WARNING)


def progress_handler(info: ProgressInfo) -> None:
    """İlerleme bilgisini terminale yazar."""
    if info.status == "downloading":
        speed_mb = (info.speed / 1024 / 1024) if info.speed else 0.0
        eta = info.eta if info.eta is not None else "?"
        print(
            f"\r{info.percent:5.1f}% | {speed_mb:.2f} MB/s | ETA: {eta}s   ",
            end="",
            flush=True,
        )
    elif info.status == "finished":
        print(f"\n✓ Tamamlandı: {info.filename}")
    elif info.status == "error":
        print(f"\n✗ Hata: {info.filename}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else "best"

    print(f"Bilgi alınıyor: {url}")
    try:
        info = extract_info(url)
    except DownloaderError as exc:
        print(f"Hata: {exc}")
        sys.exit(1)

    print(f"Başlık  : {info.title}")
    print(f"Süre    : {info.duration}s")
    print(f"Kaynak  : {info.extractor}")
    print(f"Video fmt: {len(info.video_formats)} | Ses fmt: {len(info.audio_formats)}")

    output_dir = Path("./downloads")
    output_dir.mkdir(exist_ok=True)

    options = DownloadOptions(
        output_dir=output_dir,
        quality=quality,
        audio_only=(quality == "audio"),
    )

    downloader = Downloader(options)
    print(f"\nİndirme başlıyor (kalite: {quality})...")

    try:
        path = downloader.download(url, progress_callback=progress_handler)
        print(f"\nDosya: {path}")
    except DownloaderError as exc:
        print(f"\nHata: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
