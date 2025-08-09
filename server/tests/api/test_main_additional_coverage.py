import os
from unittest.mock import Mock, patch

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


def test_health_check_defaults(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "uptime_seconds" in data


def test_generate_index_success(client, tmp_path):
    apps = tmp_path / "apps"
    docs = tmp_path / "docs"
    apps.mkdir()
    docs.mkdir()

    with (
        patch("server.main.MIRRORED_APPS_DIR", apps),
        patch("server.main.DOCS_DIR", docs),
        patch("server.main.BatchDocGenerator") as gen_cls,
    ):
        instance = Mock()
        instance.generate_index_file.return_value = "# Index"
        gen_cls.return_value = instance

        r = client.post("/api/generate/index")
        assert r.status_code == 200
        assert (docs / "README.md").exists()


def test_generate_all_with_file_watcher_disabled(client, tmp_path):
    apps = tmp_path / "apps"
    docs = tmp_path / "docs"
    apps.mkdir()
    docs.mkdir()

    results = {"successful": 1, "failed": 0, "skipped": 0}

    with (
        patch("server.main.APPS_DIR", apps),
        patch("server.main.DOCS_DIR", docs),
        patch("server.main.file_watcher", None),
        patch("server.main.BatchDocGenerator") as gen_cls,
    ):
        instance = Mock()
        instance.generate_all_docs.return_value = results
        instance.generate_index_file.return_value = "# Index"
        gen_cls.return_value = instance

        r = client.post("/api/generate/all?force=true")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True


def test_documentation_index_filters_active(client):
    files = [
        {"name": "a.md", "stem": "a", "size": 10, "title": "A"},
        {"name": "b.md", "stem": "b", "size": 10, "title": "B"},
    ]
    with (
        patch("server.main.docs_service.get_file_list", return_value=files),
        patch("server.main.count_active_apps", return_value={"active_modules": ["a"]}),
    ):
        r = client.get("/docs/")
        assert r.status_code == 200
        text = r.text
        assert "/docs/a" in text
        assert "/docs/b" not in text


def test_get_app_source_text_mode(client, tmp_path):
    mirror = tmp_path / "apps"
    mirror.mkdir()
    src = mirror / "mod2.py"
    src.write_text("print('x')\n", encoding="utf-8")
    with patch("server.main.MIRRORED_APPS_DIR", mirror):
        r = client.get("/api/app-source/mod2?fmt=text")
        assert r.status_code == 200
        assert "print('x')" in r.text
