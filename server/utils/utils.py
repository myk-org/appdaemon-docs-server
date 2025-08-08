"""Utility functions for the documentation server."""

import logging
import os
import sys
import yaml  # type: ignore[import-untyped]
from pathlib import Path
from typing import Any


def parse_boolean_env(env_var: str, default: str = "false") -> bool:
    """
    Parse a boolean environment variable with consistent behavior.

    Args:
        env_var: Environment variable name
        default: Default value if env var is not set

    Returns:
        Boolean value
    """
    value = os.getenv(env_var, default).lower()
    return value in ("true", "1", "yes", "on")


def count_automation_files(apps_dir: Path) -> int:
    """
    Count automation Python files in the apps directory.

    Excludes infrastructure and configuration files.

    Args:
        apps_dir: Path to the apps directory

    Returns:
        Number of automation files found
    """
    if not apps_dir.exists():
        return 0

    excluded_files = {"const.py", "infra.py", "utils.py", "__init__.py", "apps.py", "configuration.py", "secrets.py"}

    return len([f for f in apps_dir.glob("*.py") if f.name not in excluded_files])


def count_documentation_files(docs_dir: Path) -> int:
    """
    Count markdown documentation files in the docs directory.

    Args:
        docs_dir: Path to the documentation directory

    Returns:
        Number of documentation files found
    """
    if not docs_dir.exists():
        return 0

    return len(list(docs_dir.glob("*.md")))


def count_active_apps(
    apps_dir: Path, docs_dir: Path | None = None, doc_stems: list[str] | None = None
) -> dict[str, int | list[str]]:
    """
    Count active apps based on apps.yaml configuration.

    Args:
        apps_dir: Path to the apps directory containing apps.yaml
        docs_dir: Path to the documentation directory (optional if doc_stems provided)
        doc_stems: Precomputed list of documentation file stems (optional)

    Returns:
        Dictionary with counts and module lists for filtering
    """
    apps_yaml_path = apps_dir / "apps.yaml"

    # Get documentation file stems - either from parameter or by scanning
    if doc_stems is not None:
        doc_files = doc_stems
    elif docs_dir is not None:
        doc_files = [f.stem for f in docs_dir.glob("*.md")] if docs_dir.exists() else []
    else:
        raise ValueError("Either docs_dir or doc_stems must be provided")

    total = len(doc_files)

    if not apps_yaml_path.exists():
        # Fallback if no apps.yaml
        return {
            "active": 0,
            "total": total,
            "inactive": total,
            "active_modules": [],
            "inactive_modules": doc_files,
            "all_modules": doc_files,
        }

    try:
        with open(apps_yaml_path, "r", encoding="utf-8") as f:
            apps_config = yaml.safe_load(f)

        # Validate that YAML loaded content is a dictionary
        if not isinstance(apps_config, dict):
            error_msg = (
                f"Invalid apps.yaml format: expected dictionary, got {type(apps_config).__name__}. "
                f"Content: {apps_config}"
            )
            logging.error(error_msg)
            raise ValueError(error_msg)

        # Get unique modules configured in apps.yaml
        active_modules = set()
        for app, config in apps_config.items():
            if isinstance(config, dict) and config.get("module"):
                active_modules.add(config["module"])

        # Use set operations for efficient filtering
        doc_stems_set = set(doc_files)
        active_in_docs = active_modules & doc_stems_set
        inactive_in_docs = doc_stems_set - active_modules

        # Convert to sorted lists
        active_modules_list = sorted(list(active_in_docs))
        inactive_modules_list = sorted(list(inactive_in_docs))

        return {
            "active": len(active_modules_list),
            "total": total,
            "inactive": len(inactive_modules_list),
            "active_modules": active_modules_list,
            "inactive_modules": inactive_modules_list,
            "all_modules": sorted(doc_files),
        }

    except yaml.YAMLError as e:
        error_msg = f"YAML parsing error in {apps_yaml_path}: {e}"
        logging.error(error_msg)
        return {
            "active": 0,
            "total": total,
            "inactive": total,
            "active_modules": [],
            "inactive_modules": doc_files,
            "all_modules": doc_files,
        }
    except (OSError, IOError) as e:
        error_msg = f"File I/O error reading {apps_yaml_path}: {e}"
        logging.error(error_msg)
        return {
            "active": 0,
            "total": total,
            "inactive": total,
            "active_modules": [],
            "inactive_modules": doc_files,
            "all_modules": doc_files,
        }
    except ValueError:
        # Already logged in validation above
        return {
            "active": 0,
            "total": total,
            "inactive": total,
            "active_modules": [],
            "inactive_modules": doc_files,
            "all_modules": doc_files,
        }


