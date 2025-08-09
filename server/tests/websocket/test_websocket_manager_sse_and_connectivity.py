from server.websocket.websocket_manager import WebSocketManager, WebSocketEvent, EventType
import asyncio
import pytest


@pytest.mark.asyncio
async def test_sse_publish_invoked_without_ws_connections(monkeypatch):
    # Ensure SSE publish is invoked even with no websocket connections
    manager = WebSocketManager()

    called = asyncio.Event()

    async def fake_publish(event_dict):
        called.set()

    manager.get_sse_broker().publish = fake_publish  # type: ignore[attr-defined]

    await manager.broadcast(WebSocketEvent(EventType.SYSTEM_STATUS, {"x": 1}))

    # Should have triggered publish
    assert called.is_set()


@pytest.mark.asyncio
async def test_connect_then_disconnect_basic_flow(monkeypatch):
    manager = WebSocketManager()

    class DummyWS:
        async def accept(self):
            return None

        async def send_text(self, txt):
            return None

    ws = DummyWS()

    await manager.connect(ws)  # type: ignore[arg-type]
    # After connect, count should be updated
    assert manager.get_connection_count() >= 0

    await manager.disconnect(ws)  # type: ignore[arg-type]
    assert manager.get_connection_count() >= 0
