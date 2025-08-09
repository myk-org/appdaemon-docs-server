import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

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


@pytest.mark.asyncio
async def test_start_file_watcher_disabled_by_config(tmp_path):
    from server.main import start_file_watcher

    dir_status = SimpleNamespace(apps_exists=True)
    config = {"enable_file_watcher": False}
    watcher = await start_file_watcher(dir_status, config)  # type: ignore[arg-type]
    assert watcher is None


@pytest.mark.asyncio
async def test_start_file_watcher_success(tmp_path):
    from server import main as main_mod

    apps = tmp_path / "apps"
    gen = tmp_path / "gen"
    docs = tmp_path / "docs"
    apps.mkdir()
    gen.mkdir()
    docs.mkdir()

    dir_status = SimpleNamespace(apps_exists=True)
    config = {
        "enable_file_watcher": True,
        "watch_debounce_delay": 0.1,
        "watch_max_retries": 1,
        "watch_force_regenerate": False,
        "watch_log_level": "INFO",
    }

    fake_watcher = AsyncMock()
    fake_watcher.is_watching = True
    fake_watcher.start_watching = AsyncMock(return_value=None)

    with (
        patch.object(main_mod, "REAL_APPS_DIR", apps),
        patch.object(main_mod, "MIRRORED_APPS_DIR", gen),
        patch.object(main_mod, "DOCS_DIR", docs),
        patch.object(main_mod, "FileWatcher", return_value=fake_watcher),
    ):
        watcher = await main_mod.start_file_watcher(dir_status, config)  # type: ignore[arg-type]
        assert watcher is not None
        assert watcher.is_watching


@pytest.mark.asyncio
async def test_start_file_watcher_error(tmp_path):
    from server import main as main_mod

    apps = tmp_path / "apps"
    gen = tmp_path / "gen"
    docs = tmp_path / "docs"
    apps.mkdir()
    gen.mkdir()
    docs.mkdir()

    dir_status = SimpleNamespace(apps_exists=True)
    config = {
        "enable_file_watcher": True,
        "watch_debounce_delay": 0.1,
        "watch_max_retries": 1,
        "watch_force_regenerate": False,
        "watch_log_level": "INFO",
    }

    with (
        patch.object(main_mod, "REAL_APPS_DIR", apps),
        patch.object(main_mod, "MIRRORED_APPS_DIR", gen),
        patch.object(main_mod, "DOCS_DIR", docs),
        patch.object(main_mod, "FileWatcher", side_effect=RuntimeError("boom")),
        patch.object(main_mod.websocket_manager, "broadcast_batch_status", new_callable=AsyncMock),
    ):
        watcher = await main_mod.start_file_watcher(dir_status, config)  # type: ignore[arg-type]
        assert watcher is None


@pytest.mark.asyncio
async def test_run_initial_documentation_generation_success(tmp_path):
    from server import main as main_mod

    apps = tmp_path / "apps"
    apps.mkdir()
    gen = tmp_path / "gen"
    gen.mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()

    dir_status = SimpleNamespace(apps_exists=True)
    config = {"force_regenerate": True}

    fake_gen = Mock()
    fake_gen.generate_all_docs.return_value = {"successful": 1, "failed": 0, "skipped": 0}
    fake_gen.generate_index_file.return_value = "# Index"

    with (
        patch.object(main_mod, "MIRRORED_APPS_DIR", gen),
        patch.object(main_mod, "DOCS_DIR", docs),
        patch.object(main_mod, "BatchDocGenerator", return_value=fake_gen),
        patch.object(main_mod.websocket_manager, "broadcast_batch_status", new_callable=AsyncMock),
    ):
        ok = await main_mod.run_initial_documentation_generation(dir_status, config)  # type: ignore[arg-type]
        assert ok is True
        assert (docs / "README.md").exists()


def test_trigger_single_file_generation_skip(client, tmp_path):
    apps = tmp_path / "apps"
    apps.mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (apps / "file.py").write_text("# ok", encoding="utf-8")
    (docs / "file.md").write_text("exists", encoding="utf-8")

    with (
        patch("server.main.APPS_DIR", apps),
        patch("server.main.DOCS_DIR", docs),
    ):
        r = client.post("/api/generate/file/file.py")
        assert r.status_code == 200
        data = r.json()
        assert data.get("skipped") is True


def test_partials_app_sources_ok_even_if_list_fails(client, tmp_path):
    # Should still return 200 with empty list when file list fails internally
    mirror = tmp_path / "apps"
    mirror.mkdir()
    with (
        patch("server.main.MIRRORED_APPS_DIR", mirror),
        patch("server.main.docs_service.get_file_list", side_effect=RuntimeError("x")),
    ):
        r = client.get("/partials/app-sources")
        assert r.status_code == 200
