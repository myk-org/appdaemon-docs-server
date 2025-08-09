"""
File Watcher for AppDaemon Documentation Generator

This module provides a robust file watching system that automatically regenerates
documentation when Python source files change, with debouncing, error handling,
and comprehensive logging.
"""

import asyncio
import logging
import os
import time
import shutil
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from weakref import WeakSet

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from server.generators.batch_doc_generator import BatchDocGenerator
from server.utils.progress_callbacks import ProgressCallbackManager
from server.websocket.websocket_manager import websocket_manager, EventType


@dataclass
class WatchConfig:
    """Configuration for file watching behavior."""

    # Directory paths with robust defaults
    # Real apps directory to watch for changes
    watch_directory: Path = field(default_factory=lambda: Path(os.getenv("APPS_DIR") or "/app/appdaemon-apps"))
    # Directory used for generation (typically the mirrored/copied apps)
    generation_directory: Path | None = None
    output_directory: Path = field(default_factory=lambda: Path(os.getenv("DOCS_DIR") or "/app/docs"))

    # File filtering
    file_patterns: set[str] = field(default_factory=lambda: {"*.py"})
    excluded_files: set[str] = field(
        default_factory=lambda: {
            "const.py",
            "infra.py",
            "utils.py",
            "__init__.py",
            "apps.py",
            "configuration.py",
            "secrets.py",
        }
    )

    # Timing configuration
    debounce_delay: float = 2.0  # seconds
    max_retry_attempts: int = 3
    retry_delay: float = 1.0  # seconds between retries

    # Processing options
    force_regenerate: bool = False
    batch_processing: bool = True

    # Logging configuration
    log_level: str = "INFO"
    max_recent_events: int = 100


@dataclass
class FileEvent:
    """Represents a file system event with metadata."""

    file_path: Path
    event_type: str
    timestamp: float
    retry_count: int = 0

    def __init__(self, file_path: Path | str, event_type: str, timestamp: float, retry_count: int = 0) -> None:
        """Initialize FileEvent with automatic path conversion."""
        self.file_path = Path(file_path) if isinstance(file_path, str) else file_path
        self.event_type = event_type
        self.timestamp = timestamp
        self.retry_count = retry_count

        if self.timestamp <= 0:
            raise ValueError("Timestamp must be positive")

        if self.retry_count < 0:
            raise ValueError("Retry count cannot be negative")


@dataclass
class GenerationResult:
    """Result of a documentation generation operation."""

    success: bool
    file_path: Path
    output_path: Path | None = None
    error_message: str | None = None
    generation_time: float = 0.0
    retry_count: int = 0


