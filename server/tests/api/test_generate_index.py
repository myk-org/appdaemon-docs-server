"""Tests for the /api/generate/index endpoint."""

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


def test_generate_index_success(client, tmp_path):
    # Mock generator to return fixed content
    with patch("server.main.BatchDocGenerator") as gen_cls:
        gen = Mock()
        gen.generate_index_file.return_value = "# Index"
        gen_cls.return_value = gen

        resp = client.post("/api/generate/index")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "Index regenerated"


def test_generate_index_failure(client):
    with patch("server.main.BatchDocGenerator", side_effect=Exception("boom")):
        resp = client.post("/api/generate/index")
        assert resp.status_code == 500
