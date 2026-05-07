"""API request/response şemaları."""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal


# === Request Schemas ===

class ExtractRequest(BaseModel):
    """Video bilgisi çekme isteği."""
    url: str = Field(..., description="Video URL'si", examples=["https://youtu.be/dQw4w9WgXcQ"])


class DownloadRequest(BaseModel):
    """İndirme başlatma isteği."""
    url: str = Field(..., description="Video URL'si")
    quality: str = Field("720p", description="Kalite: best, 1080p, 720p, 480p, 360p, audio")
    audio_only: bool = Field(False, description="Sadece ses indir")
    audio_format: Literal["mp3", "m4a", "opus"] = Field("mp3")
    video_format: Literal["mp4", "mkv", "webm"] = Field("mp4")
    embed_thumbnail: bool = Field(True)
    embed_metadata: bool = Field(True)
    embed_subtitles: bool = Field(False)
    subtitle_languages: list[str] = Field(default_factory=lambda: ["en", "tr"])


# === Response Schemas ===

class FormatInfo(BaseModel):
    """Tek bir format bilgisi."""
    format_id: str
    ext: str
    resolution: str | None = None
    fps: int | None = None
    filesize: int | None = None
    has_audio: bool
    has_video: bool


class VideoInfoResponse(BaseModel):
    """Video bilgisi."""
    url: str
    title: str
    description: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    uploader: str | None = None
    upload_date: str | None = None
    view_count: int | None = None
    extractor: str
    is_playlist: bool = False
    playlist_count: int | None = None
    video_formats: list[FormatInfo] = Field(default_factory=list)
    audio_formats: list[FormatInfo] = Field(default_factory=list)


class DownloadStartResponse(BaseModel):
    """İndirme başlatma yanıtı."""
    task_id: str = Field(..., description="Görev takibi için ID")
    status: str = "queued"
    message: str = "İndirme kuyruğa alındı"


class TaskProgressResponse(BaseModel):
    """Görev ilerleme bilgisi."""
    task_id: str
    status: Literal["queued", "downloading", "completed", "failed", "cancelled"]
    progress_percent: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    speed_bytes_per_sec: float | None = None
    eta_seconds: int | None = None
    title: str | None = None
    filename: str | None = None
    file_size_bytes: int | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    download_url: str | None = None  # Tamamlandığında dolu


class ErrorResponse(BaseModel):
    """Standart hata yanıtı."""
    error: str
    detail: str
    category: str = "generic"


class HealthResponse(BaseModel):
    """Health check yanıtı."""
    status: Literal["ok", "degraded", "error"]
    version: str
    yt_dlp_version: str
    redis_connected: bool
    celery_workers: int
    disk_free_gb: float
