"""Tiny tests to nudge coverage by exercising utils branches."""

from server.utils.utils import (
    DirectoryStatus,
    get_server_config,
    get_environment_config,
    print_startup_info,
    parse_boolean_env,
)


def test_utils_print_startup_info_and_envs(tmp_path, capsys, monkeypatch):
    apps = tmp_path / "apps"
    docs = tmp_path / "docs"
    apps.mkdir()
    docs.mkdir()

    # Create one automation file to count
    (apps / "auto.py").write_text("# app")

    # Configure envs
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9999")
    monkeypatch.setenv("RELOAD", "true")
    monkeypatch.setenv("LOG_LEVEL", "info")
    monkeypatch.setenv("ENABLE_FILE_WATCHER", "false")

    ds = DirectoryStatus(apps, docs)
    sc = get_server_config()
    ec = get_environment_config()

    # Exercise print path
    print_startup_info(ds, sc, ec)
    out = capsys.readouterr().out
    assert "Starting" in out

    # Quick boolean parser check
    assert parse_boolean_env("MISSING_FLAG", default="true") is True
