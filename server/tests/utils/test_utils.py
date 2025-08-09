"""Tests for utility functions."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from server.utils.utils import (
    DirectoryStatus,
    count_automation_files,
    count_documentation_files,
    get_environment_config,
    get_server_config,
    parse_boolean_env,
    print_startup_info,
)


class TestParseBooleanEnv:
    """Test cases for parse_boolean_env function."""

    def test_parse_boolean_env_true_values(self):
        """Test that various true values are parsed correctly."""
        true_values = ["true", "TRUE", "True", "1", "yes", "YES", "on", "ON"]

        for value in true_values:
            with patch.dict(os.environ, {"TEST_VAR": value}):
                assert parse_boolean_env("TEST_VAR") is True

    def test_parse_boolean_env_false_values(self):
        """Test that various false values are parsed correctly."""
        false_values = ["false", "FALSE", "False", "0", "no", "NO", "off", "OFF", ""]

        for value in false_values:
            with patch.dict(os.environ, {"TEST_VAR": value}):
                assert parse_boolean_env("TEST_VAR") is False

    def test_parse_boolean_env_default_false(self):
        """Test that missing env var returns default false."""
        with patch.dict(os.environ, {}, clear=True):
            assert parse_boolean_env("MISSING_VAR") is False

    def test_parse_boolean_env_custom_default(self):
        """Test custom default value."""
        with patch.dict(os.environ, {}, clear=True):
            assert parse_boolean_env("MISSING_VAR", "true") is True
            assert parse_boolean_env("MISSING_VAR", "false") is False

    def test_parse_boolean_env_invalid_values(self):
        """Test that invalid values are treated as false."""
        invalid_values = ["maybe", "unknown", "2", "invalid"]

        for value in invalid_values:
            with patch.dict(os.environ, {"TEST_VAR": value}):
                assert parse_boolean_env("TEST_VAR") is False


class TestCountAutomationFiles:
    """Test cases for count_automation_files function."""

    def test_count_automation_files_nonexistent_dir(self):
        """Test counting files in non-existent directory."""
        non_existent = Path("/nonexistent/directory")
        assert count_automation_files(non_existent) == 0

    def test_count_automation_files_empty_dir(self):
        """Test counting files in empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            apps_dir = Path(temp_dir)
            assert count_automation_files(apps_dir) == 0

    def test_count_automation_files_with_automation_files(self):
        """Test counting automation files excludes infrastructure files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            apps_dir = Path(temp_dir)

            # Create automation files
            (apps_dir / "automation1.py").touch()
            (apps_dir / "automation2.py").touch()
            (apps_dir / "my_module.py").touch()

            # Create infrastructure files (should be excluded)
            (apps_dir / "const.py").touch()
            (apps_dir / "infra.py").touch()
            (apps_dir / "utils.py").touch()
            (apps_dir / "__init__.py").touch()
            (apps_dir / "apps.py").touch()
            (apps_dir / "configuration.py").touch()
            (apps_dir / "secrets.py").touch()

            # Create non-Python files (should be excluded)
            (apps_dir / "readme.txt").touch()
            (apps_dir / "config.yaml").touch()

            assert count_automation_files(apps_dir) == 3

    def test_count_automation_files_only_infrastructure(self):
        """Test that only infrastructure files returns 0."""
        with tempfile.TemporaryDirectory() as temp_dir:
            apps_dir = Path(temp_dir)

            # Create only infrastructure files
            (apps_dir / "const.py").touch()
            (apps_dir / "infra.py").touch()
            (apps_dir / "utils.py").touch()

            assert count_automation_files(apps_dir) == 0


class TestCountDocumentationFiles:
    """Test cases for count_documentation_files function."""

    def test_count_documentation_files_nonexistent_dir(self):
        """Test counting files in non-existent directory."""
        non_existent = Path("/nonexistent/directory")
        assert count_documentation_files(non_existent) == 0

    def test_count_documentation_files_empty_dir(self):
        """Test counting files in empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)
            assert count_documentation_files(docs_dir) == 0

    def test_count_documentation_files_with_markdown(self):
        """Test counting markdown files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)

            # Create markdown files
            (docs_dir / "doc1.md").touch()
            (docs_dir / "doc2.md").touch()
            (docs_dir / "README.md").touch()

            # Create non-markdown files (should be excluded)
            (docs_dir / "not_doc.txt").touch()
            (docs_dir / "config.yaml").touch()
            (docs_dir / "script.py").touch()

            assert count_documentation_files(docs_dir) == 3

    def test_count_documentation_files_no_markdown(self):
        """Test counting when no markdown files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)

            # Create non-markdown files
            (docs_dir / "file.txt").touch()
            (docs_dir / "config.yaml").touch()

            assert count_documentation_files(docs_dir) == 0


