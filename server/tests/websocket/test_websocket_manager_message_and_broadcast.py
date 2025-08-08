import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocketDisconnect

from server.websocket.websocket_manager import EventType, WebSocketEvent, WebSocketManager


@pytest.mark.asyncio
async def test_handle_client_message_ping_and_status_request():
    mgr = WebSocketManager()
    ws = AsyncMock()
    with patch.object(mgr, "_send_to_client", new=AsyncMock()) as send:
        await mgr.handle_client_message(ws, json.dumps({"type": "ping", "timestamp": 123}))
        await mgr.handle_client_message(ws, json.dumps({"type": "status_request"}))

        assert send.await_count >= 2
        sent_types = [call.args[1].event_type for call in send.await_args_list]
        assert EventType.SYSTEM_STATUS in sent_types
        assert EventType.SERVER_STATUS in sent_types


@pytest.mark.asyncio
async def test_send_to_client_handles_disconnect():
    mgr = WebSocketManager()
    ws = AsyncMock()
    ws.send_text.side_effect = WebSocketDisconnect()
    with patch.object(mgr, "disconnect", new=AsyncMock()) as disconnect:
        with pytest.raises(WebSocketDisconnect):
            await mgr._send_to_client(ws, WebSocketEvent(event_type=EventType.SYSTEM_STATUS, data={"x": 1}))
        disconnect.assert_awaited_once_with(ws)


@pytest.mark.asyncio
async def test_broadcast_with_connection_publishes_to_sse():
    mgr = WebSocketManager()
    ws = AsyncMock()
    mgr._connections.add(ws)
    with (
        patch.object(mgr, "_send_to_client", new=AsyncMock()),
        patch.object(mgr.get_sse_broker(), "publish", new=AsyncMock()) as publish,
    ):
        sent = await mgr.broadcast(WebSocketEvent(event_type=EventType.SYSTEM_STATUS, data={"msg": "hello"}))
        assert sent == 1
        publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_broadcast_errors_cleanup_and_stats():
    mgr = WebSocketManager()
    fake_ws = AsyncMock()
    mgr._connections.add(fake_ws)
    with (
        patch.object(mgr, "_send_to_client", new=AsyncMock(side_effect=Exception("boom"))),
        patch.object(mgr, "disconnect", new=AsyncMock()) as disconnect,
        patch.object(mgr.get_sse_broker(), "publish", new=AsyncMock()),
    ):
        sent = await mgr.broadcast(WebSocketEvent(event_type=EventType.SYSTEM_STATUS, data={"a": 1}))
        assert sent == 0
        disconnect.assert_awaited_once_with(fake_ws)
        assert mgr.stats["broadcast_errors"] >= 1


@pytest.mark.asyncio
async def test_progress_and_file_change_helpers():
    mgr = WebSocketManager()
    with patch.object(mgr, "broadcast", new=AsyncMock(return_value=0)) as b:
        await mgr.broadcast_generation_progress(current=0, total=0, current_file="x.py", stage="start")
        await mgr.broadcast_file_change("/tmp/a/b.py", EventType.FILE_CREATED)
        assert b.await_count == 2
        args_list = [call.args for call in b.await_args_list]
        assert args_list[0][0].event_type == EventType.DOC_GENERATION_PROGRESS
        assert args_list[1][0].event_type == EventType.FILE_CREATED


def test_stats_and_info_accessors():
    mgr = WebSocketManager()
    info = mgr.get_connection_info()
    stats = mgr.get_stats()
    assert "active_connections" in info
    assert "events_sent" in stats
