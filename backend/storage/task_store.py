"""Görev metadata yönetimi (Redis tabanlı)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import redis

from backend.config import settings


# Redis client (singleton)
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


# Key prefix'leri
TASK_KEY_PREFIX = "vd:task:"
TASK_TTL_SECONDS = settings.file_retention_hours * 3600 + 3600  # Dosya süresinden 1 saat fazla


class TaskStore:
    """Görev metadata'sını Redis'te saklayan class."""

    @staticmethod
    def _key(task_id: str) -> str:
        return f"{TASK_KEY_PREFIX}{task_id}"

    @classmethod
    def create(cls, task_id: str, url: str, options: dict) -> dict:
        """Yeni görev oluştur."""
        data = {
            "task_id": task_id,
            "status": "queued",
            "url": url,
            "options": options,
            "progress_percent": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": None,
            "speed_bytes_per_sec": None,
            "eta_seconds": None,
            "title": None,
            "filename": None,
            "file_size_bytes": None,
            "error_message": None,
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }
        cls._save(task_id, data)
        return data

    @classmethod
    def get(cls, task_id: str) -> dict | None:
        """Görev bilgisini al."""
        raw = get_redis().get(cls._key(task_id))
        if raw is None:
            return None
        return json.loads(raw)

    @classmethod
    def update(cls, task_id: str, **updates: Any) -> dict | None:
        """Görev bilgisini güncelle (kısmi update)."""
        data = cls.get(task_id)
        if data is None:
            return None
        data.update(updates)
        cls._save(task_id, data)
        return data

    @classmethod
    def delete(cls, task_id: str) -> bool:
        """Görevi sil."""
        return bool(get_redis().delete(cls._key(task_id)))

    @classmethod
    def _save(cls, task_id: str, data: dict) -> None:
        """Internal: Redis'e yaz."""
        get_redis().setex(
            cls._key(task_id),
            TASK_TTL_SECONDS,
            json.dumps(data, default=str),
        )

    @classmethod
    def list_active(cls) -> list[dict]:
        """Aktif (henüz tamamlanmamış) görevleri listele."""
        keys = get_redis().keys(f"{TASK_KEY_PREFIX}*")
        results = []
        for key in keys:
            raw = get_redis().get(key)
            if raw:
                data = json.loads(raw)
                if data.get("status") in ("queued", "downloading"):
                    results.append(data)
        return results
