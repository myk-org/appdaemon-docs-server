import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(
        os.environ,
        {
            "APPS_DIR": "/tmp/test_apps",
            "DOCS_DIR": "/tmp/test_docs",
            "TEMPLATES_DIR": "server/templates",
            "STATIC_DIR": "server/static",
            "LOG_LEVEL": "INFO",
            "ENABLE_FILE_WATCHER": "false",
        },
    ):
        yield


@pytest.fixture
def client(mock_env):
    from server.main import app

    return TestClient(app)


def test_pygments_css(client):
    r = client.get("/api/css/pygments.css")
    assert r.status_code == 200
    assert "highlight" in r.text


def test_search_min_length(client):
    r = client.get("/api/search?q=a")
    assert r.status_code == 200
    data = r.json()
    assert data["total_results"] == 0
    assert "must be at least 2" in data["message"].lower()


def test_search_with_docs_files(client, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "alpha.md").write_text("# Alpha\nThis is a sample alpha document.", encoding="utf-8")
    (docs / "beta.md").write_text("# Beta\nAnother document mentions Alpha.", encoding="utf-8")

    with patch("server.main.DOCS_DIR", docs):
        r = client.get("/api/search?q=alpha")
        assert r.status_code == 200
        data = r.json()
        assert data["total_results"] >= 1
        assert any(res["filename"] == "alpha.md" for res in data["results"]) or any(
            res["filename"] == "beta.md" for res in data["results"]
        )


def test_app_source_not_found(client):
    r = client.get("/api/app-source/nope?fmt=html")
    assert r.status_code in (404, 500)


def test_sse_head(client):
    r = client.head("/sse")
    assert r.status_code == 200
    assert r.headers.get("Content-Type") == "text/event-stream"


def test_ws_status(client):
    r = client.get("/api/ws/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "active"


def test_watcher_status_disabled(client):
    r = client.get("/api/watcher/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("disabled", "stopped")


def test_get_file_content_success(client):
    with patch("server.main.docs_service.get_file_content", return_value=("<h1>Doc</h1>", "Title")):
        r = client.get("/api/file/sample.md")
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Title"
        assert data["type"] == "markdown"


def test_documentation_file_success(client):
    with patch("server.main.docs_service.get_file_content", return_value=("<h1>Doc</h1>", "Doc Title")):
        r = client.get("/docs/sample")
        assert r.status_code == 200
        assert "Doc Title" in r.text


def test_files_pagination_and_sanitization(client):
    files = [
        {"name": "a.md", "stem": "a", "size": 100, "title": "A", "last_updated": None},
        {"name": "b.md", "stem": "b", "size": 200, "title": "B", "last_updated": None},
    ]
    with patch("server.main.docs_service.get_file_list", return_value=files):
        r = client.get("/api/files?limit=1&offset=1")
        assert r.status_code == 200
        data = r.json()
        assert data["total_count"] == 2
        assert len(data["files"]) == 1
        # Ensure optional None fields are stripped
        assert "last_updated" not in data["files"][0]
