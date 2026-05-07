"""İndirilen dosya yaşam döngüsü."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from backend.config import settings


class FileManager:
    """Dosya saklama ve temizleme."""

    @classmethod
    def get_download_dir(cls) -> Path:
        """İndirme dizinini döndür, yoksa oluştur."""
        path = settings.download_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_task_dir(cls, task_id: str) -> Path:
        """Belirli bir görev için izole klasör (dosya çakışması olmasın)."""
        path = cls.get_download_dir() / task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_task_file(cls, task_id: str) -> Path | None:
        """Görev klasöründeki dosyayı bul (genelde tek dosya olur)."""
        task_dir = cls.get_task_dir(task_id)
        files = [f for f in task_dir.iterdir() if f.is_file()]
        if not files:
            return None
        # En büyük dosyayı al (video, partial dosyaları değil)
        return max(files, key=lambda f: f.stat().st_size)

    @classmethod
    def cleanup_task(cls, task_id: str) -> None:
        """Bir görevin tüm dosyalarını sil."""
        task_dir = cls.get_download_dir() / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)

    @classmethod
    def cleanup_old_files(cls) -> dict:
        """Eski dosyaları temizle. Çağrılma sıklığı: cron ile saatte bir.

        Strateji:
        1. file_retention_hours'tan eski dosyaları sil
        2. Toplam boyut max_storage_gb'i aşıyorsa, en eski dosyalardan başlayarak sil

        Returns: İstatistik dict
        """
        download_dir = cls.get_download_dir()
        if not download_dir.exists():
            return {"deleted_count": 0, "freed_bytes": 0}

        cutoff_time = datetime.now() - timedelta(hours=settings.file_retention_hours)
        deleted_count = 0
        freed_bytes = 0

        # 1) Yaş bazlı temizlik
        for task_dir in download_dir.iterdir():
            if not task_dir.is_dir():
                continue
            try:
                mtime = datetime.fromtimestamp(task_dir.stat().st_mtime)
                if mtime < cutoff_time:
                    size = sum(f.stat().st_size for f in task_dir.rglob("*") if f.is_file())
                    shutil.rmtree(task_dir, ignore_errors=True)
                    deleted_count += 1
                    freed_bytes += size
            except OSError:
                continue

        # 2) Boyut bazlı temizlik (eskiden yeniye)
        max_bytes = settings.max_storage_gb * 1024 * 1024 * 1024
        total_size = sum(
            f.stat().st_size for f in download_dir.rglob("*") if f.is_file()
        )

        if total_size > max_bytes:
            task_dirs = sorted(
                [d for d in download_dir.iterdir() if d.is_dir()],
                key=lambda d: d.stat().st_mtime,
            )
            for task_dir in task_dirs:
                if total_size <= max_bytes:
                    break
                try:
                    size = sum(f.stat().st_size for f in task_dir.rglob("*") if f.is_file())
                    shutil.rmtree(task_dir, ignore_errors=True)
                    total_size -= size
                    deleted_count += 1
                    freed_bytes += size
                except OSError:
                    continue

        return {
            "deleted_count": deleted_count,
            "freed_bytes": freed_bytes,
            "remaining_size_bytes": total_size,
        }

    @classmethod
    def get_disk_usage(cls) -> dict:
        """Disk kullanımı bilgisi."""
        download_dir = cls.get_download_dir()
        usage = shutil.disk_usage(str(download_dir))

        total_used = 0
        if download_dir.exists():
            total_used = sum(
                f.stat().st_size for f in download_dir.rglob("*") if f.is_file()
            )

        return {
            "downloads_used_bytes": total_used,
            "disk_free_bytes": usage.free,
            "disk_total_bytes": usage.total,
        }
