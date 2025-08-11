"""Cover additional error branches in file_watcher via minimal stubs."""

from server.watchers.file_watcher import FileWatcher, WatchConfig


def test_file_watcher_init_with_nonexistent_dir(tmp_path):
    # Point watcher to a directory that does not exist to hit early returns
    nonexist = tmp_path / "nope"
    cfg = WatchConfig(watch_directory=nonexist, output_directory=tmp_path)
    fw = FileWatcher(cfg)
    # Access internal status to avoid unused object
    status = fw.get_status()
    assert "files_processed" in status["statistics"]
