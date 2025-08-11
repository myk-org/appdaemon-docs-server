"""Extra tests for WebSocketManager SSE publishing and connection flow."""

from unittest.mock import AsyncMock, patch

import pytest

from server.websocket.websocket_manager import WebSocketEvent, EventType, WebSocketManager


@pytest.mark.asyncio
async def test_broadcast_publishes_to_sse():
    mgr = WebSocketManager()
    event = WebSocketEvent(event_type=EventType.SYSTEM_STATUS, data={"message": "ok"})

    # Connect a dummy websocket so broadcast doesn't early-return
    ws = AsyncMock()
    with patch.object(mgr, "_send_to_client", new=AsyncMock()):
        await mgr.connect(ws)

        # Subscribe and ensure publish occurs
        q = await mgr.get_sse_broker().subscribe()
        try:
            await mgr.broadcast(event)
            received = await q.get()
            assert received["event_type"] == "system_status"
        finally:
            await mgr.get_sse_broker().unsubscribe(q)


@pytest.mark.asyncio
async def test_connect_emits_connection_established():
    mgr = WebSocketManager()
    ws = AsyncMock()
    with patch.object(mgr, "_send_to_client", new=AsyncMock()) as send:
        await mgr.connect(ws)
        # Two initial messages: system_status and connection_established
        assert send.await_count >= 2
