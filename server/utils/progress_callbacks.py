"""Shared progress callback utilities for documentation generation."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Any


logger = logging.getLogger(__name__)


class ProgressCallbackManager:
    """Manages progress callbacks for documentation generation with WebSocket broadcasting."""

    def __init__(self, websocket_manager: Any, pending_tasks: set[asyncio.Task[Any]] | None = None):
        """Initialize progress callback manager.

        Args:
            websocket_manager: WebSocket manager for broadcasting progress
            pending_tasks: Optional set to track pending async tasks
        """
        self.websocket_manager = websocket_manager
        self.pending_tasks = pending_tasks or set()

    async def async_progress_callback(self, current: int, total: int, current_file: str, stage: str) -> None:
        """Async progress callback that broadcasts to WebSocket clients.

        Args:
            current: Current item being processed
            total: Total number of items to process
            current_file: Name of current file being processed
            stage: Current processing stage
        """
        logger.debug(f"Generation progress: {current}/{total} - {current_file} ({stage})")
        await self.websocket_manager.broadcast_generation_progress(
            current=current, total=total, current_file=current_file, stage=stage
        )

    def sync_progress_callback(self, current: int, total: int, current_file: str, stage: str) -> None:
        """Sync wrapper for async progress callback.

        Creates async task and optionally tracks it for proper cleanup.

        Args:
            current: Current item being processed
            total: Total number of items to process
            current_file: Name of current file being processed
            stage: Current processing stage
        """
        task = asyncio.create_task(self.async_progress_callback(current, total, current_file, stage))

        if self.pending_tasks is not None:
            self.pending_tasks.add(task)
            task.add_done_callback(self.pending_tasks.discard)

    def get_sync_callback(self) -> Callable[[int, int, str, str], None]:
        """Get the sync progress callback function.

        Returns:
            Sync progress callback function
        """
        return self.sync_progress_callback