class DebounceHandler:
    """Handles debouncing of file system events."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self._pending_events: dict[Path, FileEvent] = {}
        self._timer_tasks: dict[Path, asyncio.Task[None]] = {}

    async def add_event(self, event: FileEvent, callback: Callable[[FileEvent], None]) -> None:
        """Add an event to be debounced."""
        file_path = event.file_path

        # Cancel existing timer for this file
        if file_path in self._timer_tasks:
            self._timer_tasks[file_path].cancel()

        # Store the latest event
        self._pending_events[file_path] = event

        # Create new timer
        self._timer_tasks[file_path] = asyncio.create_task(self._delayed_callback(file_path, callback))

    async def _delayed_callback(self, file_path: Path, callback: Callable[[FileEvent], None]) -> None:
        """Execute callback after delay."""
        try:
            await asyncio.sleep(self.delay)

            # Get the event and clean up
            event = self._pending_events.pop(file_path, None)
            self._timer_tasks.pop(file_path, None)

            if event:
                callback(event)
        except asyncio.CancelledError:
            # Timer was cancelled, clean up
            self._pending_events.pop(file_path, None)
            self._timer_tasks.pop(file_path, None)

    def cancel_all(self) -> None:
        """Cancel all pending timers."""
        for task in self._timer_tasks.values():
            task.cancel()
        self._pending_events.clear()
        self._timer_tasks.clear()


class FileWatchEventHandler(FileSystemEventHandler):  # type: ignore[misc]
    """Handles file system events for the watcher."""

    def __init__(self, watcher: "FileWatcher"):
        super().__init__()
        self.watcher = watcher
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _attach_future_logging(self, future: Any, context: str) -> None:
        """Attach a done-callback that logs exceptions from the future.

        This ensures errors raised inside background coroutines are not silently dropped.
        """
        try:

            def _on_done(f: Any) -> None:
                try:
                    # Calling result() will re-raise any exception from the coroutine
                    f.result()
                except Exception as exc:  # noqa: BLE001 - we want to log any exception
                    self.logger.error(f"Unhandled exception in background task ({context}): {exc}")

            future.add_done_callback(_on_done)
        except Exception as exc:  # Defensive: attaching callback itself should not break flow
            self.logger.error(f"Failed to attach done callback for ({context}): {exc}")

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if not event.is_directory:
            self._handle_file_event(event, "modified")

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory:
            self._handle_file_event(event, "created")

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events."""
        if not event.is_directory:
            self._handle_file_event(event, "moved")

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if not event.is_directory:
            self._handle_file_event(event, "deleted")

    def _handle_file_event(self, event: FileSystemEvent, event_type: str) -> None:
        """Process a file system event."""
        try:
            file_path = Path(os.fsdecode(event.src_path))

            # Broadcast WebSocket event for all file changes (not just processed ones)
            if self.watcher.loop:
                fut = asyncio.run_coroutine_threadsafe(
                    self._broadcast_file_change(file_path, event_type), self.watcher.loop
                )
                self._attach_future_logging(fut, "broadcast_file_change")

            # Check if file should be processed
            if self.watcher._should_process_file(file_path):
                file_event = FileEvent(file_path=file_path, event_type=event_type, timestamp=time.time())

                self.logger.debug(f"File {event_type}: {file_path}")

                # Schedule debounced processing
                if self.watcher.loop:
                    try:
                        fut2 = asyncio.run_coroutine_threadsafe(
                            self.watcher._schedule_debounced_processing(file_event), self.watcher.loop
                        )
                        self._attach_future_logging(fut2, "schedule_debounced_processing")
                    except Exception as exc:  # noqa: BLE001 - we want to log any exception
                        self.logger.error(f"Failed to schedule debounced processing: {exc}")

        except Exception as e:
            self.logger.error(f"Error handling file event: {e}")

    async def _broadcast_file_change(self, file_path: Path, event_type: str) -> None:
        """Broadcast file change event via WebSocket."""
        try:
            # Map event types to WebSocket event types
            event_mapping = {
                "created": EventType.FILE_CREATED,
                "modified": EventType.FILE_MODIFIED,
                "deleted": EventType.FILE_DELETED,
                "moved": EventType.FILE_MODIFIED,  # Treat moves as modifications
            }

            ws_event_type = event_mapping.get(event_type, EventType.FILE_MODIFIED)

            # Broadcast to WebSocket clients
            await websocket_manager.broadcast_file_change(str(file_path), ws_event_type)

        except Exception as e:
            self.logger.error(f"Error broadcasting file change via WebSocket: {e}")


