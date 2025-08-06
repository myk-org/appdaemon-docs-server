"""Tests for WebSocket manager."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.websocket.websocket_manager import EventType, WebSocketEvent, WebSocketManager


class TestWebSocketEvent:
    """Test cases for WebSocketEvent class."""

    def test_websocket_event_creation(self):
        """Test WebSocketEvent creation."""
        event = WebSocketEvent(event_type=EventType.BATCH_STARTED, data={"message": "Starting batch", "files": 5})

        assert event.event_type == EventType.BATCH_STARTED
        assert event.data == {"message": "Starting batch", "files": 5}

    def test_websocket_event_to_dict(self):
        """Test WebSocketEvent to_dict method."""
        event = WebSocketEvent(
            event_type=EventType.BATCH_COMPLETED, data={"message": "Batch complete", "success": True}
        )

        result = event.to_dict()
        assert result["event_type"] == "batch_completed"
        assert result["data"] == {"message": "Batch complete", "success": True}
        assert "timestamp" in result

    def test_websocket_event_no_data(self):
        """Test WebSocketEvent without data."""
        event = WebSocketEvent(event_type=EventType.SERVER_STATUS, data={"message": "Server ready"})

        result = event.to_dict()
        assert result["event_type"] == "server_status"
        assert result["data"] == {"message": "Server ready"}


class TestWebSocketManager:
    """Test cases for WebSocketManager class."""

    @pytest.fixture
    def manager(self):
        """Create a WebSocketManager instance for testing."""
        return WebSocketManager()

    def test_init(self, manager):
        """Test WebSocketManager initialization."""
        assert len(manager._connections) == 0
        assert manager.stats["events_sent"] == 0

    @pytest.mark.asyncio
    async def test_connect(self, manager):
        """Test WebSocket connection."""
        mock_websocket = AsyncMock()

        await manager.connect(mock_websocket)

        assert mock_websocket in manager._connections
        assert len(manager._connections) == 1
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, manager):
        """Test WebSocket disconnection."""
        mock_websocket = AsyncMock()

        # Connect first
        await manager.connect(mock_websocket)
        assert len(manager._connections) == 1

        # Then disconnect
        await manager.disconnect(mock_websocket)
        assert len(manager._connections) == 0

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self, manager):
        """Test disconnecting a websocket that wasn't connected."""
        mock_websocket = AsyncMock()

        # Should not raise an error
        await manager.disconnect(mock_websocket)
        assert len(manager._connections) == 0

    @pytest.mark.asyncio
    async def test_send_to_client_success(self, manager):
        """Test sending message to single websocket."""
        mock_websocket = AsyncMock()
        event = WebSocketEvent(event_type=EventType.SYSTEM_STATUS, data={"message": "test"})

        await manager._send_to_client(mock_websocket, event)

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_client_failure(self, manager):
        """Test sending message to websocket with failure."""
        mock_websocket = AsyncMock()
        mock_websocket.send_text.side_effect = Exception("Send failed")
        event = WebSocketEvent(event_type=EventType.SYSTEM_STATUS, data={"message": "test"})

        with pytest.raises(Exception):
            await manager._send_to_client(mock_websocket, event)

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_with_connections(self, manager):
        """Test broadcasting to connected websockets."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await manager.connect(mock_ws1)
        await manager.connect(mock_ws2)

        event = WebSocketEvent(event_type=EventType.BATCH_STARTED, data={"message": "Test broadcast"})

        with patch.object(manager, "_send_to_client") as mock_send:
            result = await manager.broadcast(event)

            assert mock_send.call_count == 2
            assert result == 2

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self, manager):
        """Test broadcasting with no connections."""
        event = WebSocketEvent(event_type=EventType.BATCH_STARTED, data={"message": "Test broadcast"})

        # Should not raise an error
        result = await manager.broadcast(event)
        assert result == 0

    @pytest.mark.asyncio
    async def test_broadcast_batch_status(self, manager):
        """Test broadcast_batch_status convenience method."""
        mock_websocket = AsyncMock()
        await manager.connect(mock_websocket)

        with patch.object(manager, "broadcast") as mock_broadcast:
            await manager.broadcast_batch_status(EventType.BATCH_COMPLETED, "Batch finished", {"files": 5})

            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args[0][0]
            assert isinstance(call_args, WebSocketEvent)
            assert call_args.event_type == EventType.BATCH_COMPLETED
            assert call_args.data["message"] == "Batch finished"
            assert call_args.data["files"] == 5

    def test_get_connection_info(self, manager):
        """Test get_connection_info method."""
        # Add some mock connections
        manager._connections = {Mock(), Mock(), Mock()}
        manager.stats["events_sent"] = 42

        info = manager.get_connection_info()

        assert info["active_connections"] == 3
        assert info["events_sent"] == 42
        assert "total_connections" in info
        assert "broadcast_errors" in info

    @pytest.mark.asyncio
    async def test_broadcast_with_failed_connections(self, manager):
        """Test broadcasting when some connections fail."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await manager.connect(mock_ws1)
        await manager.connect(mock_ws2)

        event = WebSocketEvent(event_type=EventType.BATCH_STARTED, data={"message": "Test broadcast"})

        # Mock first connection to fail, second to succeed
        async def mock_send_side_effect(ws, event):
            if ws == mock_ws1:
                raise Exception("Connection failed")

        with patch.object(manager, "_send_to_client", side_effect=mock_send_side_effect):
            result = await manager.broadcast(event)

            # Failed connection should be removed
            assert mock_ws1 not in manager._connections
            assert mock_ws2 in manager._connections
            assert result == 1

    def test_event_types_enum(self):
        """Test EventType enum values."""
        assert EventType.BATCH_STARTED.value == "batch_started"
        assert EventType.BATCH_COMPLETED.value == "batch_completed"
        assert EventType.BATCH_ERROR.value == "batch_error"
        assert EventType.DOC_GENERATION_COMPLETED.value == "doc_generation_completed"
        assert EventType.WATCHER_STATUS.value == "watcher_status"
        assert EventType.SERVER_STATUS.value == "server_status"

    @pytest.mark.asyncio
    async def test_multiple_connections_and_disconnections(self, manager):
        """Test multiple connection and disconnection cycles."""
        websockets = [AsyncMock() for _ in range(5)]

        # Connect all websockets
        for ws in websockets:
            await manager.connect(ws)

        assert len(manager._connections) == 5

        # Disconnect some
        for ws in websockets[:3]:
            await manager.disconnect(ws)

        assert len(manager._connections) == 2
        assert websockets[3] in manager._connections
        assert websockets[4] in manager._connections

    @pytest.mark.asyncio
    async def test_websocket_manager_global_instance(self):
        """Test that global websocket manager instance exists."""
        from server.websocket.websocket_manager import websocket_manager

        assert isinstance(websocket_manager, WebSocketManager)
        assert len(websocket_manager._connections) == 0
