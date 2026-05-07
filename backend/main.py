"""FastAPI uygulaması — entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api.routes import router
from backend.utils.logging_setup import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup ve shutdown hook'ları."""
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("Video Downloader Backend başlıyor")
    logger.info(f"Download dir: {settings.download_dir}")
    logger.info(f"Redis: {settings.redis_url}")
    logger.info(f"Max concurrent: {settings.max_concurrent_downloads}")
    logger.info("=" * 50)

    # Download dir oluştur
    settings.download_dir.mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Backend kapanıyor")


app = FastAPI(
    title="Video Downloader API",
    description="Çok platformlu video indirme sistemi (1800+ site desteği)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'lar
app.include_router(router)


@app.get("/")
async def root():
    return {
        "name": "Video Downloader API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
