"""API endpoint testleri."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer dev-key-change-me-in-production"}


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "name" in r.json()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "yt_dlp_version" in data


def test_extract_no_auth(client):
    r = client.post("/api/extract", json={"url": "https://youtu.be/test"})
    assert r.status_code == 401


def test_extract_invalid_key(client):
    r = client.post(
        "/api/extract",
        json={"url": "https://youtu.be/test"},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert r.status_code == 401


def test_extract_bad_url(client, auth_headers):
    r = client.post(
        "/api/extract",
        json={"url": "not a url"},
        headers=auth_headers,
    )
    assert r.status_code in (400, 500)


@pytest.mark.network
def test_extract_youtube(client, auth_headers):
    r = client.post(
        "/api/extract",
        json={"url": "https://youtu.be/jNQXAC9IVRw"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["title"]
    assert data["duration"] > 0
