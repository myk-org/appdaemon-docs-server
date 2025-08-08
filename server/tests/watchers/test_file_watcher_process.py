"""Process-level tests for FileWatcher._process_single_event and handler mapping."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from server.watchers.file_watcher import FileWatcher, WatchConfig, FileEvent, FileWatchEventHandler


@pytest.mark.asyncio
async def test_process_single_event_success(tmp_path, monkeypatch):
    cfg = WatchConfig(watch_directory=tmp_path, output_directory=tmp_path)
    watcher = FileWatcher(cfg)
    # Mock batch generator
    watcher.batch_generator.generate_single_file_docs = lambda p: ("# ok", True)

    # Stub websocket broadcasts
    with patch("server.watchers.file_watcher.websocket_manager.broadcast_batch_status", new=AsyncMock()):
        evt = FileEvent(file_path=tmp_path / "a.py", event_type="modified", timestamp=1.0)
        await watcher._process_single_event(evt)

    # Output created
    assert (tmp_path / "a.md").exists()
    st = watcher.get_status()
    assert st["statistics"]["successful_generations"] >= 1


@pytest.mark.asyncio
async def test_process_single_event_failure(tmp_path):
    cfg = WatchConfig(watch_directory=tmp_path, output_directory=tmp_path, max_retry_attempts=1, retry_delay=0)
    watcher = FileWatcher(cfg)

    def raiser(_):
        raise RuntimeError("boom")

    watcher.batch_generator.generate_single_file_docs = raiser

    with patch("server.watchers.file_watcher.websocket_manager.broadcast_batch_status", new=AsyncMock()):
        evt = FileEvent(file_path=tmp_path / "b.py", event_type="modified", timestamp=1.0)
        await watcher._process_single_event(evt)

    st = watcher.get_status()
    assert st["statistics"]["failed_generations"] >= 1


@pytest.mark.asyncio
async def test_file_watch_event_handler_mapping(tmp_path, monkeypatch):
    cfg = WatchConfig(watch_directory=tmp_path, output_directory=tmp_path)
    watcher = FileWatcher(cfg)
    # Provide loop for handler scheduling
    watcher.loop = asyncio.get_running_loop()
    handler = FileWatchEventHandler(watcher)

    # Patch run_coroutine_threadsafe to capture coroutine
    calls = []

    def fake_run(coro, loop):
        calls.append((coro, loop))
        # Schedule coroutine quickly
        asyncio.get_event_loop().create_task(coro)

        class F:
            def add_done_callback(self, *a, **k):
                return None

        return F()

    with (
        patch("server.watchers.file_watcher.asyncio.run_coroutine_threadsafe", side_effect=fake_run),
        patch("server.watchers.file_watcher.websocket_manager.broadcast_file_change", new=AsyncMock()),
    ):
        # Simulate events
        for et in ("created", "modified", "deleted"):
            ev = SimpleNamespace(is_directory=False, src_path=str(tmp_path / "c.py"))
            handler._handle_file_event(ev, et)

    assert len(calls) >= 3
