"""
core modülü için temel testler.

Ağ gerektiren testler @pytest.mark.network ile işaretlenmiştir;
çalıştırmak için: pytest tests/ -m network
"""

import pytest

from core import (
    AudioFormat,
    DownloadOptions,
    Downloader,
    VideoFormat,
    extract_info,
)
from core.exceptions import InvalidURLError, VideoUnavailableError
from core.formats import build_format_selector, parse_formats
from core.progress import ProgressInfo, ProgressTracker


# ---------------------------------------------------------------------------
# exceptions
# ---------------------------------------------------------------------------

class TestExtractInfoErrors:
    def test_invalid_url_plain_string(self) -> None:
        with pytest.raises(InvalidURLError):
            extract_info("not a url")

    def test_invalid_url_unsupported_site(self) -> None:
        with pytest.raises(InvalidURLError):
            extract_info("https://example.com/random-page")


# ---------------------------------------------------------------------------
# formats
# ---------------------------------------------------------------------------

class TestBuildFormatSelector:
    def test_best(self) -> None:
        assert build_format_selector("best") == "bestvideo+bestaudio/best"

    def test_720p(self) -> None:
        sel = build_format_selector("720p")
        assert "720" in sel
        assert "bestvideo" in sel

    def test_audio_quality(self) -> None:
        assert build_format_selector("audio") == "bestaudio/best"

    def test_audio_only_flag(self) -> None:
        assert build_format_selector("best", audio_only=True) == "bestaudio/best"

    def test_unknown_quality_falls_back_to_best(self) -> None:
        assert build_format_selector("999p") == "bestvideo+bestaudio/best"


class TestParseFormats:
    def _make_fmt(self, **kwargs) -> dict:
        defaults = {
            "format_id": "1",
            "ext": "mp4",
            "width": 1280,
            "height": 720,
            "vcodec": "avc1",
            "acodec": "none",
            "fps": 30,
            "filesize": None,
        }
        defaults.update(kwargs)
        return defaults

    def test_video_format_parsed(self) -> None:
        info = {"formats": [self._make_fmt()]}
        videos, audios = parse_formats(info)
        assert len(videos) == 1
        assert len(audios) == 0
        assert videos[0].resolution == "1280x720"

    def test_audio_format_parsed(self) -> None:
        info = {
            "formats": [
                self._make_fmt(vcodec="none", acodec="mp4a", width=None, height=None)
            ]
        }
        videos, audios = parse_formats(info)
        assert len(videos) == 0
        assert len(audios) == 1

    def test_empty_formats(self) -> None:
        videos, audios = parse_formats({"formats": []})
        assert videos == []
        assert audios == []


# ---------------------------------------------------------------------------
# progress
# ---------------------------------------------------------------------------

class TestProgressTracker:
    def test_downloading_status(self) -> None:
        received: list[ProgressInfo] = []
        tracker = ProgressTracker(received.append)
        tracker.hook(
            {
                "status": "downloading",
                "downloaded_bytes": 500,
                "total_bytes": 1000,
                "speed": 100.0,
                "eta": 5,
                "filename": "test.mp4",
            }
        )
        assert len(received) == 1
        assert received[0].percent == pytest.approx(50.0)
        assert received[0].status == "downloading"

    def test_finished_status(self) -> None:
        received: list[ProgressInfo] = []
        tracker = ProgressTracker(received.append)
        tracker.hook({"status": "finished", "downloaded_bytes": 1000, "filename": "f.mp4"})
        assert received[0].status == "finished"

    def test_unknown_status_ignored(self) -> None:
        received: list[ProgressInfo] = []
        tracker = ProgressTracker(received.append)
        tracker.hook({"status": "processing", "downloaded_bytes": 0})
        assert received == []


# ---------------------------------------------------------------------------
# Network testleri (opsiyonel)
# ---------------------------------------------------------------------------

@pytest.mark.network
def test_extract_youtube() -> None:
    info = extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert info.title
    assert info.duration is not None and info.duration > 0
    assert len(info.video_formats) > 0
    assert info.extractor == "youtube"
