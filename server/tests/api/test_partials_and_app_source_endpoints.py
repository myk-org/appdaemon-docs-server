from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
import os


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


def test_partials_app_sources_filters_active(client, tmp_path):
    # Prepare mirrored apps with two modules
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    (mirror / "a.py").write_text("# a", encoding="utf-8")
    (mirror / "b.py").write_text("# b", encoding="utf-8")

    # Patch active modules to only include 'a'
    files_list = [
        {"name": "a.md", "stem": "a", "size": 10, "title": "A"},
        {"name": "b.md", "stem": "b", "size": 10, "title": "B"},
    ]

    with (
        patch("server.main.MIRRORED_APPS_DIR", mirror),
        patch("server.main.docs_service.get_file_list", return_value=files_list),
        patch("server.main.count_active_apps", return_value={"active_modules": ["a"]}),
    ):
        r = client.get("/partials/app-sources")
        assert r.status_code == 200
        html = r.text
        assert "a.py" in html
        assert "b.py" not in html


def test_get_app_source_html(client, tmp_path):
    mirror = tmp_path / "apps"
    mirror.mkdir()
    (mirror / "mod.py").write_text(
        """
def x():
    return 1
""",
        encoding="utf-8",
    )

    with patch("server.main.MIRRORED_APPS_DIR", mirror):
        r = client.get("/api/app-source/mod?fmt=html&theme=light")
        assert r.status_code == 200
        # Contains pygments CSS scope container id
        assert "app-source-viewer" in r.text
        assert "highlight" in r.text


def test_get_app_source_raw(client, tmp_path):
    mirror = tmp_path / "apps"
    mirror.mkdir()
    (mirror / "rawmod.py").write_text(
        """
def y():
    return 2
""",
        encoding="utf-8",
    )

    with patch("server.main.MIRRORED_APPS_DIR", mirror):
        r = client.get("/api/app-source/raw/rawmod")
        assert r.status_code == 200
        data = r.json()
        assert data["module"] == "rawmod"
        assert "def y()" in data["content"]