class FileWatcher:
    """
    Robust file watcher for AppDaemon documentation generation.

    Features:
    - Debounced file change processing
    - Error handling with retry logic
    - Comprehensive logging and status tracking
    - Integration with BatchDocGenerator
    - Configurable watch patterns and exclusions
    """

    def __init__(self, config: WatchConfig | None = None) -> None:
        """
        Initialize the file watcher.

        Args:
            config: Watch configuration, defaults to WatchConfig()

        Raises:
            ValueError: If configuration parameters are invalid
        """
        self.config = config or WatchConfig()

        # Validate configuration parameters
        self._validate_config()

        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, self.config.log_level.upper()))

        # Normalize generation directory (default to watch_directory when not specified)
        if self.config.generation_directory is None:
            self.config.generation_directory = self.config.watch_directory

        # Core components
        self.batch_generator = BatchDocGenerator(self.config.generation_directory, self.config.output_directory)

        # Watchdog components
        self.observer = Observer()
        self.event_handler = FileWatchEventHandler(self)

        # Debouncing and processing
        self.debounce_handler = DebounceHandler(self.config.debounce_delay)
        self._processing_queue: asyncio.Queue[FileEvent] = asyncio.Queue()
        self._processing_task: asyncio.Task[None] | None = None
        self.loop: asyncio.AbstractEventLoop | None = None

        # Status tracking
        self.is_watching = False
        self.start_time: float | None = None
        self.stats = {
            "files_processed": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "total_events": 0,
            "retry_attempts": 0,
        }

        # Event history
        self.recent_events: deque[FileEvent] = deque(maxlen=self.config.max_recent_events)
        self.recent_results: deque[GenerationResult] = deque(maxlen=self.config.max_recent_events)

        # Currently watched files
        self.watched_files: set[Path] = set()

        # Error tracking
        self.error_counts: dict[Path, int] = defaultdict(int)
        self.last_errors: dict[Path, str] = {}

        # Callbacks for external integration
        self._generation_callbacks: WeakSet[Callable[[GenerationResult], None]] = WeakSet()

    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if self.config.debounce_delay < 0:
            raise ValueError("Debounce delay must be non-negative")

        if self.config.max_retry_attempts < 0:
            raise ValueError("Max retry attempts must be non-negative")

        if self.config.retry_delay < 0:
            raise ValueError("Retry delay must be non-negative")

        if not self.config.file_patterns:
            raise ValueError("At least one file pattern must be specified")

        if self.config.max_recent_events <= 0:
            raise ValueError("Max recent events must be positive")

    def add_generation_callback(self, callback: Callable[[GenerationResult], None]) -> None:
        """Add a callback to be called when generation completes."""
        self._generation_callbacks.add(callback)

    def _should_process_file(self, file_path: Path) -> bool:
        """Check if a file should be processed for documentation generation."""
        # Check file extension
        if not any(file_path.match(pattern) for pattern in self.config.file_patterns):
            return False

        # Check excluded files
        if file_path.name in self.config.excluded_files:
            return False

        # Check if file is in watch directory
        try:
            file_path.relative_to(self.config.watch_directory)
        except ValueError:
            return False

        return True

    def _scan_existing_files(self) -> None:
        """Scan for existing files in the watch directory."""
        self.watched_files.clear()

        try:
            for pattern in self.config.file_patterns:
                for file_path in self.config.watch_directory.glob(pattern):
                    if self._should_process_file(file_path):
                        self.watched_files.add(file_path)

            self.logger.info(f"Found {len(self.watched_files)} files to watch")

        except Exception as e:
            self.logger.error(f"Error scanning existing files: {e}")

    async def _schedule_debounced_processing(self, event: FileEvent) -> None:
        """Schedule debounced processing of a file event."""
        await self.debounce_handler.add_event(event, self._queue_for_processing)

    def _queue_for_processing(self, event: FileEvent) -> None:
        """Queue an event for processing."""
        self.recent_events.append(event)
        self.stats["total_events"] += 1

        try:
            if self.loop is not None:
                asyncio.run_coroutine_threadsafe(self._processing_queue.put(event), self.loop)
            else:
                # Attempt to schedule on current running loop if available
                loop = asyncio.get_running_loop()
                loop.create_task(self._processing_queue.put(event))
        except RuntimeError:
            # If no event loop is running, we'll handle this gracefully
            self.logger.warning("No event loop running, event will be processed when watcher starts")

    async def _process_events(self) -> None:
        """Main event processing loop."""
        while True:
            try:
                event = await self._processing_queue.get()
                await self._process_single_event(event)
                self._processing_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in event processing loop: {e}")
                await asyncio.sleep(1)  # Brief pause before continuing

    async def _process_single_event(self, event: FileEvent) -> None:
        """Process a single file event with retry logic."""
        file_path = event.file_path
        max_retries = self.config.max_retry_attempts

        # Opportunistically sync source .py file for read-only viewing on create/modify
        try:
            if file_path.suffix == ".py" and event.event_type in {"created", "modified", "moved"}:
                dest_base = Path(os.getenv("APP_SOURCES_DIR", "data/app-sources")).resolve()
                excluded = {
                    "const.py",
                    "infra.py",
                    "utils.py",
                    "__init__.py",
                    "apps.py",
                    "configuration.py",
                    "secrets.py",
                }
                if file_path.name not in excluded and file_path.exists():
                    try:
                        rel = file_path.relative_to(self.config.watch_directory)
                    except ValueError:
                        rel = Path(file_path.name)
                    dest = dest_base / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, dest)
        except Exception as sync_err:
            # Do not fail the main processing due to sync errors
            self.logger.debug(f"Source sync skipped for {file_path}: {sync_err}")

        # Broadcast generation started event
        await websocket_manager.broadcast_batch_status(
            EventType.DOC_GENERATION_STARTED,
            f"Starting documentation generation for {file_path.name}",
            {"file_path": str(file_path), "current_file": file_path.name},
        )

        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()

                self.logger.info(f"Generating docs for {file_path.name} (attempt {attempt + 1})")

                # Generate documentation
                docs, success = self.batch_generator.generate_single_file_docs(file_path)

                if success:
                    # Write to output file
                    output_file = self.config.output_directory / f"{file_path.stem}.md"
                    output_file.write_text(docs, encoding="utf-8")

                    generation_time = time.time() - start_time

                    result = GenerationResult(
                        success=True,
                        file_path=file_path,
                        output_path=output_file,
                        generation_time=generation_time,
                        retry_count=attempt,
                    )

                    self.stats["files_processed"] += 1
                    self.stats["successful_generations"] += 1
                    if attempt > 0:
                        self.stats["retry_attempts"] += attempt

                    # Clear error tracking for this file
                    self.error_counts.pop(file_path, None)
                    self.last_errors.pop(file_path, None)

                    self.logger.info(f"✅ Generated docs for {file_path.name} in {generation_time:.2f}s")

                    # Broadcast success event
                    await websocket_manager.broadcast_batch_status(
                        EventType.DOC_GENERATION_COMPLETED,
                        f"Successfully generated documentation for {file_path.name}",
                        {
                            "file_path": str(file_path),
                            "output_path": str(output_file),
                            "generation_time": generation_time,
                            "current_file": file_path.name,
                        },
                    )

                else:
                    # Generation failed but no exception
                    raise RuntimeError("Documentation generation returned failure status")

                # Record result and notify callbacks
                self.recent_results.append(result)
                self._notify_callbacks(result)

                return  # Success, exit retry loop

            except Exception as e:
                error_msg = str(e)
                self.error_counts[file_path] += 1
                self.last_errors[file_path] = error_msg

                if attempt < max_retries:
                    self.logger.warning(
                        f"Failed to generate docs for {file_path.name} (attempt {attempt + 1}): {error_msg}. "
                        f"Retrying in {self.config.retry_delay}s..."
                    )
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    # All retries exhausted
                    generation_time = time.time() - start_time

                    result = GenerationResult(
                        success=False,
                        file_path=file_path,
                        error_message=error_msg,
                        generation_time=generation_time,
                        retry_count=attempt,
                    )

                    self.stats["files_processed"] += 1
                    self.stats["failed_generations"] += 1
                    self.stats["retry_attempts"] += attempt

                    self.logger.error(
                        f"❌ Failed to generate docs for {file_path.name} after {max_retries + 1} attempts: {error_msg}"
                    )

                    # Broadcast error event
                    await websocket_manager.broadcast_batch_status(
                        EventType.DOC_GENERATION_ERROR,
                        f"Failed to generate documentation for {file_path.name}: {error_msg}",
                        {
                            "file_path": str(file_path),
                            "error_message": error_msg,
                            "retry_count": attempt,
                            "current_file": file_path.name,
                        },
                    )

                    # Record result and notify callbacks
                    self.recent_results.append(result)
                    self._notify_callbacks(result)

    def _notify_callbacks(self, result: GenerationResult) -> None:
        """Notify all registered callbacks of generation result."""
        for callback in list(self._generation_callbacks):
            try:
                callback(result)
            except Exception as e:
                self.logger.error(f"Error in generation callback: {e}")

    async def start_watching(self) -> None:
        """Start the file watcher."""
        if self.is_watching:
            self.logger.warning("File watcher is already running")
            return

        try:
            self.logger.info(f"Starting file watcher for {self.config.watch_directory}")

            # Ensure directories exist
            self.config.watch_directory.mkdir(parents=True, exist_ok=True)
            self.config.output_directory.mkdir(parents=True, exist_ok=True)

            # Scan existing files
            self._scan_existing_files()

            # Record the running loop for cross-thread scheduling
            self.loop = asyncio.get_running_loop()

            # Set up watchdog observer (support recursive when env enables it)
            recursive = os.getenv("RECURSIVE_SCAN", "false").lower() in ("true", "1", "yes", "on")
            self.observer.schedule(self.event_handler, str(self.config.watch_directory), recursive=recursive)

            # Start processing task
            self._processing_task = asyncio.create_task(self._process_events())

            # Start observer
            self.observer.start()

            self.is_watching = True
            self.start_time = time.time()

            self.logger.info(
                f"File watcher started successfully. "
                f"Watching {len(self.watched_files)} files with {self.config.debounce_delay}s debounce."
            )

        except Exception as e:
            self.logger.error(f"Failed to start file watcher: {e}")
            await self.stop_watching()
            raise

    async def stop_watching(self) -> None:
        """Stop the file watcher."""
        if not self.is_watching:
            return

        self.logger.info("Stopping file watcher...")

        try:
            # Stop observer
            if self.observer.is_alive():
                self.observer.stop()
                self.observer.join(timeout=5.0)

            # Cancel debounce timers
            self.debounce_handler.cancel_all()

            # Cancel processing task
            if self._processing_task and not self._processing_task.done():
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass

            # Clear processing queue
            while not self._processing_queue.empty():
                try:
                    self._processing_queue.get_nowait()
                    self._processing_queue.task_done()
                except asyncio.QueueEmpty:
                    break

            self.is_watching = False

            uptime = time.time() - self.start_time if self.start_time else 0
            self.logger.info(f"File watcher stopped. Uptime: {uptime:.1f}s")

        except Exception as e:
            self.logger.error(f"Error stopping file watcher: {e}")

        finally:
            self.is_watching = False

    async def generate_all_docs(self, force: bool = False) -> dict[str, Any]:
        """
        Generate documentation for all watched files.

        Args:
            force: Force regeneration even if docs already exist

        Returns:
            Dictionary with generation results
        """
        self.logger.info("Starting full documentation generation...")

        # Broadcast batch started event
        await websocket_manager.broadcast_batch_status(
            EventType.BATCH_STARTED,
            "Starting full documentation generation...",
            {"force_regenerate": force or self.config.force_regenerate},
        )

        # Create progress callback for WebSocket broadcasting
        progress_manager = ProgressCallbackManager(websocket_manager)

        start_time = time.time()
        results: dict[str, Any] = self.batch_generator.generate_all_docs(
            force_regenerate=force or self.config.force_regenerate,
            progress_callback=progress_manager.sync_progress_callback,
        )
        generation_time = time.time() - start_time

        # Update statistics
        self.stats["files_processed"] += results["total_files"]
        self.stats["successful_generations"] += results["successful"]
        self.stats["failed_generations"] += results["failed"]

        self.logger.info(
            f"Full generation complete in {generation_time:.2f}s: "
            f"{results['successful']} successful, {results['failed']} failed, {results['skipped']} skipped"
        )

        # Broadcast batch completed event
        if results["failed"] > 0:
            await websocket_manager.broadcast_batch_status(
                EventType.BATCH_ERROR,
                f"Batch generation completed with errors: {results['failed']} failed",
                {
                    "total_files": results["total_files"],
                    "successful": results["successful"],
                    "failed": results["failed"],
                    "skipped": results["skipped"],
                    "generation_time": generation_time,
                },
            )
        else:
            await websocket_manager.broadcast_batch_status(
                EventType.BATCH_COMPLETED,
                f"Batch generation completed successfully: {results['successful']} files processed",
                {
                    "total_files": results["total_files"],
                    "successful": results["successful"],
                    "failed": results["failed"],
                    "skipped": results["skipped"],
                    "generation_time": generation_time,
                },
            )

        return results

    def get_status(self) -> dict[str, Any]:
        """Get current watcher status and statistics."""
        uptime = time.time() - self.start_time if self.start_time else 0

        return {
            "is_watching": self.is_watching,
            "start_time": self.start_time,
            "uptime_seconds": uptime,
            "config": {
                "watch_directory": str(self.config.watch_directory),
                "output_directory": str(self.config.output_directory),
                "debounce_delay": self.config.debounce_delay,
                "max_retry_attempts": self.config.max_retry_attempts,
            },
            "watched_files": [str(f) for f in sorted(self.watched_files)],
            "statistics": self.stats.copy(),
            "recent_events_count": len(self.recent_events),
            "recent_results_count": len(self.recent_results),
            "pending_events": self._processing_queue.qsize(),
            "files_with_errors": len(self.error_counts),
            "error_summary": dict(self.error_counts),
        }

    def get_recent_events(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent file events."""
        recent = list(self.recent_events)[-limit:]
        return [
            {
                "file_path": str(event.file_path),
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "retry_count": event.retry_count,
            }
            for event in recent
        ]

    def get_recent_results(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent generation results."""
        recent = list(self.recent_results)[-limit:]
        return [
            {
                "success": result.success,
                "file_path": str(result.file_path),
                "output_path": str(result.output_path) if result.output_path else None,
                "error_message": result.error_message,
                "generation_time": result.generation_time,
                "retry_count": result.retry_count,
            }
            for result in recent
        ]

    def get_error_summary(self) -> dict[str, dict[str, Any]]:
        """Get summary of files with errors."""
        return {
            str(file_path): {
                "error_count": count,
                "last_error": self.last_errors.get(file_path, "Unknown error"),
            }
            for file_path, count in self.error_counts.items()
        }

    async def __aenter__(self) -> "FileWatcher":
        """Async context manager entry."""
        await self.start_watching()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.stop_watching()
