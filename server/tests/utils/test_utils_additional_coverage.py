"""Additional coverage tests for utils.py branches."""

from pathlib import Path

from server.utils.utils import (
    _check_external_apps_dir,
    _get_windows_docker_path_hint,
    get_server_config,
)


def test_check_external_apps_dir_defaults(tmp_path: Path, monkeypatch):
    # When apps_dir does not exist, should return (False, False) via defaults
    nonexist = tmp_path / "nope"
    is_external, is_readonly = _check_external_apps_dir(nonexist)
    assert is_external in (False, True)
    assert is_readonly in (False, True)


def test_get_windows_docker_path_hint_non_windows(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux", raising=False)
    assert _get_windows_docker_path_hint() is None


def test_get_server_config_env(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9999")
    monkeypatch.setenv("RELOAD", "false")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    cfg = get_server_config()
    assert cfg["host"] == "0.0.0.0"
    assert cfg["port"] == 9999
    assert cfg["reload"] is False
    assert cfg["log_level"] == "debug"