def get_environment_config() -> dict[str, Any]:
    """
    Get all environment configuration values used by the server.

    Returns:
        Dictionary of configuration values
    """
    return {
        "force_regenerate": parse_boolean_env("FORCE_REGENERATE"),
        "enable_file_watcher": parse_boolean_env("ENABLE_FILE_WATCHER", "true"),
        "watch_debounce_delay": float(os.getenv("WATCH_DEBOUNCE_DELAY", "2.0")),
        "watch_max_retries": int(os.getenv("WATCH_MAX_RETRIES", "3")),
        "watch_force_regenerate": parse_boolean_env("WATCH_FORCE_REGENERATE"),
        "watch_log_level": os.getenv("WATCH_LOG_LEVEL", "INFO"),
    }


def get_server_config() -> dict[str, Any]:
    """
    Get server configuration values for uvicorn.

    Returns:
        Dictionary of server configuration values
    """
    return {
        "host": os.getenv("HOST", "127.0.0.1"),
        "port": int(os.getenv("PORT", "8080")),
        "reload": parse_boolean_env("RELOAD", "true"),
        "log_level": os.getenv("LOG_LEVEL", "info").lower(),
    }


def _check_external_apps_dir(apps_dir: Path) -> tuple[bool, bool]:
    """
    Check if APPS_DIR is external to the repository and if it's mounted read-only.

    Args:
        apps_dir: Path to the apps directory

    Returns:
        Tuple of (is_external, is_readonly)
    """
    try:
        # Get current working directory and check if apps_dir is within it
        cwd = Path.cwd()
        try:
            apps_dir.relative_to(cwd)
            is_external = False
        except ValueError:
            # apps_dir is not within current working directory
            is_external = True

        # Check if directory is read-only
        is_readonly = False
        if apps_dir.exists():
            try:
                # Try to create a temporary file to test write permissions
                test_file = apps_dir / ".write_test_temp"
                test_file.touch()
                test_file.unlink()  # Clean up
            except (PermissionError, OSError):
                is_readonly = True

        return is_external, is_readonly
    except Exception:
        # If any error occurs, assume safe defaults
        return False, False


def _get_windows_docker_path_hint() -> str | None:
    """
    Get Windows Docker path hint if running on Windows.

    Returns:
        Path hint string for Windows or None for other platforms
    """
    if sys.platform == "win32":
        return (
            "💡 Windows Docker Tip: Use forward slashes and drive mapping:\n"
            "   Windows path: C:\\path\\to\\apps\n"
            "   Docker path:  /c/path/to/apps or //c/path/to/apps\n"
            "   Example: -v //c/Users/username/apps:/app/appdaemon-apps"
        )
    return None


