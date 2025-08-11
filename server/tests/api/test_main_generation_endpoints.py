"""Additional API tests to cover branches in main.py."""

from unittest.mock import Mock, patch

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


def test_generate_all_uses_batch_when_no_watcher(client):
    from pathlib import Path
    from unittest.mock import MagicMock

    # Mock APPS_DIR.exists() to return True specifically
    mock_apps_dir = MagicMock(spec=Path)
    mock_apps_dir.exists.return_value = True

    # Mock DOCS_DIR and the README.md file writing
    mock_docs_dir = MagicMock(spec=Path)
    mock_readme_path = MagicMock(spec=Path)
    mock_docs_dir.__truediv__.return_value = mock_readme_path
    mock_readme_path.write_text.return_value = None

    with (
        patch("server.main.file_watcher", None),
        patch("server.main.BatchDocGenerator") as gen_cls,
        patch("server.main.APPS_DIR", mock_apps_dir),
        patch("server.main.DOCS_DIR", mock_docs_dir),
        patch("server.main.websocket_manager") as mock_ws_manager,
    ):
        # Mock the websocket manager's broadcast method to be async
        from unittest.mock import AsyncMock

        mock_ws_manager.broadcast_batch_status = AsyncMock(return_value=None)

        gen = Mock()
        gen.generate_all_docs.return_value = {
            "total_files": 1,
            "successful": 1,
            "failed": 0,
            "skipped": 0,
            "generated_files": [],
            "failed_files": [],
            "skipped_files": [],
        }
        gen.generate_index_file.return_value = "# Index"
        gen_cls.return_value = gen

        r = client.post("/api/generate/all")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True


def test_generate_file_skip_when_exists(client, tmp_path):
    # Create source and output to hit skip branch
    apps = tmp_path / "apps1"
    docs = tmp_path / "docs1"
    apps.mkdir()
    docs.mkdir()
    with patch("server.main.APPS_DIR", apps), patch("server.main.DOCS_DIR", docs):
        (apps / "file.py").write_text("# ok")
        (docs / "file.md").write_text("exists")
        r = client.post("/api/generate/file/file.py")
        assert r.status_code == 200
        assert r.json()["skipped"] is True


def test_search_no_results(client):
    r = client.get("/api/search?q=zz")
    assert r.status_code == 200
    data = r.json()
    assert data["total_results"] == 0


def test_watcher_status_disabled(client):
    with patch("server.main.file_watcher", None):
        r = client.get("/api/watcher/status")
        assert r.status_code == 200
        assert r.json()["status"] == "disabled"
