"""Tests for the SSE endpoint and pagination/security additions."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Ensure required env vars exist for importing the app."""
    monkeypatch.setenv("APPS_DIR", "/tmp/test_apps")
    monkeypatch.setenv("DOCS_DIR", "/tmp/test_docs")
    monkeypatch.setenv("TEMPLATES_DIR", "server/templates")
    monkeypatch.setenv("STATIC_DIR", "server/static")
    monkeypatch.setenv("ENABLE_FILE_WATCHER", "false")
    yield


@pytest.fixture
def client(mock_env):
    from server.main import app

    return TestClient(app)


def test_sse_headers_and_close(client):
    # Use HEAD to validate headers without consuming the stream
    r = client.head("/sse")
    assert r.status_code == 200
    ctype = r.headers.get("content-type", "")
    assert "text/event-stream" in ctype


def test_files_pagination_returns_slice(client):
    files = [
        {"name": f"file{i}.md", "stem": f"file{i}", "size": 100 + i, "modified": 1700000000 + i, "title": f"File {i}"}
        for i in range(5)
    ]

    with patch("server.main.docs_service.get_file_list", return_value=files):
        resp = client.get("/api/files?limit=2&offset=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 5
        assert len(data["files"]) == 2
        assert data["files"][0]["name"] == "file1.md"
        assert data["limit"] == 2
        assert data["offset"] == 1


def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "Content-Security-Policy" in resp.headers
    assert "X-Content-Type-Options" in resp.headers
    assert "Referrer-Policy" in resp.headers


@pytest.mark.asyncio
async def test_sse_broker_publish_receive():
    from server.websocket.websocket_manager import websocket_manager, WebSocketEvent, EventType

    broker = websocket_manager.get_sse_broker()
    q = await broker.subscribe()
    try:
        event = WebSocketEvent(event_type=EventType.SYSTEM_STATUS, data={"message": "hello"})
        await broker.publish(event.to_dict())
        received = await q.get()
        assert received["event_type"] == EventType.SYSTEM_STATUS.value
        assert received["data"]["message"] == "hello"
    finally:
        await broker.unsubscribe(q)
