"""Extra coverage for utils internals and edge cases."""

import logging
import sys
from pathlib import Path
from unittest.mock import patch

from server.utils.utils import (
    _check_external_apps_dir,
    _get_windows_docker_path_hint,
    count_automation_files,
    count_documentation_files,
    DirectoryStatus,
)


def test_check_external_apps_dir_external_and_readonly(tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    apps.mkdir()

    # Make it appear external by changing cwd to a created different directory
    other = tmp_path / "different"
    other.mkdir()
    monkeypatch.chdir(other)

    # Force write permission check to fail by patching Path.touch
    with patch("pathlib.Path.touch", side_effect=PermissionError("ro")):
        is_external, is_readonly = _check_external_apps_dir(apps)
        assert is_external is True
        assert is_readonly is True


def test_get_windows_docker_path_hint(monkeypatch):
    # Simulate Windows platform
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    hint = _get_windows_docker_path_hint()
    assert hint is not None and "Docker" in hint


def test_count_automation_and_docs(tmp_path: Path):
    apps = tmp_path / "apps"
    docs = tmp_path / "docs"
    apps.mkdir()
    docs.mkdir()

    # Create automation files and excluded files
    for name in ["a.py", "b.py", "const.py", "infra.py", "__init__.py"]:
        (apps / name).write_text("# x")

    (docs / "one.md").write_text("# one")
    (docs / "two.md").write_text("# two")

    assert count_automation_files(apps) == 2  # a.py, b.py only
    assert count_documentation_files(docs) == 2


def test_directory_status_log_messages(tmp_path, caplog):
    logger = logging.getLogger("test.utils")
    caplog.set_level(logging.INFO)

    apps = tmp_path / "apps"
    docs = tmp_path / "docs"

    # Missing both -> warnings and errors
    ds = DirectoryStatus(apps, docs)
    ds.log_status(logger)
    # Create dirs and re-check messages
    apps.mkdir()
    docs.mkdir()
    (apps / "a.py").write_text("#")
    (docs / "a.md").write_text("#")
    ds = DirectoryStatus(apps, docs)
    ds.log_status(logger)
    assert any("Documentation ready" in m for m in caplog.messages) or any(
        "will be created" in m for m in caplog.messages
    )
