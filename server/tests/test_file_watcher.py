"""
Tests for the FileWatcher system.

These tests verify the file watcher's functionality including:
- File system event handling
- Debouncing behavior
- Error handling and retry logic
- Status tracking and reporting
- Integration with BatchDocGenerator
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from server.watchers.file_watcher import FileWatcher, WatchConfig, FileEvent, GenerationResult, DebounceHandler


class TestWatchConfig:
    """Test the WatchConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = WatchConfig()

        assert config.watch_directory == Path("../apps")
        assert config.output_directory == Path("../apps/docs")
        assert config.debounce_delay == 2.0
        assert config.max_retry_attempts == 3
        assert config.retry_delay == 1.0
        assert not config.force_regenerate
        assert config.batch_processing
        assert config.log_level == "INFO"
        assert config.max_recent_events == 100

    def test_custom_config(self):
        """Test custom configuration values."""
        config = WatchConfig(
            watch_directory=Path("/custom/apps"),
            output_directory=Path("/custom/docs"),
            debounce_delay=3.5,
            max_retry_attempts=5,
            force_regenerate=True,
            log_level="DEBUG",
        )

        assert config.watch_directory == Path("/custom/apps")
        assert config.output_directory == Path("/custom/docs")
        assert config.debounce_delay == 3.5
        assert config.max_retry_attempts == 5
        assert config.force_regenerate
        assert config.log_level == "DEBUG"


class TestFileEvent:
    """Test the FileEvent dataclass."""

    def test_file_event_creation(self):
        """Test FileEvent creation and path handling."""
        timestamp = time.time()

        # Test with Path object
        event1 = FileEvent(file_path=Path("/test/file.py"), event_type="modified", timestamp=timestamp)

        assert isinstance(event1.file_path, Path)
        assert event1.file_path == Path("/test/file.py")
        assert event1.event_type == "modified"
        assert event1.timestamp == timestamp
        assert event1.retry_count == 0

        # Test with string path (should be converted)
        event2 = FileEvent(file_path="/test/file.py", event_type="created", timestamp=timestamp)

        assert isinstance(event2.file_path, Path)
        assert event2.file_path == Path("/test/file.py")


class TestGenerationResult:
    """Test the GenerationResult dataclass."""

    def test_successful_result(self):
        """Test successful generation result."""
        result = GenerationResult(
            success=True, file_path=Path("/test/file.py"), output_path=Path("/test/docs/file.md"), generation_time=1.5
        )

        assert result.success
        assert result.file_path == Path("/test/file.py")
        assert result.output_path == Path("/test/docs/file.md")
        assert result.error_message is None
        assert result.generation_time == 1.5
        assert result.retry_count == 0

    def test_failed_result(self):
        """Test failed generation result."""
        result = GenerationResult(
            success=False,
            file_path=Path("/test/file.py"),
            error_message="Parse error",
            generation_time=0.5,
            retry_count=2,
        )

        assert not result.success
        assert result.file_path == Path("/test/file.py")
        assert result.output_path is None
        assert result.error_message == "Parse error"
        assert result.generation_time == 0.5
        assert result.retry_count == 2


class TestDebounceHandler:
    """Test the debouncing functionality."""

    @pytest.mark.asyncio
    async def test_debounce_single_event(self):
        """Test debouncing a single event."""
        handler = DebounceHandler(delay=0.1)
        callback_mock = Mock()

        event = FileEvent(file_path=Path("/test/file.py"), event_type="modified", timestamp=time.time())

        # Add event
        await handler.add_event(event, callback_mock)

        # Callback should not be called immediately
        assert not callback_mock.called

        # Wait for debounce delay
        await asyncio.sleep(0.15)

        # Callback should now be called
        callback_mock.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_debounce_multiple_events_same_file(self):
        """Test debouncing multiple events for the same file."""
        handler = DebounceHandler(delay=0.1)
        callback_mock = Mock()

        file_path = Path("/test/file.py")

        # Add multiple events for the same file
        event1 = FileEvent(file_path, "modified", time.time())
        event2 = FileEvent(file_path, "modified", time.time() + 0.01)
        event3 = FileEvent(file_path, "modified", time.time() + 0.02)

        await handler.add_event(event1, callback_mock)
        await asyncio.sleep(0.05)  # Half the delay
        await handler.add_event(event2, callback_mock)
        await asyncio.sleep(0.05)  # Half the delay
        await handler.add_event(event3, callback_mock)

        # Wait for final debounce
        await asyncio.sleep(0.15)

        # Should only be called once with the last event
        callback_mock.assert_called_once_with(event3)

    @pytest.mark.asyncio
    async def test_debounce_different_files(self):
        """Test debouncing events for different files."""
        handler = DebounceHandler(delay=0.1)
        callback_mock = Mock()

        event1 = FileEvent(Path("/test/file1.py"), "modified", time.time())
        event2 = FileEvent(Path("/test/file2.py"), "modified", time.time())

        # Add events for different files
        await handler.add_event(event1, callback_mock)
        await handler.add_event(event2, callback_mock)

        # Wait for debounce delay
        await asyncio.sleep(0.15)

        # Should be called twice, once for each file
        assert callback_mock.call_count == 2
        callback_mock.assert_any_call(event1)
        callback_mock.assert_any_call(event2)

    @pytest.mark.asyncio
    async def test_cancel_all(self):
        """Test cancelling all pending timers."""
        handler = DebounceHandler(delay=0.1)
        callback_mock = Mock()

        event = FileEvent(Path("/test/file.py"), "modified", time.time())

        # Add event
        await handler.add_event(event, callback_mock)

        # Cancel all timers
        handler.cancel_all()

        # Wait beyond debounce delay
        await asyncio.sleep(0.15)

        # Callback should not be called
        assert not callback_mock.called


