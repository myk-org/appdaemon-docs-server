"""Small tests to exercise remaining branches in main.py for coverage."""

from unittest.mock import patch

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


def test_health_starting_status(client):
    # Not completed, apps dir exists -> starting
    with (
        patch("server.main.startup_generation_completed", False),
        patch("server.main.startup_errors", []),
    ):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "starting"


def test_pygments_css_error_path(client):
    # Force HtmlFormatter to raise to hit error branch
    with patch("server.main.HtmlFormatter", side_effect=Exception("boom")):
        r = client.get("/api/css/pygments.css")
        assert r.status_code == 500


def test_ws_status_error(client):
    # Force websocket status endpoint to error path
    with patch("server.main.websocket_manager.get_connection_info", side_effect=Exception("boom")):
        r = client.get("/api/ws/status")
        assert r.status_code == 500


def test_watcher_status_error(client):
    # Provide a watcher that raises on get_status
    fake = type("W", (), {"get_status": lambda self: (_ for _ in ()).throw(Exception("err"))})()
    with patch("server.main.file_watcher", fake):
        r = client.get("/api/watcher/status")
        assert r.status_code == 500


def test_generate_file_error_branch(client, tmp_path):
    # Cause single file generation to raise and return 500
    src = tmp_path  # Reuse fixture-created dirs
    out = tmp_path
    (src / "x.py").write_text("# ok")
    with patch("server.main.APPS_DIR", src), patch("server.main.DOCS_DIR", out):
        with patch("server.main.BatchDocGenerator.generate_single_file_docs", side_effect=Exception("boom")):
            r = client.post("/api/generate/file/x.py")
            assert r.status_code == 500


def test_generate_all_missing_apps_dir(client, tmp_path):
    missing = tmp_path / "noapps"  # does not exist
    with patch("server.main.APPS_DIR", missing):
        r = client.post("/api/generate/all")
        assert r.status_code == 404
