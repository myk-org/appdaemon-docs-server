"""Basic UI tests that work without complex async setup."""

import time
import subprocess
import tempfile
import requests
from pathlib import Path
import pytest


@pytest.fixture(scope="module")
def test_server():
    """Start a simple test server for UI validation."""
    # Create temporary directories
    apps_dir = Path(tempfile.mkdtemp(prefix="test_apps_"))
    docs_dir = Path(tempfile.mkdtemp(prefix="test_docs_"))

    # Create a simple test file
    (apps_dir / "test_app.py").write_text('''
"""Test automation app."""

class TestApp:
    """Simple test automation class."""

    def initialize(self):
        """Initialize the app."""
        pass

    def test_method(self):
        """Test method."""
        return "test"
''')

    # Set up environment
    import os

    env = os.environ.copy()
    env.update({
        "APPS_DIR": str(apps_dir),
        "DOCS_DIR": str(docs_dir),
        "HOST": "127.0.0.1",
        "PORT": "8081",  # Use different port to avoid conflicts
        "LOG_LEVEL": "error",
        "FORCE_REGENERATE": "true",
        "ENABLE_FILE_WATCHER": "false",
    })

    # Start server
    server_process = subprocess.Popen(
        ["uv", "run", "python", "server/run-dev.py"],
        cwd="/home/myakove/git/appdaemon-docs-server",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to be ready
    base_url = "http://127.0.0.1:8081"
    max_retries = 30
    for _ in range(max_retries):
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            pass
        time.sleep(1)
    else:
        server_process.terminate()
        raise RuntimeError("Test server failed to start")

    try:
        yield base_url
    finally:
        server_process.terminate()
        server_process.wait(timeout=10)

        # Cleanup
        import shutil

        shutil.rmtree(apps_dir, ignore_errors=True)
        shutil.rmtree(docs_dir, ignore_errors=True)


def test_server_health_endpoint(test_server):
    """Test that the server health endpoint works."""
    response = requests.get(f"{test_server}/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded", "unhealthy"]


def test_docs_homepage_loads(test_server):
    """Test that the main documentation page loads."""
    response = requests.get(f"{test_server}/docs/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")

    # Check for basic page elements
    content = response.text
    assert "<title>" in content
    assert "Documentation" in content
    assert "<!DOCTYPE html>" in content


def test_api_files_endpoint_returns_json(test_server):
    """Test that the API files endpoint returns JSON."""
    response = requests.get(f"{test_server}/api/files")
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")

    # Should be a dict with files list
    data = response.json()
    assert isinstance(data, dict)
    assert "files" in data
    assert isinstance(data["files"], list)


def test_regenerate_all_endpoint(test_server):
    """Test that the regenerate all endpoint works."""
    response = requests.post(f"{test_server}/api/generate/all")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "message" in data


def test_css_theme_variables_present(test_server):
    """Test that CSS custom properties for themes are present."""
    response = requests.get(f"{test_server}/docs/")
    assert response.status_code == 200
    content = response.text

    # Check for CSS custom properties
    assert "--bg-primary:" in content
    assert "--text-primary:" in content
    assert "--theme-transition:" in content
    assert '[data-theme="dark"]' in content


def test_regenerate_buttons_present(test_server):
    """Test that regenerate buttons are present in the UI."""
    response = requests.get(f"{test_server}/docs/")
    assert response.status_code == 200
    content = response.text

    # Check for regenerate all button
    assert "regenerateAllBtn" in content
    assert "Regenerate All" in content

    # Check for button styling
    assert "regenerate-button" in content


def test_theme_toggle_present(test_server):
    """Test that theme toggle is present."""
    response = requests.get(f"{test_server}/docs/")
    assert response.status_code == 200
    content = response.text

    assert "themeToggle" in content
    assert "theme-toggle" in content


def test_websocket_status_indicator_present(test_server):
    """Test that WebSocket status indicator is present."""
    response = requests.get(f"{test_server}/docs/")
    assert response.status_code == 200
    content = response.text

    assert "websocketStatus" in content
    assert "websocket-status" in content


def test_mermaid_support_present(test_server):
    """Test that Mermaid diagram support is present in document pages."""
    # First get the files list
    files_response = requests.get(f"{test_server}/api/files")
    files_data = files_response.json()

    if files_data.get("files"):  # If we have any docs
        # Get the first document page
        first_doc = files_data["files"][0]
        response = requests.get(f"{test_server}/docs/{first_doc['name']}")
        assert response.status_code == 200
        content = response.text

        # Check for Mermaid CDN and functions
        assert "mermaid" in content.lower()
        assert "renderMermaidDiagrams" in content
    else:
        # If no docs, just verify main page has the foundation
        response = requests.get(f"{test_server}/docs/")
        content = response.text
        # At minimum, check that the infrastructure is ready
        assert "function" in content.lower()


def test_accessibility_button_colors(test_server):
    """Test that button colors meet accessibility standards."""
    response = requests.get(f"{test_server}/docs/")
    assert response.status_code == 200
    content = response.text

    # Check for the improved button colors we implemented
    assert "--bg-button: #1e3a8a" in content  # WCAG AA compliant color
    assert "--bg-button-hover: #1e40af" in content
