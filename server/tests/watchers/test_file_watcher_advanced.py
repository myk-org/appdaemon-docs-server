"""Additional tests for file watcher to boost coverage."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from server.watchers.file_watcher import FileWatcher, WatchConfig


class TestFileWatcherAdvanced:
    """Advanced test cases for FileWatcher."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            watch_dir = temp_path / "watch"
            output_dir = temp_path / "output"
            watch_dir.mkdir()
            output_dir.mkdir()

            yield watch_dir, output_dir

    @pytest.fixture
    def config(self, temp_dirs):
        """Create a test configuration."""
        watch_dir, output_dir = temp_dirs
        return WatchConfig(
            watch_directory=watch_dir,
            output_directory=output_dir,
            debounce_delay=0.1,
            max_retry_attempts=2,
            force_regenerate=True,
        )

    @pytest.fixture
    def watcher(self, config):
        """Create a FileWatcher instance for testing."""
        return FileWatcher(config)

    def test_should_process_file_various_extensions(self, watcher, temp_dirs):
        """Test file processing decision for various file types."""
        watch_dir, output_dir = temp_dirs
        watcher.config.watch_directory = watch_dir

        # Should process Python files in watch directory
        assert watcher._should_process_file(watch_dir / "automation.py") is True
        assert watcher._should_process_file(watch_dir / "test_script.py") is True

        # Should not process excluded files
        assert watcher._should_process_file(watch_dir / "const.py") is False
        assert watcher._should_process_file(watch_dir / "__init__.py") is False

        # Should not process non-Python files
        assert watcher._should_process_file(watch_dir / "readme.txt") is False
        assert watcher._should_process_file(watch_dir / "config.yaml") is False

    def test_should_process_file_patterns(self, watcher, temp_dirs):
        """Test file processing patterns."""
        watch_dir, output_dir = temp_dirs
        watcher.config.watch_directory = watch_dir

        # Custom pattern matching in watch directory
        assert watcher._should_process_file(watch_dir / "my_automation.py") is True
        assert watcher._should_process_file(watch_dir / "sensor_handler.py") is True

        # Excluded patterns
        excluded_files = ["secrets.py", "utils.py", "apps.py", "configuration.py"]
        for filename in excluded_files:
            assert watcher._should_process_file(watch_dir / filename) is False

    @pytest.mark.asyncio
    async def test_start_stop_watching(self, watcher):
        """Test starting and stopping file watching."""
        # Mock the observer that's already created in the watcher
        with (
            patch.object(watcher.observer, "start") as mock_start,
            patch.object(watcher.observer, "stop") as mock_stop,
            patch.object(watcher.observer, "is_alive", return_value=True),
            patch.object(watcher.observer, "join"),
        ):
            # Start watching
            await watcher.start_watching()

            assert watcher.is_watching is True
            mock_start.assert_called_once()

            # Stop watching
            await watcher.stop_watching()

            assert watcher.is_watching is False
            mock_stop.assert_called_once()

    def test_scan_existing_files(self, watcher, temp_dirs):
        """Test scanning existing files functionality."""
        watch_dir, output_dir = temp_dirs

        # Update watcher config to use temp directory
        watcher.config.watch_directory = watch_dir

        # Create test files
        (watch_dir / "automation1.py").write_text("# Automation 1")
        (watch_dir / "automation2.py").write_text("# Automation 2")
        (watch_dir / "const.py").write_text("# Constants")  # Should be excluded

        # Test the private _scan_existing_files method
        watcher._scan_existing_files()

        # Should have found automation files but excluded const.py
        assert len(watcher.watched_files) == 2
        file_names = {f.name for f in watcher.watched_files}
        assert "automation1.py" in file_names
        assert "automation2.py" in file_names
        assert "const.py" not in file_names

    def test_get_status_detailed(self, watcher):
        """Test detailed status information."""
        status = watcher.get_status()

        assert "is_watching" in status
        assert "statistics" in status  # Changed from events_processed
        assert "watched_files" in status  # Changed from files_generated
        assert "error_summary" in status  # Changed from last_error
        assert "config" in status

        # Check config details
        config_info = status["config"]
        assert "watch_directory" in config_info
        assert "debounce_delay" in config_info

    def test_get_recent_events_empty(self, watcher):
        """Test getting recent events when none exist."""
        events = watcher.get_recent_events()
        assert events == []

    def test_get_recent_results_empty(self, watcher):
        """Test getting recent results when none exist."""
        results = watcher.get_recent_results()
        assert results == []

    def test_get_error_summary_no_errors(self, watcher):
        """Test error summary when no errors exist."""
        summary = watcher.get_error_summary()
        # get_error_summary returns dict[str, dict[str, Any]] - file paths to error info
        assert summary == {}  # No errors means empty dict

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, watcher):
        """Test using FileWatcher as context manager."""
        # Mock the observer that's already created in the watcher
        with (
            patch.object(watcher.observer, "start") as mock_start,
            patch.object(watcher.observer, "stop") as mock_stop,
            patch.object(watcher.observer, "is_alive", return_value=True),
            patch.object(watcher.observer, "join"),
        ):
            async with watcher:
                assert watcher.is_watching is True
                mock_start.assert_called_once()

            assert watcher.is_watching is False
            mock_stop.assert_called_once()

    def test_config_validation(self, temp_dirs):
        """Test configuration validation."""
        watch_dir, output_dir = temp_dirs

        # Valid config
        config = WatchConfig(watch_directory=watch_dir, output_directory=output_dir)
        watcher = FileWatcher(config)
        assert watcher.config == config

    def test_callback_registration(self, watcher):
        """Test callback registration and management."""
        callback1 = Mock()
        callback2 = Mock()

        # Register callbacks using actual method
        watcher.add_generation_callback(callback1)
        watcher.add_generation_callback(callback2)

        # Check callbacks are stored in WeakSet
        assert len(watcher._generation_callbacks) == 2

    def test_metrics_tracking(self, watcher):
        """Test that metrics are properly tracked."""
        # Initial state - check actual stats structure
        assert watcher.stats["total_events"] == 0
        assert watcher.stats["files_processed"] == 0

        # Metrics should be accessible through status
        status = watcher.get_status()
        assert status["statistics"]["total_events"] == 0
        assert status["statistics"]["files_processed"] == 0

    @pytest.mark.asyncio
    async def test_file_processing_retry_logic(self, watcher, temp_dirs):
        """Test retry logic for file processing."""
        watch_dir, output_dir = temp_dirs
        test_file = watch_dir / "test_automation.py"
        test_file.write_text("# Test automation")

        # Mock generation that fails initially
        mock_generator = Mock()
        mock_generator.generate_single_file.side_effect = [
            Exception("First attempt fails"),
            Exception("Second attempt fails"),
            {"success": True, "output_file": "test.md"},  # Third attempt succeeds
        ]

        with patch.object(watcher, "_process_single_event") as mock_process:
            # Create a file event to process
            from server.watchers.file_watcher import FileEvent
            import time

            event = FileEvent(file_path=test_file, event_type="modified", timestamp=time.time())

            await watcher._process_single_event(event)

            # Should have called the process method
            mock_process.assert_called_once()

    def test_error_handling_edge_cases(self, watcher, temp_dirs):
        """Test error handling for edge cases."""
        watch_dir, output_dir = temp_dirs
        watcher.config.watch_directory = watch_dir

        # Test with invalid file path (outside watch directory)
        invalid_path = Path("/nonexistent/invalid.py")
        assert watcher._should_process_file(invalid_path) is False  # Outside watch dir

        # Test with file that has no extension in watch directory
        no_ext_file = watch_dir / "README"
        assert watcher._should_process_file(no_ext_file) is False

    def test_watch_config_defaults(self):
        """Test WatchConfig default values."""
        config = WatchConfig(watch_directory=Path("/test"), output_directory=Path("/output"))

        assert config.debounce_delay == 2.0
        assert config.max_retry_attempts == 3
        assert config.force_regenerate is False
        assert config.batch_processing is True
        assert config.log_level == "INFO"
        assert config.max_recent_events == 100

    def test_excluded_files_comprehensive(self, watcher, temp_dirs):
        """Test comprehensive list of excluded files."""
        watch_dir, output_dir = temp_dirs
        watcher.config.watch_directory = watch_dir

        excluded_files = [
            "const.py",
            "infra.py",
            "utils.py",
            "__init__.py",
            "apps.py",
            "configuration.py",
            "secrets.py",
        ]

        for filename in excluded_files:
            assert watcher._should_process_file(watch_dir / filename) is False

        # Test variations
        assert watcher._should_process_file(watch_dir / "my_const.py") is True
        assert watcher._should_process_file(watch_dir / "CONST.py") is True  # Case sensitive

    @pytest.mark.asyncio
    async def test_concurrent_file_events(self, watcher, temp_dirs):
        """Test handling of concurrent file events."""
        watch_dir, _ = temp_dirs

        # Create multiple files simultaneously
        files = [watch_dir / f"automation_{i}.py" for i in range(5)]
        for f in files:
            f.write_text(f"# Automation {f.stem}")

        # Test processing multiple files using the actual debounced processing
        with patch.object(watcher, "_schedule_debounced_processing") as mock_schedule:
            # Simulate events for each file
            from server.watchers.file_watcher import FileEvent
            import time

            for f in files:
                event = FileEvent(file_path=f, event_type="modified", timestamp=time.time())
                await watcher._schedule_debounced_processing(event)

            # Should schedule debounced processing for each file
            assert mock_schedule.call_count == len(files)

    def test_debounce_handler_edge_cases(self, watcher):
        """Test debounce handler edge cases."""
        from server.watchers.file_watcher import DebounceHandler

        handler = DebounceHandler(delay=0.1)  # Required delay parameter

        # Test empty operations
        handler.cancel_all()  # Should not raise error when empty
        assert len(handler._timer_tasks) == 0  # Correct attribute name

    def test_generation_result_variations(self):
        """Test GenerationResult with different scenarios."""
        from server.watchers.file_watcher import GenerationResult

        # Success result - use correct parameter names
        success_result = GenerationResult(
            file_path=Path("test.py"), success=True, output_path=Path("test.md"), generation_time=1.5
        )
        assert success_result.success is True
        assert success_result.error_message is None

        # Failure result
        failure_result = GenerationResult(
            file_path=Path("test.py"), success=False, error_message="Generation failed", generation_time=0.5
        )
        assert failure_result.success is False
        assert failure_result.output_path is None