def print_startup_info(
    dir_status: "DirectoryStatus", server_config: dict[str, Any], env_config: dict[str, Any]
) -> None:
    """
    Print comprehensive startup information including configuration and status.

    Args:
        dir_status: Directory status information
        server_config: Server configuration
        env_config: Environment configuration
    """
    # Import at function level to avoid circular import
    try:
        from server.main import APP_TITLE, APP_VERSION

        app_title = APP_TITLE
        app_version = APP_VERSION
    except ImportError:
        # Fallback values in case of circular import
        app_title = "AppDaemon Documentation Server"
        app_version = "1.0.0"

    print(f"Starting {app_title} v{app_version}...")
    print(f"Apps directory: {dir_status.apps_dir}")
    print(f"Documentation directory: {dir_status.docs_dir}")
    print(f"Server will be available at: http://{server_config['host']}:{server_config['port']}")

    # Check for external APPS_DIR and add safety notes
    is_external, is_readonly = _check_external_apps_dir(dir_status.apps_dir)

    if is_external:
        print()
        print("📍 External Apps Directory Detected:")
        print(f"   Apps directory is outside the repository: {dir_status.apps_dir}")
        if is_readonly:
            print("   🔒 Directory is mounted read-only - file watcher will monitor but cannot modify files")
        else:
            print("   ⚠️  Directory has write access - changes will affect external filesystem")

        print("   💡 Safety Notes:")
        print("      • External paths allow full filesystem access")
        print("      • Consider using read-only mounts for production")
        print("      • Ensure proper backup of external directories")
        print("      • Review file permissions for security")

    # Add Windows Docker path hints if applicable
    windows_hint = _get_windows_docker_path_hint()
    if windows_hint:
        print()
        print(windows_hint)

    print()

    # Configuration section
    print("Configuration:")
    print(f"  HOST={server_config['host']}")
    print(f"  PORT={server_config['port']}")
    print(f"  RELOAD={server_config['reload']}")
    print(f"  LOG_LEVEL={server_config['log_level']}")
    print(f"  FORCE_REGENERATE={env_config['force_regenerate']}")
    print(f"  ENABLE_FILE_WATCHER={env_config['enable_file_watcher']}")
    print(f"  WATCH_DEBOUNCE_DELAY={env_config['watch_debounce_delay']}")
    print()

    # Directory status section
    if not dir_status.apps_exists:
        print(f"⚠️  Warning: Apps directory not found at {dir_status.apps_dir}")
        print("         Auto-generation will be skipped")
    else:
        print(f"📁 Found {dir_status.apps_count} automation files to process")

    if not dir_status.docs_exists:
        print(f"⚠️  Documentation directory will be created at {dir_status.docs_dir}")
    else:
        print(f"📚 Found {dir_status.docs_count} existing documentation files")

    print()

    # Features section
    print("Features enabled:")
    print(f"  🚀 Auto-generation on startup: {'Yes' if dir_status.apps_exists else 'No (apps dir missing)'}")
    print(f"  👀 File watcher: {'Yes' if env_config['enable_file_watcher'] else 'No'}")
    print("  🔄 WebSocket real-time updates: Yes")
    print("  🔍 Full-text search: Yes")
    print()


class DirectoryStatus:
    """Helper class to encapsulate directory status information."""

    def __init__(self, apps_dir: Path, docs_dir: Path) -> None:
        """
        Initialize directory status.

        Args:
            apps_dir: Path to apps directory
            docs_dir: Path to docs directory
        """
        self.apps_dir = apps_dir
        self.docs_dir = docs_dir
        self.apps_exists = apps_dir.exists()
        self.docs_exists = docs_dir.exists()
        self.apps_count = count_automation_files(apps_dir) if self.apps_exists else 0
        self.docs_count = count_documentation_files(docs_dir) if self.docs_exists else 0

    def log_status(self, logger: Any) -> None:
        """
        Log directory status information.

        Args:
            logger: Logger instance
        """
        if not self.apps_exists:
            logger.error(f"Apps directory not found: {self.apps_dir}")
        else:
            logger.info(f"Found {self.apps_count} automation files to process")

        if not self.docs_exists:
            logger.warning(f"Documentation directory will be created at {self.docs_dir}")
        else:
            logger.info(f"📚 Documentation ready: {self.docs_count} files available")
