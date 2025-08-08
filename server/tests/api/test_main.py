"""Tests for main FastAPI application."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient


# Mock environment variables before importing main
@pytest.fixture(autouse=True)
def mock_env():
    """Mock environment variables for testing."""
    with patch.dict(
        os.environ,
        {
            "APPS_DIR": "/tmp/test_apps",
            "DOCS_DIR": "/tmp/test_docs",
            "TEMPLATES_DIR": "server/templates",
            "STATIC_DIR": "server/static",
            "LOG_LEVEL": "INFO",
            "ENABLE_FILE_WATCHER": "false",  # Disable for testing
        },
    ):
        yield


class TestMainApiEndpoints:
    """Test cases for the main FastAPI application."""

    @pytest.fixture
    def client(self, mock_env):
        """Create a test client for the FastAPI app."""
        # Import after env vars are mocked
        from server.main import app

        return TestClient(app)

    @pytest.fixture
    def mock_startup_components(self):
        """Mock components used during startup."""
        with (
            patch("server.main.run_initial_documentation_generation", return_value=True),
            patch("server.main.start_file_watcher", return_value=None),
            patch("server.main.broadcast_startup_completion"),
            patch("server.main.DirectoryStatus") as mock_dir_status,
            patch(
                "server.main.get_environment_config",
                return_value={
                    "enable_file_watcher": False,
                    "force_regenerate": False,
                    "watch_debounce_delay": 2.0,
                    "watch_max_retries": 3,
                    "watch_force_regenerate": False,
                    "watch_log_level": "INFO",
                },
            ),
        ):
            # Mock directory status
            mock_status = Mock()
            mock_status.apps_exists = True
            mock_status.docs_exists = True
            mock_status.apps_count = 5
            mock_status.docs_count = 10
            mock_status.log_status = Mock()
            mock_dir_status.return_value = mock_status

            yield mock_status

    def test_root_redirect(self, client, mock_startup_components):
        """Test that root endpoint redirects to docs."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/docs/"

    def test_health_endpoint_startup_completed(self, client, mock_startup_components):
        """Test health endpoint when startup is completed."""
        # Set startup as completed
        with patch("server.main.startup_generation_completed", True):
            with patch("server.main.startup_errors", []):
                response = client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert data["startup_generation_completed"] is True
                assert data["startup_errors"] == []

    def test_health_endpoint_startup_errors(self, client, mock_startup_components):
        """Test health endpoint with startup errors."""
        errors = ["Error 1", "Error 2"]
        with patch("server.main.startup_generation_completed", False):
            with patch("server.main.startup_errors", errors):
                response = client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "unhealthy"  # startup_errors + not completed = unhealthy
                assert data["startup_generation_completed"] is False
                assert data["startup_errors"] == errors

    def test_list_files_endpoint(self, client, mock_startup_components):
        """Test list files API endpoint."""
        mock_files = [
            {"name": "test1.md", "title": "Test 1", "size": 100, "modified": 1234567890},
            {"name": "test2.md", "title": "Test 2", "size": 200, "modified": 1234567891},
        ]

        with patch("server.main.docs_service.get_file_list", return_value=mock_files):
            response = client.get("/api/files")
            assert response.status_code == 200
            data = response.json()
            assert data["files"] == mock_files
            assert data["total_count"] == 2
            assert "docs_available" in data
            assert "docs_directory" in data

    def test_list_files_endpoint_error(self, client, mock_startup_components):
        """Test list files API endpoint with service error."""
        with patch("server.main.docs_service.get_file_list", side_effect=Exception("Service error")):
            response = client.get("/api/files")
            assert response.status_code == 500

    def test_get_file_endpoint(self, client, mock_startup_components):
        """Test get file API endpoint."""
        mock_content = "<h1>Test Content</h1>"
        mock_title = "Test File"

        with patch("server.main.docs_service.get_file_content", return_value=(mock_content, mock_title)):
            response = client.get("/api/file/test.md")
            assert response.status_code == 200
            data = response.json()
            assert data["content"] == mock_content
            assert data["title"] == mock_title
            assert data["filename"] == "test.md"
            assert data["type"] == "markdown"

    def test_get_file_endpoint_not_found(self, client, mock_startup_components):
        """Test get file API endpoint with non-existent file."""
        from fastapi import HTTPException

        with patch(
            "server.main.docs_service.get_file_content", side_effect=HTTPException(status_code=404, detail="Not found")
        ):
            response = client.get("/api/file/nonexistent.md")
            assert response.status_code == 404

    def test_docs_index_page(self, client, mock_startup_components):
        """Test docs index page rendering."""
        mock_files = [{"name": "test.md", "title": "Test", "size": 100, "modified": 1234567890}]

        with patch("server.main.docs_service.get_file_list", return_value=mock_files):
            response = client.get("/docs/")
            assert response.status_code == 200
            # The response should contain HTML from the rendered template
            assert "text/html" in response.headers.get("content-type", "")

    def test_docs_file_page(self, client, mock_startup_components):
        """Test individual docs file page rendering."""
        mock_content = "<h1>Test Content</h1>"
        mock_title = "Test File"

        with patch("server.main.docs_service.get_file_content", return_value=(mock_content, mock_title)):
            response = client.get("/docs/test.md")
            assert response.status_code == 200
            # The response should contain HTML from the rendered template
            assert "text/html" in response.headers.get("content-type", "")

    def test_search_endpoint(self, client, mock_startup_components):
        """Test search API endpoint."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test markdown files
            docs_dir = Path(temp_dir)
            (docs_dir / "test1.md").write_text("# Test 1\nThis is a test file with some content.")
            (docs_dir / "test2.md").write_text("# Test 2\nAnother test file with different content.")

            with patch("server.main.DOCS_DIR", docs_dir):
                response = client.get("/api/search?q=test")
                assert response.status_code == 200
                data = response.json()
                assert "results" in data
                assert "query" in data
                assert "total_results" in data
                assert "message" in data

    def test_search_endpoint_empty_query(self, client, mock_startup_components):
        """Test search endpoint with empty query."""
        response = client.get("/api/search?q=")
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []
        assert data["query"] == ""
        assert data["total_results"] == 0
        assert "message" in data

    def test_pygments_css_endpoint(self, client, mock_startup_components):
        """Test Pygments CSS generation endpoint."""
        response = client.get("/api/css/pygments.css")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/css; charset=utf-8"
        # Check that CSS contains expected highlighting styles
        assert ".highlight" in response.text

    def test_websocket_status_endpoint(self, client, mock_startup_components):
        """Test WebSocket status endpoint."""
        mock_connection_info = {
            "active_connections": 5,
            "total_connections": 10,
            "events_sent": 100,
            "broadcast_errors": 0,
        }

        with patch("server.main.websocket_manager.get_connection_info", return_value=mock_connection_info):
            response = client.get("/api/ws/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "active"
            assert data["websocket_enabled"] is True
            assert data["connection_info"] == mock_connection_info

    def test_watcher_status_endpoint_active(self, client, mock_startup_components):
        """Test watcher status endpoint with active watcher."""
        mock_watcher = Mock()
        mock_watcher.get_status.return_value = {
            "is_watching": True,
            "watch_directory": "/tmp/test_apps",
            "events_processed": 50,
        }

        with patch("server.main.file_watcher", mock_watcher):
            response = client.get("/api/watcher/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "active"
            assert data["watcher_info"]["is_watching"] is True

    def test_watcher_status_endpoint_inactive(self, client, mock_startup_components):
        """Test watcher status endpoint with no watcher."""
        with patch("server.main.file_watcher", None):
            response = client.get("/api/watcher/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "disabled"
            assert data["message"] == "File watcher not initialized"
            assert data["is_watching"] is False

    def test_generate_all_endpoint_success(self, client, mock_startup_components):
        """Test generate all documentation endpoint."""
        mock_results = {
            "total_files": 5,
            "successful": 5,
            "failed": 0,
            "skipped": 0,
            "generated_files": ["file1.py", "file2.py"],
            "failed_files": [],
            "skipped_files": [],
        }

        # Mock file_watcher to be None so it uses BatchDocGenerator
        with (
            patch("server.main.file_watcher", None),
            patch("server.main.BatchDocGenerator") as mock_generator_class,
            patch("server.main.APPS_DIR") as mock_apps_dir,
            patch("server.main.DOCS_DIR") as mock_docs_dir,
        ):
            # Mock APPS_DIR to exist
            mock_apps_dir.exists.return_value = True

            # Mock DOCS_DIR operations
            mock_index_path = Mock()
            mock_docs_dir.__truediv__.return_value = mock_index_path

            mock_generator = Mock()
            mock_generator.generate_all_docs.return_value = mock_results
            mock_generator.generate_index_file.return_value = "# Index"
            mock_generator_class.return_value = mock_generator

            response = client.post("/api/generate/all")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Documentation generation completed"
            assert data["results"] == mock_results

    def test_generate_all_endpoint_with_force(self, client, mock_startup_components):
        """Test generate all documentation endpoint with force flag."""
        mock_results = {
            "total_files": 5,
            "successful": 5,
            "failed": 0,
            "skipped": 0,
            "generated_files": ["file1.py", "file2.py"],
            "failed_files": [],
            "skipped_files": [],
        }

        # Mock file_watcher to be None so it uses BatchDocGenerator
        with (
            patch("server.main.file_watcher", None),
            patch("server.main.BatchDocGenerator") as mock_generator_class,
            patch("server.main.APPS_DIR") as mock_apps_dir,
            patch("server.main.DOCS_DIR") as mock_docs_dir,
        ):
            # Mock APPS_DIR to exist
            mock_apps_dir.exists.return_value = True

            # Mock DOCS_DIR operations
            mock_index_path = Mock()
            mock_docs_dir.__truediv__.return_value = mock_index_path

            mock_generator = Mock()
            mock_generator.generate_all_docs.return_value = mock_results
            mock_generator.generate_index_file.return_value = "# Index"
            mock_generator_class.return_value = mock_generator

            response = client.post("/api/generate/all?force=true")
            assert response.status_code == 200
            # Verify force parameter was passed to generate_all_docs
            mock_generator.generate_all_docs.assert_called_with(force_regenerate=True)

    def test_generate_file_endpoint_success(self, client, mock_startup_components):
        """Test generate single file endpoint."""
        mock_generator = Mock()
        # generate_single_file_docs returns (docs_content, success_flag)
        mock_generator.generate_single_file_docs.return_value = ("# Generated docs", True)

        # Mock APPS_DIR to make the file path exist
        with patch("server.main.APPS_DIR") as mock_apps_dir:
            mock_file = Mock()
            mock_file.exists.return_value = True
            mock_file.stem = "test"
            mock_apps_dir.__truediv__.return_value = mock_file
            mock_apps_dir.exists.return_value = True

            with patch("server.main.BatchDocGenerator", return_value=mock_generator):
                with patch("server.main.DOCS_DIR") as mock_docs_dir:
                    mock_output_file = Mock()
                    mock_output_file.exists.return_value = False  # File doesn't exist so it will generate
                    mock_docs_dir.__truediv__.return_value = mock_output_file

                    response = client.post("/api/generate/file/test.py")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
                    assert (
                        "Generated docs" in data["message"] or "Documentation generated successfully" in data["message"]
                    )
                    data = response.json()
                    assert data["success"] is True
                    assert "Documentation generated successfully" in data["message"]
                    assert data["skipped"] is False

    def test_generate_file_endpoint_not_found(self, client, mock_startup_components):
        """Test generate single file endpoint with non-existent file."""
        mock_generator = Mock()
        mock_generator.generate_single_file.side_effect = FileNotFoundError("File not found")

        with patch("server.main.BatchDocGenerator", return_value=mock_generator):
            response = client.post("/api/generate/file/nonexistent.py")
            assert response.status_code == 404

    def test_broadcast_test_endpoint(self, client, mock_startup_components):
        """Test WebSocket broadcast test endpoint."""
        with patch("server.main.websocket_manager.broadcast") as mock_broadcast:
            mock_broadcast.return_value = 2  # clients_notified
            with patch("server.main.websocket_manager.get_connection_count") as mock_count:
                mock_count.return_value = 3  # total_connections
                response = client.post("/api/ws/broadcast")
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["message"] == "Test message"
                assert data["clients_notified"] == 2
                assert data["total_connections"] == 3

    def test_broadcast_test_endpoint_custom_message(self, client, mock_startup_components):
        """Test WebSocket broadcast test endpoint with custom message."""
        custom_message = "Custom test message"

        with patch("server.main.websocket_manager.broadcast") as mock_broadcast:
            mock_broadcast.return_value = 1  # clients_notified
            with patch("server.main.websocket_manager.get_connection_count") as mock_count:
                mock_count.return_value = 2  # total_connections
                response = client.post(f"/api/ws/broadcast?message={custom_message}")
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["message"] == custom_message
                assert data["clients_notified"] == 1
                assert data["total_connections"] == 2


class TestStartupLifecycle:
    """Test startup and utility functions."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            apps_dir = temp_path / "apps"
            docs_dir = temp_path / "docs"
            apps_dir.mkdir()
            docs_dir.mkdir()

            # Create test files
            (apps_dir / "test_automation.py").write_text("# Test automation")

            yield apps_dir, docs_dir

    @pytest.mark.asyncio
    async def test_run_initial_documentation_generation_success(self, temp_dirs):
        """Test successful initial documentation generation."""
        from server.main import run_initial_documentation_generation
        from server.utils.utils import DirectoryStatus

        apps_dir, docs_dir = temp_dirs
        dir_status = DirectoryStatus(apps_dir, docs_dir)
        config = {"force_regenerate": False}

        with (
            patch("server.main.BatchDocGenerator") as mock_generator_class,
            patch("server.main.APPS_DIR", apps_dir),
            patch("server.main.DOCS_DIR", docs_dir),
        ):
            mock_generator = Mock()
            mock_generator.generate_all_docs.return_value = {
                "total_files": 1,
                "successful": 1,
                "failed": 0,
                "skipped": 0,
                "generated_files": ["test.py"],
                "failed_files": [],
                "skipped_files": [],
            }
            mock_generator.generate_index_file.return_value = "# Test Index"
            mock_generator_class.return_value = mock_generator

            with (
                patch("server.main.websocket_manager.broadcast_batch_status"),
                patch("server.main.pending_tasks", set()),
            ):
                result = await run_initial_documentation_generation(dir_status, config)
                assert result is True

    @pytest.mark.asyncio
    async def test_run_initial_documentation_generation_no_apps(self):
        """Test initial documentation generation when apps directory doesn't exist."""
        from server.main import run_initial_documentation_generation
        from server.utils.utils import DirectoryStatus

        apps_dir = Path("/nonexistent")
        docs_dir = Path("/tmp/docs")
        dir_status = DirectoryStatus(apps_dir, docs_dir)
        config = {"force_regenerate": False}

        result = await run_initial_documentation_generation(dir_status, config)
        assert result is False

    @pytest.mark.asyncio
    async def test_run_initial_documentation_generation_error(self, temp_dirs):
        """Test initial documentation generation with error."""
        from server.main import run_initial_documentation_generation
        from server.utils.utils import DirectoryStatus

        apps_dir, docs_dir = temp_dirs
        dir_status = DirectoryStatus(apps_dir, docs_dir)
        config = {"force_regenerate": False}

        with patch("server.main.BatchDocGenerator") as mock_generator_class:
            mock_generator_class.side_effect = Exception("Generation failed")

            with patch("server.main.websocket_manager.broadcast_batch_status"):
                result = await run_initial_documentation_generation(dir_status, config)
                assert result is False

    @pytest.mark.asyncio
    async def test_start_file_watcher_success(self, temp_dirs):
        """Test successful file watcher start."""
        from server.main import start_file_watcher
        from server.utils.utils import DirectoryStatus

        apps_dir, docs_dir = temp_dirs
        dir_status = DirectoryStatus(apps_dir, docs_dir)
        config = {
            "enable_file_watcher": True,
            "watch_debounce_delay": 2.0,
            "watch_max_retries": 3,
            "watch_force_regenerate": False,
            "watch_log_level": "INFO",
        }

        with patch("server.main.FileWatcher") as mock_watcher_class:
            mock_watcher = Mock()
            mock_watcher.start_watching = AsyncMock()
            mock_watcher_class.return_value = mock_watcher

            with patch("server.main.websocket_manager.broadcast_batch_status"):
                result = await start_file_watcher(dir_status, config)
                assert result == mock_watcher

    @pytest.mark.asyncio
    async def test_start_file_watcher_disabled(self, temp_dirs):
        """Test file watcher when disabled by configuration."""
        from server.main import start_file_watcher
        from server.utils.utils import DirectoryStatus

        apps_dir, docs_dir = temp_dirs
        dir_status = DirectoryStatus(apps_dir, docs_dir)
        config = {"enable_file_watcher": False}

        result = await start_file_watcher(dir_status, config)
        assert result is None

    @pytest.mark.asyncio
    async def test_start_file_watcher_no_apps_dir(self):
        """Test file watcher when apps directory doesn't exist."""
        from server.main import start_file_watcher
        from server.utils.utils import DirectoryStatus

        apps_dir = Path("/nonexistent")
        docs_dir = Path("/tmp/docs")
        dir_status = DirectoryStatus(apps_dir, docs_dir)
        config = {"enable_file_watcher": True}

        result = await start_file_watcher(dir_status, config)
        assert result is None

    @pytest.mark.asyncio
    async def test_broadcast_startup_completion(self):
        """Test startup completion broadcast."""
        from server.main import broadcast_startup_completion

        dir_status = Mock()
        dir_status.docs_count = 10
        watcher = Mock()
        watcher.is_watching = True

        with patch("server.main.websocket_manager.broadcast_batch_status") as mock_broadcast:
            await broadcast_startup_completion(dir_status, watcher, True)
            mock_broadcast.assert_called_once()

            # Check the call arguments
            args = mock_broadcast.call_args[0]
            assert "ready" in args[1]  # Message should contain "ready"

    def test_app_configuration(self):
        """Test FastAPI app configuration."""
        from server.main import app, APP_TITLE, APP_DESCRIPTION, APP_VERSION

        assert app.title == APP_TITLE
        assert app.description == APP_DESCRIPTION
        assert app.version == APP_VERSION
        assert app.docs_url == "/api/docs"
        assert app.redoc_url == "/api/redoc"

    def test_global_variables_initialization(self, mock_env):
        """Test that global variables are properly initialized."""
        # Re-import to test initialization with mocked env
        import importlib
        import server.main

        importlib.reload(server.main)

        assert server.main.APPS_DIR == Path("/tmp/test_apps").resolve()
        assert server.main.DOCS_DIR == Path("/tmp/test_docs").resolve()
        assert server.main.markdown_processor is not None
        assert server.main.docs_service is not None

    # Removed: test that required reloading module to simulate missing APPS_DIR
