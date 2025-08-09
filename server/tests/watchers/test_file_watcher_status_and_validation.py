"""More status/validation tests for FileWatcher without running the observer."""

import time
from pathlib import Path
import pytest

from server.watchers.file_watcher import FileWatcher, WatchConfig, FileEvent, GenerationResult


def test_get_recent_events_and_results(tmp_path: Path):
    cfg = WatchConfig(watch_directory=tmp_path, output_directory=tmp_path)
    watcher = FileWatcher(cfg)

    # Seed recent events/results
    watcher.recent_events.append(FileEvent(file_path=tmp_path / "a.py", event_type="modified", timestamp=time.time()))
    watcher.recent_results.append(GenerationResult(success=True, file_path=tmp_path / "a.py", generation_time=0.1))

    events = watcher.get_recent_events()
    results = watcher.get_recent_results()
    assert len(events) == 1 and events[0]["event_type"] == "modified"
    assert len(results) == 1 and results[0]["success"] is True


@pytest.mark.parametrize(
    "field, value",
    [
        ("debounce_delay", -1.0),
        ("max_retry_attempts", -1),
        ("retry_delay", -1.0),
        ("max_recent_events", 0),
    ],
)
def test_validate_config_raises(field, value, tmp_path: Path):
    kwargs = {
        "watch_directory": tmp_path,
        "output_directory": tmp_path,
    }
    cfg = WatchConfig(**kwargs)
    setattr(cfg, field, value)
    with pytest.raises(ValueError):
        FileWatcher(cfg)
