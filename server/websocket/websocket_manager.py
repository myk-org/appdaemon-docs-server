"""
WebSocket Manager for Documentation Server

Manages WebSocket connections and provides real-time notifications for:
- File changes and documentation generation
- Batch processing status
- System events and error notifications
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class EventType(Enum):
    """Types of WebSocket events."""

    # File events
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"

    # Documentation generation events
    DOC_GENERATION_STARTED = "doc_generation_started"
    DOC_GENERATION_COMPLETED = "doc_generation_completed"
    DOC_GENERATION_ERROR = "doc_generation_error"
    DOC_GENERATION_PROGRESS = "doc_generation_progress"

    # Batch processing events
    BATCH_STARTED = "batch_started"
    BATCH_COMPLETED = "batch_completed"
    BATCH_ERROR = "batch_error"
    BATCH_PROGRESS = "batch_progress"

    # System events
    SYSTEM_STATUS = "system_status"
    WATCHER_STATUS = "watcher_status"
    SERVER_STATUS = "server_status"


@dataclass
class WebSocketEvent:
    """Represents a WebSocket event."""

    event_type: EventType
    data: dict[str, Any]
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Set timestamp if not provided."""
        if self.timestamp is None:
            import time

            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class WebSocketManager:
    """
    Manages WebSocket connections for real-time documentation updates.

    Features:
    - Connection management with automatic cleanup
    - Event broadcasting to all connected clients
    - Typed event system with enumerated event types
    - Error handling and graceful disconnection
    - Connection statistics and monitoring
    """

    def __init__(self) -> None:
        """Initialize the WebSocket manager."""
        self.logger = logging.getLogger(__name__)

        # Active connections
        self._connections: set[WebSocket] = set()

        # Event tracking
        self._event_count = 0
        self._connection_count = 0

        # Statistics
        self.stats = {
            "total_connections": 0,
            "current_connections": 0,
            "events_sent": 0,
            "broadcast_errors": 0,
        }

    async def connect(self, websocket: WebSocket) -> None:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept
        """
        try:
            await websocket.accept()
            self._connections.add(websocket)
            self._connection_count += 1
            self.stats["total_connections"] += 1
            self.stats["current_connections"] = len(self._connections)

            self.logger.info(f"WebSocket connected. Total connections: {len(self._connections)}")

            # Send welcome message
            welcome_event = WebSocketEvent(
                event_type=EventType.SYSTEM_STATUS,
                data={
                    "message": "Connected to documentation server",
                    "connection_id": self._connection_count,
                    "active_connections": len(self._connections),
                },
            )
            await self._send_to_client(websocket, welcome_event)

        except Exception as e:
            self.logger.error(f"Error accepting WebSocket connection: {e}")
            self._connections.discard(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Handle WebSocket disconnection.

        Args:
            websocket: The WebSocket connection to disconnect
        """
        try:
            self._connections.discard(websocket)
            self.stats["current_connections"] = len(self._connections)

            self.logger.info(f"WebSocket disconnected. Total connections: {len(self._connections)}")

        except Exception as e:
            self.logger.error(f"Error handling WebSocket disconnection: {e}")

    async def handle_client_message(self, websocket: WebSocket, message: str) -> None:
        """
        Handle incoming message from WebSocket client.

        Args:
            websocket: The WebSocket connection
            message: Raw message string from client
        """
        try:
            # Parse JSON message
            data = json.loads(message)
            message_type = data.get("type", "unknown")

            self.logger.debug(f"Received WebSocket message: {message_type}")

            # Handle different message types
            if message_type == "ping":
                response = WebSocketEvent(
                    event_type=EventType.SYSTEM_STATUS, data={"message": "pong", "server_time": data.get("timestamp")}
                )
                await self._send_to_client(websocket, response)

            elif message_type == "status_request":
                status_event = WebSocketEvent(
                    event_type=EventType.SERVER_STATUS,
                    data={
                        "connections": len(self._connections),
                        "events_sent": self.stats["events_sent"],
                        "uptime": "running",
                    },
                )
                await self._send_to_client(websocket, status_event)

            else:
                # Unknown message type
                error_event = WebSocketEvent(
                    event_type=EventType.SYSTEM_STATUS, data={"error": f"Unknown message type: {message_type}"}
                )
                await self._send_to_client(websocket, error_event)

        except json.JSONDecodeError:
            error_event = WebSocketEvent(event_type=EventType.SYSTEM_STATUS, data={"error": "Invalid JSON message"})
            await self._send_to_client(websocket, error_event)

        except Exception as e:
            self.logger.error(f"Error handling client message: {e}")
            error_event = WebSocketEvent(
                event_type=EventType.SYSTEM_STATUS, data={"error": "Server error processing message"}
            )
            await self._send_to_client(websocket, error_event)

    async def broadcast(self, event: WebSocketEvent) -> int:
        """
        Broadcast an event to all connected clients.

        Args:
            event: The event to broadcast

        Returns:
            Number of clients that received the event
        """
        if not self._connections:
            return 0

        successful_sends = 0
        failed_connections = set()

        for websocket in self._connections.copy():
            try:
                await self._send_to_client(websocket, event)
                successful_sends += 1

            except Exception as e:
                self.logger.warning(f"Failed to send event to WebSocket client: {e}")
                failed_connections.add(websocket)
                self.stats["broadcast_errors"] += 1

        # Clean up failed connections
        for websocket in failed_connections:
            await self.disconnect(websocket)

        if successful_sends > 0:
            self.stats["events_sent"] += successful_sends
            self.logger.debug(f"Broadcast event {event.event_type.value} to {successful_sends} clients")

        return successful_sends

    async def _send_to_client(self, websocket: WebSocket, event: WebSocketEvent) -> None:
        """
        Send an event to a specific WebSocket client.

        Args:
            websocket: The WebSocket connection
            event: The event to send
        """
        try:
            message = json.dumps(event.to_dict())
            await websocket.send_text(message)

        except WebSocketDisconnect:
            # Client disconnected, this is normal
            await self.disconnect(websocket)
            raise

        except Exception as e:
            # Other errors - log and re-raise
            self.logger.error(f"Error sending WebSocket message: {e}")
            raise

    # Convenience methods for specific event types

    async def broadcast_file_change(self, file_path: str, event_type: EventType) -> int:
        """
        Broadcast a file change event.

        Args:
            file_path: Path to the changed file
            event_type: Type of file change event

        Returns:
            Number of clients notified
        """
        event = WebSocketEvent(
            event_type=event_type,
            data={"file_path": file_path, "filename": file_path.split("/")[-1] if "/" in file_path else file_path},
        )
        return await self.broadcast(event)

    async def broadcast_generation_progress(self, current: int, total: int, current_file: str, stage: str) -> int:
        """
        Broadcast documentation generation progress.

        Args:
            current: Current file number
            total: Total number of files
            current_file: Name of file being processed
            stage: Current processing stage

        Returns:
            Number of clients notified
        """
        event = WebSocketEvent(
            event_type=EventType.DOC_GENERATION_PROGRESS,
            data={
                "current": current,
                "total": total,
                "current_file": current_file,
                "stage": stage,
                "progress_percentage": (current / total * 100) if total > 0 else 0,
            },
        )
        return await self.broadcast(event)

    async def broadcast_batch_status(
        self, event_type: EventType, message: str, data: dict[str, Any] | None = None
    ) -> int:
        """
        Broadcast a batch processing status event.

        Args:
            event_type: Type of batch event
            message: Status message
            data: Additional event data

        Returns:
            Number of clients notified
        """
        event_data = {"message": message}
        if data:
            event_data.update(data)

        event = WebSocketEvent(event_type=event_type, data=event_data)
        return await self.broadcast(event)

    # Status and monitoring methods

    def get_connection_count(self) -> int:
        """Get current number of active connections."""
        return len(self._connections)

    def get_connection_info(self) -> dict[str, Any]:
        """Get detailed connection information."""
        return {
            "active_connections": len(self._connections),
            "total_connections": self.stats["total_connections"],
            "events_sent": self.stats["events_sent"],
            "broadcast_errors": self.stats["broadcast_errors"],
        }

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics."""
        self.stats["current_connections"] = len(self._connections)
        return self.stats.copy()


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
