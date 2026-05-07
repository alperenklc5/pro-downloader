"""Asenkron indirme görevi."""
from pathlib import Path
from datetime import datetime
import logging

from backend.tasks.celery_app import celery_app
from backend.storage.task_store import TaskStore
from backend.storage.file_manager import FileManager
from backend.config import settings
from core import Downloader, DownloadOptions, ProgressInfo
from core.auth import CookieConfig
from core.exceptions import DownloaderError, AuthenticationRequiredError
from core.error_messages import humanize_error


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="backend.tasks.download_task.download_video")
def download_video(self, task_id: str, url: str, options_dict: dict) -> dict:
    """Video indirme görevi.

    Args:
        task_id: Görev ID'si (TaskStore key)
        url: Video URL'si
        options_dict: DownloadRequest'ten gelen opsiyonlar

    Returns:
        Sonuç dict (TaskStore'da da güncel tutulur)
    """
    logger.info(f"İndirme başlıyor: task_id={task_id}, url={url}")

    # Görev metadata güncelle
    TaskStore.update(task_id, status="downloading")

    # Cookie config (sadece manuel dosya, browser yok)
    cookies = CookieConfig()
    if settings.cookies_file and settings.cookies_file.exists():
        cookies = CookieConfig(
            mode="file",
            file_path=settings.cookies_file,
        )

    # Download options
    options = DownloadOptions(
        output_dir=FileManager.get_task_dir(task_id),
        quality=options_dict.get("quality", "720p"),
        audio_only=options_dict.get("audio_only", False),
        audio_format=options_dict.get("audio_format", "mp3"),
        video_format=options_dict.get("video_format", "mp4"),
        embed_thumbnail=options_dict.get("embed_thumbnail", True),
        embed_metadata=options_dict.get("embed_metadata", True),
        embed_subtitles=options_dict.get("embed_subtitles", False),
        subtitle_languages=options_dict.get("subtitle_languages", ["en", "tr"]),
        rate_limit=settings.download_rate_limit,
        cookies=cookies,
    )

    # Progress callback (Redis'e yaz)
    def progress_callback(info: ProgressInfo) -> None:
        TaskStore.update(
            task_id,
            progress_percent=info.percent,
            downloaded_bytes=info.downloaded_bytes,
            total_bytes=info.total_bytes,
            speed_bytes_per_sec=info.speed,
            eta_seconds=info.eta,
            filename=info.filename,
        )

    try:
        downloader = Downloader(options)
        downloaded_path = downloader.download(url, progress_callback=progress_callback)

        # Başarılı
        file_size = downloaded_path.stat().st_size
        TaskStore.update(
            task_id,
            status="completed",
            progress_percent=100.0,
            filename=downloaded_path.name,
            file_size_bytes=file_size,
            completed_at=datetime.now().isoformat(),
        )

        logger.info(f"İndirme tamamlandı: task_id={task_id}, size={file_size}")
        return {"success": True, "task_id": task_id, "filename": downloaded_path.name}

    except DownloaderError as e:
        friendly = humanize_error(str(e))
        error_msg = f"{friendly.title}: {friendly.message}"
        TaskStore.update(
            task_id,
            status="failed",
            error_message=error_msg,
            completed_at=datetime.now().isoformat(),
        )
        FileManager.cleanup_task(task_id)
        logger.error(f"İndirme başarısız: task_id={task_id}, error={error_msg}")
        return {"success": False, "task_id": task_id, "error": error_msg}

    except Exception as e:
        TaskStore.update(
            task_id,
            status="failed",
            error_message=f"Beklenmeyen hata: {e}",
            completed_at=datetime.now().isoformat(),
        )
        FileManager.cleanup_task(task_id)
        logger.exception(f"İndirme'de beklenmeyen hata: task_id={task_id}")
        return {"success": False, "task_id": task_id, "error": str(e)}


@celery_app.task(name="backend.tasks.download_task.cleanup_task")
def cleanup_task() -> dict:
    """Periyodik dosya temizleme."""
    result = FileManager.cleanup_old_files()
    logger.info(f"Cleanup tamamlandı: {result}")
    return result
