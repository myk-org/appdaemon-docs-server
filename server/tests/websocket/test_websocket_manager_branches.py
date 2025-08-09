import json
import pytest

from server.websocket.websocket_manager import WebSocketManager, WebSocketEvent, EventType


@pytest.mark.asyncio
async def test_event_timestamp_is_not_overwritten_when_provided():
    # Cover branch where timestamp is provided and not overwritten
    e = WebSocketEvent(event_type=EventType.SYSTEM_STATUS, data={"a": 1}, timestamp=123.456)
    assert e.to_dict()["timestamp"] == 123.456


@pytest.mark.asyncio
async def test_handle_client_message_sends_error_on_invalid_json(monkeypatch):
    manager = WebSocketManager()

    sent_events = []

    async def fake_send(ws, event):
        sent_events.append(event)

    manager._send_to_client = fake_send  # type: ignore[assignment]

    class DummyWS:
        pass

    await manager.handle_client_message(DummyWS(), "not-json")
    # Should send an error event
    assert any(ev.event_type == EventType.SYSTEM_STATUS for ev in sent_events)


@pytest.mark.asyncio
async def test_handle_client_message_reports_unknown_type(monkeypatch):
    manager = WebSocketManager()
    sent = []

    async def fake_send(ws, event):
        sent.append(event)

    manager._send_to_client = fake_send  # type: ignore[assignment]

    class DummyWS:
        pass

    await manager.handle_client_message(DummyWS(), json.dumps({"type": "unknown"}))
    assert any("Unknown message type" in (ev.data.get("error") or "") for ev in sent)


@pytest.mark.asyncio
async def test_broadcast_handles_publish_exception_without_raising(monkeypatch):
    manager = WebSocketManager()

    async def boom(_):
        raise RuntimeError("boom")

    manager.get_sse_broker().publish = boom  # type: ignore[attr-defined]

    # Should not raise
    await manager.broadcast(WebSocketEvent(EventType.SYSTEM_STATUS, {"x": 1}))


@pytest.mark.asyncio
async def test_broadcast_cleans_up_failed_connections(monkeypatch):
    manager = WebSocketManager()

    class BadWS:
        async def send_text(self, txt):
            raise RuntimeError("send failure")

    ws = BadWS()
    manager._connections.add(ws)  # type: ignore[arg-type]

    await manager.broadcast(WebSocketEvent(EventType.SYSTEM_STATUS, {}))

    # Connection should be cleaned up
    assert ws not in manager._connections


@pytest.mark.asyncio
async def test_connect_gracefully_handles_accept_exception(monkeypatch):
    manager = WebSocketManager()

    class WS:
        async def accept(self):
            raise RuntimeError("accept fail")

    ws = WS()
    # Should swallow the error and not add connection
    await manager.connect(ws)  # type: ignore[arg-type]
    assert manager.get_connection_count() == 0