class TestGetEnvironmentConfig:
    """Test cases for get_environment_config function."""

    def test_get_environment_config_defaults(self):
        """Test environment config with default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = get_environment_config()

            expected = {
                "force_regenerate": False,
                "enable_file_watcher": True,
                "watch_debounce_delay": 2.0,
                "watch_max_retries": 3,
                "watch_force_regenerate": False,
                "watch_log_level": "INFO",
                "markdown_cache_size": 128,
            }

            assert config == expected

    def test_get_environment_config_custom_values(self):
        """Test environment config with custom values."""
        env_vars = {
            "FORCE_REGENERATE": "true",
            "ENABLE_FILE_WATCHER": "false",
            "WATCH_DEBOUNCE_DELAY": "5.5",
            "WATCH_MAX_RETRIES": "10",
            "WATCH_FORCE_REGENERATE": "yes",
            "WATCH_LOG_LEVEL": "DEBUG",
            "MARKDOWN_CACHE_SIZE": "256",
        }

        with patch.dict(os.environ, env_vars):
            config = get_environment_config()

            expected = {
                "force_regenerate": True,
                "enable_file_watcher": False,
                "watch_debounce_delay": 5.5,
                "watch_max_retries": 10,
                "watch_force_regenerate": True,
                "watch_log_level": "DEBUG",
                "markdown_cache_size": 256,
            }

            assert config == expected

    def test_get_environment_config_partial_override(self):
        """Test environment config with partial override."""
        env_vars = {
            "FORCE_REGENERATE": "true",
            "WATCH_DEBOUNCE_DELAY": "1.0",
        }

        with patch.dict(os.environ, env_vars):
            config = get_environment_config()

            assert config["force_regenerate"] is True
            assert config["watch_debounce_delay"] == 1.0
            # Other values should be defaults
            assert config["enable_file_watcher"] is True
            assert config["watch_max_retries"] == 3
            assert config["markdown_cache_size"] == 128


class TestGetServerConfig:
    """Test cases for get_server_config function."""

    def test_get_server_config_defaults(self):
        """Test server config with default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = get_server_config()

            expected = {
                "host": "127.0.0.1",
                "port": 8080,
                "reload": True,
                "log_level": "info",
            }

            assert config == expected

    def test_get_server_config_custom_values(self):
        """Test server config with custom values."""
        env_vars = {
            "HOST": "0.0.0.0",
            "PORT": "9000",
            "RELOAD": "false",
            "LOG_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, env_vars):
            config = get_server_config()

            expected = {
                "host": "0.0.0.0",
                "port": 9000,
                "reload": False,
                "log_level": "debug",
            }

            assert config == expected

    def test_get_server_config_invalid_port(self):
        """Test server config with invalid port value."""
        with patch.dict(os.environ, {"PORT": "invalid"}):
            with pytest.raises(ValueError):
                get_server_config()


class TestDirectoryStatus:
    """Test cases for DirectoryStatus class."""

    def test_directory_status_both_exist(self):
        """Test DirectoryStatus when both directories exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            apps_dir = temp_path / "apps"
            docs_dir = temp_path / "docs"

            # Create directories and files
            apps_dir.mkdir()
            docs_dir.mkdir()
            (apps_dir / "automation.py").touch()
            (docs_dir / "doc.md").touch()

            status = DirectoryStatus(apps_dir, docs_dir)

            assert status.apps_dir == apps_dir
            assert status.docs_dir == docs_dir
            assert status.apps_exists is True
            assert status.docs_exists is True
            assert status.apps_count == 1
            assert status.docs_count == 1

    def test_directory_status_neither_exist(self):
        """Test DirectoryStatus when neither directory exists."""
        apps_dir = Path("/nonexistent/apps")
        docs_dir = Path("/nonexistent/docs")

        status = DirectoryStatus(apps_dir, docs_dir)

        assert status.apps_dir == apps_dir
        assert status.docs_dir == docs_dir
        assert status.apps_exists is False
        assert status.docs_exists is False
        assert status.apps_count == 0
        assert status.docs_count == 0

    def test_directory_status_log_status(self):
        """Test DirectoryStatus.log_status method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            apps_dir = temp_path / "apps"
            docs_dir = temp_path / "nonexistent"

            apps_dir.mkdir()
            (apps_dir / "automation.py").touch()

            status = DirectoryStatus(apps_dir, docs_dir)
            mock_logger = Mock()

            status.log_status(mock_logger)

            # Should log info for existing apps dir
            mock_logger.info.assert_any_call("Found 1 automation files to process")
            # Should log warning for missing docs dir
            mock_logger.warning.assert_called_once()

    def test_directory_status_log_status_missing_apps(self):
        """Test DirectoryStatus.log_status when apps directory is missing."""
        apps_dir = Path("/nonexistent/apps")
        docs_dir = Path("/nonexistent/docs")

        status = DirectoryStatus(apps_dir, docs_dir)
        mock_logger = Mock()

        status.log_status(mock_logger)

        # Should log error for missing apps dir
        mock_logger.error.assert_called_once()


class TestPrintStartupInfo:
    """Test cases for print_startup_info function."""

    def test_print_startup_info_happy_path(self, capsys):
        """Test basic startup info printing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            apps_dir = temp_path / "apps"
            docs_dir = temp_path / "docs"
            apps_dir.mkdir()
            docs_dir.mkdir()

            dir_status = DirectoryStatus(apps_dir, docs_dir)
            server_config = {
                "host": "127.0.0.1",
                "port": 8080,
                "reload": True,
                "log_level": "info",
            }
            env_config = {
                "force_regenerate": False,
                "enable_file_watcher": True,
                "watch_debounce_delay": 2.0,
                "watch_max_retries": 3,
                "watch_force_regenerate": False,
                "watch_log_level": "INFO",
                "markdown_cache_size": 128,
            }

            print_startup_info(dir_status, server_config, env_config)

            captured = capsys.readouterr()
            assert "AppDaemon Documentation Server" in captured.out
            assert "127.0.0.1:8080" in captured.out
            assert "HOST=127.0.0.1" in captured.out
            assert "PORT=8080" in captured.out

    def test_print_startup_info_missing_apps_dir(self, capsys):
        """Test startup info when apps directory is missing."""
        apps_dir = Path("/nonexistent/apps")
        docs_dir = Path("/nonexistent/docs")

        dir_status = DirectoryStatus(apps_dir, docs_dir)
        server_config = {"host": "127.0.0.1", "port": 8080, "reload": True, "log_level": "info"}
        env_config = {
            "force_regenerate": False,
            "enable_file_watcher": True,
            "watch_debounce_delay": 2.0,
            "watch_max_retries": 3,
            "watch_force_regenerate": False,
            "watch_log_level": "INFO",
            "markdown_cache_size": 128,
        }

        print_startup_info(dir_status, server_config, env_config)

        captured = capsys.readouterr()
        assert "⚠️  Warning: Apps directory not found" in captured.out
        assert "Auto-generation will be skipped" in captured.out

    def test_print_startup_info_import_fallback(self, capsys):
        """Test startup info with import fallback values."""
        # Mock the import to fail, forcing fallback values
        with patch.dict("sys.modules", {"server.main": None}):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                apps_dir = temp_path / "apps"
                docs_dir = temp_path / "docs"
                apps_dir.mkdir()
                docs_dir.mkdir()

                dir_status = DirectoryStatus(apps_dir, docs_dir)
                server_config = {"host": "127.0.0.1", "port": 8080, "reload": True, "log_level": "info"}
                env_config = {
                    "force_regenerate": False,
                    "enable_file_watcher": True,
                    "watch_debounce_delay": 2.0,
                    "watch_max_retries": 3,
                    "watch_force_regenerate": False,
                    "watch_log_level": "INFO",
                    "markdown_cache_size": 128,
                }

                print_startup_info(dir_status, server_config, env_config)

                captured = capsys.readouterr()
                # Should use fallback values
                assert "AppDaemon Documentation Server" in captured.out
                assert "v1.0.0" in captured.out