class TestFileWatcher:
    """Test the main FileWatcher functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.watch_dir = Path(self.temp_dir) / "apps"
        self.docs_dir = Path(self.temp_dir) / "docs"

        # Create directories
        self.watch_dir.mkdir(parents=True)
        self.docs_dir.mkdir(parents=True)

        # Create test config
        self.config = WatchConfig(
            watch_directory=self.watch_dir,
            output_directory=self.docs_dir,
            debounce_delay=0.1,
            max_retry_attempts=2,
            retry_delay=0.1,
            log_level="DEBUG",
        )

    def test_should_process_file(self):
        """Test file filtering logic."""
        watcher = FileWatcher(self.config)

        # Should process Python files
        assert watcher._should_process_file(self.watch_dir / "automation.py")
        assert watcher._should_process_file(self.watch_dir / "climate.py")

        # Should not process excluded files
        assert not watcher._should_process_file(self.watch_dir / "const.py")
        assert not watcher._should_process_file(self.watch_dir / "infra.py")
        assert not watcher._should_process_file(self.watch_dir / "__init__.py")

        # Should not process non-Python files
        assert not watcher._should_process_file(self.watch_dir / "config.yaml")
        assert not watcher._should_process_file(self.watch_dir / "README.md")

        # Should not process files outside watch directory
        other_dir = Path(self.temp_dir) / "other"
        assert not watcher._should_process_file(other_dir / "file.py")

    def test_scan_existing_files(self):
        """Test scanning for existing files."""
        # Create test files
        (self.watch_dir / "automation1.py").write_text("# Test file 1")
        (self.watch_dir / "automation2.py").write_text("# Test file 2")
        (self.watch_dir / "const.py").write_text("# Excluded file")
        (self.watch_dir / "config.yaml").write_text("# Non-Python file")

        watcher = FileWatcher(self.config)
        watcher._scan_existing_files()

        # Should find only the automation files
        assert len(watcher.watched_files) == 2
        assert self.watch_dir / "automation1.py" in watcher.watched_files
        assert self.watch_dir / "automation2.py" in watcher.watched_files
        assert self.watch_dir / "const.py" not in watcher.watched_files

    def test_get_status(self):
        """Test status reporting."""
        watcher = FileWatcher(self.config)

        status = watcher.get_status()

        assert isinstance(status, dict)
        assert "is_watching" in status
        assert "start_time" in status
        assert "uptime_seconds" in status
        assert "config" in status
        assert "watched_files" in status
        assert "statistics" in status
        assert "recent_events_count" in status
        assert "recent_results_count" in status
        assert "pending_events" in status

        # Check statistics structure
        stats = status["statistics"]
        assert "files_processed" in stats
        assert "successful_generations" in stats
        assert "failed_generations" in stats
        assert "total_events" in stats
        assert "retry_attempts" in stats

    def test_callback_registration(self):
        """Test generation callback registration."""
        watcher = FileWatcher(self.config)
        callback_mock = Mock()

        # Add callback
        watcher.add_generation_callback(callback_mock)

        # Verify callback is registered
        assert callback_mock in watcher._generation_callbacks

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using FileWatcher as async context manager."""
        with (
            patch.object(FileWatcher, "start_watching") as start_mock,
            patch.object(FileWatcher, "stop_watching") as stop_mock,
        ):
            async with FileWatcher(self.config) as watcher:
                assert isinstance(watcher, FileWatcher)
                start_mock.assert_called_once()

            stop_mock.assert_called_once()

    def test_get_recent_events(self):
        """Test getting recent events."""
        watcher = FileWatcher(self.config)

        # Add some test events
        for i in range(5):
            event = FileEvent(file_path=Path(f"/test/file{i}.py"), event_type="modified", timestamp=time.time() + i)
            watcher.recent_events.append(event)

        # Get recent events
        recent = watcher.get_recent_events(limit=3)

        assert len(recent) == 3
        assert all(isinstance(event, dict) for event in recent)
        assert all("file_path" in event for event in recent)
        assert all("event_type" in event for event in recent)
        assert all("timestamp" in event for event in recent)

    def test_get_recent_results(self):
        """Test getting recent generation results."""
        watcher = FileWatcher(self.config)

        # Add some test results
        for i in range(5):
            result = GenerationResult(
                success=i % 2 == 0,  # Alternate success/failure
                file_path=Path(f"/test/file{i}.py"),
                output_path=Path(f"/test/docs/file{i}.md") if i % 2 == 0 else None,
                error_message=f"Error {i}" if i % 2 == 1 else None,
                generation_time=1.0 + i * 0.1,
            )
            watcher.recent_results.append(result)

        # Get recent results
        recent = watcher.get_recent_results(limit=3)

        assert len(recent) == 3
        assert all(isinstance(result, dict) for result in recent)
        assert all("success" in result for result in recent)
        assert all("file_path" in result for result in recent)
        assert all("generation_time" in result for result in recent)

    def test_get_error_summary(self):
        """Test getting error summary."""
        watcher = FileWatcher(self.config)

        # Add some error data
        file1 = Path("/test/file1.py")
        file2 = Path("/test/file2.py")

        watcher.error_counts[file1] = 3
        watcher.error_counts[file2] = 1
        watcher.last_errors[file1] = "Syntax error"
        watcher.last_errors[file2] = "Import error"

        # Get error summary
        summary = watcher.get_error_summary()

        assert len(summary) == 2
        assert str(file1) in summary
        assert str(file2) in summary

        assert summary[str(file1)]["error_count"] == 3
        assert summary[str(file1)]["last_error"] == "Syntax error"
        assert summary[str(file2)]["error_count"] == 1
        assert summary[str(file2)]["last_error"] == "Import error"


