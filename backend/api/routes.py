"""API endpoint tanımları."""
import uuid
from pathlib import Path
import logging

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse

from backend.api.auth import verify_api_key
from backend.api.schemas import (
    ExtractRequest, DownloadRequest,
    VideoInfoResponse, FormatInfo,
    DownloadStartResponse, TaskProgressResponse,
    ErrorResponse, HealthResponse,
)
from backend.config import settings
from backend.storage.task_store import TaskStore
from backend.storage.file_manager import FileManager
from backend.tasks.celery_app import celery_app
from backend.tasks.download_task import download_video
from core import extract_info
from core.auth import CookieConfig
from core.exceptions import (
    DownloaderError, AuthenticationRequiredError,
    InvalidURLError, VideoUnavailableError, NetworkError,
)
from core.error_messages import humanize_error


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])


# === Health ===

@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Sistem sağlık kontrolü."""
    import yt_dlp
    import redis

    # Redis kontrolü
    redis_ok = False
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    # Celery worker sayısı
    worker_count = 0
    try:
        inspect = celery_app.control.inspect(timeout=2)
        active = inspect.active()
        if active:
            worker_count = len(active)
    except Exception:
        pass

    # Disk
    usage = FileManager.get_disk_usage()
    disk_free_gb = usage["disk_free_bytes"] / (1024 ** 3)

    overall = "ok" if (redis_ok and worker_count > 0) else "degraded"

    return HealthResponse(
        status=overall,
        version="1.0.0",
        yt_dlp_version=yt_dlp.version.__version__,
        redis_connected=redis_ok,
        celery_workers=worker_count,
        disk_free_gb=round(disk_free_gb, 2),
    )


# === Extract Info ===

@router.post(
    "/extract",
    response_model=VideoInfoResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def extract(
    req: ExtractRequest,
    api_key: str = Depends(verify_api_key),
):
    """Video bilgisi çek (indirmeden önce kullanılır)."""
    cookies = CookieConfig()
    if settings.cookies_file and settings.cookies_file.exists():
        cookies = CookieConfig(mode="file", file_path=settings.cookies_file)

    try:
        info = extract_info(req.url, cookies=cookies)

        return VideoInfoResponse(
            url=info.url,
            title=info.title,
            description=info.description,
            duration=info.duration,
            thumbnail=info.thumbnail,
            uploader=info.uploader,
            upload_date=info.upload_date,
            view_count=info.view_count,
            extractor=info.extractor,
            is_playlist=info.is_playlist,
            playlist_count=info.playlist_count,
            video_formats=[
                FormatInfo(
                    format_id=f.format_id,
                    ext=f.ext,
                    resolution=f.resolution,
                    fps=f.fps,
                    filesize=f.filesize,
                    has_audio=f.has_audio,
                    has_video=f.has_video,
                ) for f in info.video_formats
            ],
            audio_formats=[
                FormatInfo(
                    format_id=f.format_id,
                    ext=f.ext,
                    resolution=None,
                    fps=None,
                    filesize=f.filesize,
                    has_audio=True,
                    has_video=False,
                ) for f in info.audio_formats
            ],
        )
    except InvalidURLError:
        raise HTTPException(status_code=400, detail="Geçersiz veya desteklenmeyen URL.")
    except VideoUnavailableError as e:
        raise HTTPException(status_code=404, detail=f"Video erişilemez: {e}")
    except AuthenticationRequiredError as e:
        raise HTTPException(status_code=401, detail=f"Login gerekli: {e}")
    except NetworkError as e:
        raise HTTPException(status_code=502, detail=f"Ağ hatası: {e}")
    except DownloaderError as e:
        friendly = humanize_error(str(e))
        raise HTTPException(status_code=500, detail=friendly.message)


# === Download Start ===

@router.post(
    "/download",
    response_model=DownloadStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_download(
    req: DownloadRequest,
    api_key: str = Depends(verify_api_key),
):
    """İndirme görevi başlat. Asenkron — task_id döner."""
    task_id = uuid.uuid4().hex

    # Önce video info çek (validation), beklemeden
    cookies = CookieConfig()
    if settings.cookies_file and settings.cookies_file.exists():
        cookies = CookieConfig(mode="file", file_path=settings.cookies_file)

    try:
        info = extract_info(req.url, cookies=cookies, timeout=15)

        # Süre limiti kontrolü
        if info.duration and info.duration > settings.max_video_duration_seconds:
            raise HTTPException(
                status_code=400,
                detail=f"Video çok uzun ({info.duration}s). Max: {settings.max_video_duration_seconds}s",
            )

        title = info.title
    except HTTPException:
        raise
    except (InvalidURLError, VideoUnavailableError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DownloaderError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Görev oluştur
    TaskStore.create(
        task_id=task_id,
        url=req.url,
        options=req.model_dump(),
    )
    TaskStore.update(task_id, title=title)

    # Celery'e at
    download_video.apply_async(
        args=[task_id, req.url, req.model_dump()],
        task_id=task_id,
    )

    logger.info(f"Görev kuyruğa alındı: task_id={task_id}, url={req.url}")

    return DownloadStartResponse(
        task_id=task_id,
        status="queued",
        message=f"İndirme kuyruğa alındı: {title}",
    )


# === Task Status ===

@router.get(
    "/status/{task_id}",
    response_model=TaskProgressResponse,
)
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Görev durumunu sorgula."""
    data = TaskStore.get(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")

    download_url = None
    if data["status"] == "completed":
        download_url = f"/api/file/{task_id}"

    return TaskProgressResponse(
        task_id=data["task_id"],
        status=data["status"],
        progress_percent=data.get("progress_percent", 0.0),
        downloaded_bytes=data.get("downloaded_bytes", 0),
        total_bytes=data.get("total_bytes"),
        speed_bytes_per_sec=data.get("speed_bytes_per_sec"),
        eta_seconds=data.get("eta_seconds"),
        title=data.get("title"),
        filename=data.get("filename"),
        file_size_bytes=data.get("file_size_bytes"),
        error_message=data.get("error_message"),
        created_at=data["created_at"],
        completed_at=data.get("completed_at"),
        download_url=download_url,
    )


# === File Download ===

@router.get("/file/{task_id}")
async def download_file(
    task_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Tamamlanmış görevin dosyasını indir."""
    data = TaskStore.get(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")

    if data["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Görev henüz tamamlanmadı (status={data['status']}).",
        )

    file_path = FileManager.get_task_file(task_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı (silinmiş olabilir).")

    # Dosyayı stream et
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


# === Cancel ===

@router.delete("/task/{task_id}")
async def cancel_task(
    task_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Görevi iptal et ve dosyalarını sil."""
    data = TaskStore.get(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")

    # Celery'de revoke
    celery_app.control.revoke(task_id, terminate=True)

    # Status güncelle
    TaskStore.update(task_id, status="cancelled")

    # Dosyaları sil
    FileManager.cleanup_task(task_id)

    return {"task_id": task_id, "status": "cancelled"}


# === List Tasks (debug için) ===

@router.get("/tasks/active")
async def list_active_tasks(api_key: str = Depends(verify_api_key)):
    """Aktif görevleri listele."""
    return TaskStore.list_active()
