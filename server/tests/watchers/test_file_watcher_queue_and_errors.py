"""Additional coverage for FileWatcher status and errors."""

import pytest

from server.watchers.file_watcher import FileWatcher, WatchConfig, FileEvent


@pytest.mark.asyncio
async def test_watcher_status_and_error_summary(tmp_path):
    cfg = WatchConfig(watch_directory=tmp_path, output_directory=tmp_path)
    watcher = FileWatcher(cfg)

    # Simulate some errors
    p1 = tmp_path / "x.py"
    p2 = tmp_path / "y.py"
    watcher.error_counts[p1] = 2
    watcher.error_counts[p2] = 1
    watcher.last_errors[p1] = "Err1"
    watcher.last_errors[p2] = "Err2"

    status = watcher.get_status()
    assert "statistics" in status
    summary = watcher.get_error_summary()
    assert str(p1) in summary
    assert summary[str(p1)]["error_count"] == 2


@pytest.mark.asyncio
async def test_queue_for_processing_without_loop(tmp_path, caplog):
    cfg = WatchConfig(watch_directory=tmp_path, output_directory=tmp_path)
    watcher = FileWatcher(cfg)
    watcher.loop = None
    evt = FileEvent(file_path=tmp_path / "a.py", event_type="modified", timestamp=1.0)
    # Should not raise
    watcher._queue_for_processing(evt)