@pytest.mark.asyncio
async def test_integration_example():
    """Test that the integration example can be imported without errors."""
    try:
        from server.watchers.integration_example import app

        assert app is not None
    except ImportError as e:
        pytest.skip(f"Integration example not importable: {e}")


# Performance test
@pytest.mark.asyncio
async def test_high_volume_events():
    """Test handling high volume of file events."""
    temp_dir = tempfile.mkdtemp()
    watch_dir = Path(temp_dir) / "apps"
    docs_dir = Path(temp_dir) / "docs"

    watch_dir.mkdir(parents=True)
    docs_dir.mkdir(parents=True)

    config = WatchConfig(
        watch_directory=watch_dir,
        output_directory=docs_dir,
        debounce_delay=0.05,  # Very short debounce for testing
        max_retry_attempts=1,
    )

    # Mock the batch generator to avoid actual file processing
    with patch("server.watchers.file_watcher.BatchDocGenerator") as mock_gen:
        mock_instance = Mock()
        mock_instance.generate_single_file_docs.return_value = ("# Test doc", True)
        mock_gen.return_value = mock_instance

        watcher = FileWatcher(config)

        # Create many test files
        test_files = []
        for i in range(20):
            file_path = watch_dir / f"test_file_{i}.py"
            file_path.write_text(f"# Test file {i}")
            test_files.append(file_path)

        # Simulate many rapid events
        events_processed = 0

        def count_events(result):
            nonlocal events_processed
            events_processed += 1

        watcher.add_generation_callback(count_events)

        # Add many events quickly
        for file_path in test_files:
            event = FileEvent(file_path=file_path, event_type="modified", timestamp=time.time())
            watcher._queue_for_processing(event)

        # Start processing briefly
        async with watcher:
            await asyncio.sleep(0.2)  # Let debouncing and processing happen

        # Verify some events were processed (exact number depends on debouncing)
        assert events_processed > 0
        assert events_processed <= len(test_files)  # Should not exceed due to debouncing


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
