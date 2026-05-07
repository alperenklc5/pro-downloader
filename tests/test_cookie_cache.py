"""Cookie cache testleri."""
from datetime import datetime, timedelta
from core.cookie_cache import (
    CacheMetadata, get_metadata, is_cache_valid,
    clear_cache,
)


def test_no_cache_initially():
    clear_cache()
    assert get_metadata() is None
    assert not is_cache_valid("firefox", None)


def test_metadata_stale_check():
    meta = CacheMetadata(
        browser="firefox",
        profile=None,
        synced_at=(datetime.now() - timedelta(days=10)).isoformat(),
        cookie_count=100,
    )
    assert meta.is_stale()

    fresh = CacheMetadata(
        browser="firefox",
        profile=None,
        synced_at=datetime.now().isoformat(),
        cookie_count=100,
    )
    assert not fresh.is_stale()


def test_age_human():
    meta = CacheMetadata(
        browser="firefox",
        profile=None,
        synced_at=(datetime.now() - timedelta(hours=2)).isoformat(),
        cookie_count=100,
    )
    assert "saat" in meta.age_human()

    recent = CacheMetadata(
        browser="firefox",
        profile=None,
        synced_at=datetime.now().isoformat(),
        cookie_count=50,
    )
    assert recent.age_human() == "az önce"


def test_cache_invalid_for_wrong_browser():
    clear_cache()
    # Even if we had a cache, wrong browser should be invalid
    assert not is_cache_valid("chrome", None)
    assert not is_cache_valid("edge", "Default")
