"""Direct tests for FileWatcher._should_process_file variations."""

from pathlib import Path

from server.watchers.file_watcher import FileWatcher, WatchConfig


def test_should_process_file_patterns_and_exclusions(tmp_path: Path):
    cfg = WatchConfig(watch_directory=tmp_path, output_directory=tmp_path)
    watcher = FileWatcher(cfg)

    # Will match pattern and not excluded
    f1 = tmp_path / "ok.py"
    f1.write_text("# x")
    assert watcher._should_process_file(f1) is True

    # Excluded by name
    f2 = tmp_path / "const.py"
    f2.write_text("# x")
    assert watcher._should_process_file(f2) is False

    # Outside of watch dir
    other = tmp_path.parent / "outer.py"
    other.write_text("# x")
    assert watcher._should_process_file(other) is False
