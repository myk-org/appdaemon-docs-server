"""Cover additional branches in main.py endpoints."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    apps = tmp_path / "apps"
    docs = tmp_path / "docs"
    apps.mkdir()
    docs.mkdir()
    monkeypatch.setenv("APPS_DIR", str(apps))
    monkeypatch.setenv("DOCS_DIR", str(docs))
    monkeypatch.setenv("TEMPLATES_DIR", "server/templates")
    monkeypatch.setenv("STATIC_DIR", "server/static")
    monkeypatch.setenv("ENABLE_FILE_WATCHER", "false")
    yield


@pytest.fixture
def client():
    from server.main import app

    return TestClient(app)


def test_search_handles_file_errors(client, tmp_path):
    # Create docs directory with one md that raises on read
    doc = tmp_path / "docs" / "a.md"
    doc.write_text("# A\ncontent")
    with patch("server.main.DOCS_DIR", tmp_path / "docs"), patch("builtins.open", side_effect=OSError("boom")):
        r = client.get("/api/search?q=a")
        assert r.status_code == 200
        assert r.json()["total_results"] >= 0


def test_watcher_status_active(client):
    fake = Mock()
    fake.get_status.return_value = {"is_watching": True}
    with patch("server.main.file_watcher", fake):
        r = client.get("/api/watcher/status")
        assert r.status_code == 200
        assert r.json()["status"] == "active"


def test_broadcast_test_message_error(client):
    with patch("server.main.websocket_manager.broadcast", new=AsyncMock(side_effect=Exception("boom"))):
        r = client.post("/api/ws/broadcast")
        assert r.status_code == 500
