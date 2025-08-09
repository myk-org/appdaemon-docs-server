"""
Documentation Web Server

FastAPI application to serve AppDaemon automation documentation with
markdown rendering, syntax highlighting, and responsive UI.
"""

import asyncio
import logging
import os
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
import html
import time
import shutil
import resource

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi_mcp import FastApiMCP
from pygments.formatters import HtmlFormatter
from pygments import highlight
from pygments.lexers import PythonLexer
import json
from pydantic import BaseModel
from starlette.middleware.gzip import GZipMiddleware

from server.generators.batch_doc_generator import BatchDocGenerator
from server.processors.markdown import MarkdownProcessor
from server.services.docs import DocumentationService
from server.utils.progress_callbacks import ProgressCallbackManager
from server.utils.utils import (
    DirectoryStatus,
    count_active_apps,
    get_environment_config,
    get_server_config,
    print_startup_info,
)
from server.watchers.file_watcher import FileWatcher, WatchConfig
from server.websocket.websocket_manager import EventType, WebSocketEvent, websocket_manager

# Load environment variables from .env file
load_dotenv()

# Configure logging with environment variable support
log_level = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logger = logging.getLogger(__name__)


def validate_safe_path(user_input: str, base_dir: Path) -> Path | None:
    """Validate that user input results in a safe path within base_dir.

    Prevents path traversal attacks by using strict regex validation.
    Only allows alphanumeric characters and underscores in filenames.

    Args:
        user_input: User-provided filename/path
        base_dir: Base directory that file must be within

    Returns:
        Safe path if valid, None if potentially malicious
    """
    try:
        # Strict validation: only allow alphanumeric characters and underscores
        # This prevents all forms of path traversal including encoded attacks
        if not re.match(r"^[A-Za-z0-9_]+$", user_input):
            logger.warning(f"Invalid path input rejected: {user_input!r}")
            return None

        # Construct and resolve path within base directory
        safe_path = (base_dir / user_input).resolve()
        base_dir_resolved = base_dir.resolve()

        # Ensure the path is within the base directory
        safe_path.relative_to(base_dir_resolved)
        return safe_path
    except (ValueError, OSError) as e:
        logger.warning(f"Path validation error for {user_input!r}: {e}")
        return None


def configure_resource_limits() -> dict[str, Any]:
    """Configure system resource limits to prevent DoS and resource exhaustion.

    Returns:
        Dictionary with current resource limits and status
    """
    limits_info: dict[str, Any] = {}

    try:
        # Set reasonable file descriptor limits
        soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)

        # Try to increase soft limit if it's too low
        target_soft_limit = min(4096, hard_limit)
        if soft_limit < target_soft_limit:
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE, (target_soft_limit, hard_limit))
                logger.info(f"Increased file descriptor limit from {soft_limit} to {target_soft_limit}")
                limits_info["file_descriptors"] = {
                    "before": soft_limit,
                    "after": target_soft_limit,
                    "hard_limit": hard_limit,
                }
            except OSError as e:
                logger.warning(f"Could not increase file descriptor limit: {e}")
                limits_info["file_descriptors"] = {"current": soft_limit, "hard_limit": hard_limit, "error": str(e)}
        else:
            limits_info["file_descriptors"] = {"current": soft_limit, "hard_limit": hard_limit}

        # Set memory limits if available (not available on all systems)
        try:
            memory_soft, memory_hard = resource.getrlimit(resource.RLIMIT_AS)
            limits_info["memory"] = {"soft": memory_soft, "hard": memory_hard}
        except (OSError, AttributeError):
            limits_info["memory"] = "not_available"

    except Exception as e:
        logger.error(f"Error configuring resource limits: {e}")
        limits_info["error"] = str(e)

    return limits_info


def get_resource_usage() -> dict[str, Any]:
    """Get current resource usage statistics.

    Returns:
        Dictionary with resource usage information
    """
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "memory_mb": usage.ru_maxrss / 1024 if hasattr(usage, "ru_maxrss") and usage.ru_maxrss else 0,
            "user_time": usage.ru_utime,
            "system_time": usage.ru_stime,
            "page_faults": usage.ru_majflt + usage.ru_minflt,
            "context_switches": getattr(usage, "ru_nvcsw", 0) + getattr(usage, "ru_nivcsw", 0),
        }
    except Exception as e:
        logger.error(f"Error getting resource usage: {e}")
        return {"error": str(e)}


# Application metadata - configurable via environment variables
APP_VERSION = "1.0.0"
APP_TITLE = os.getenv("APP_TITLE", "AppDaemon Documentation Server")
APP_DESCRIPTION = os.getenv(
    "APP_DESCRIPTION", "Web interface for AppDaemon automation documentation with markdown rendering"
)


# Base paths - resolve at startup for better performance
# REAL_APPS_DIR: real/original apps directory (source of truth)
REAL_APPS_DIR_ENV = os.getenv("APPS_DIR")

if not REAL_APPS_DIR_ENV:
    raise ValueError("APPS_DIR environment variable not set")

REAL_APPS_DIR = Path(REAL_APPS_DIR_ENV).resolve()
DOCS_DIR = Path(os.getenv("DOCS_DIR", "data/generated-docs")).resolve()
# MIRRORED_APPS_DIR: mirrored copy of apps used by the server for read-only/generation
MIRRORED_APPS_DIR = Path(os.getenv("APP_SOURCES_DIR", "data/app-sources")).resolve()

# Backward compatibility aliases for tests and external callers
# Keep these names in sync with new naming
APPS_DIR = REAL_APPS_DIR
APP_SOURCES_DIR = MIRRORED_APPS_DIR
TEMPLATES_DIR = Path(os.getenv("TEMPLATES_DIR", "server/templates")).resolve()
STATIC_DIR = Path(os.getenv("STATIC_DIR", "server/static")).resolve()

# Security: control exposure of absolute filesystem paths via API
# Only allow in development environments to prevent production path leakage
_expose_paths_env = os.getenv("EXPOSE_ABS_PATHS_IN_API", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_is_development_env = os.getenv("APP_ENV", "production").lower() in {
    "development",
    "dev",
    "debug",
}
EXPOSE_ABS_PATHS_IN_API: bool = _expose_paths_env and _is_development_env

# Global components for startup integration
file_watcher: FileWatcher | None = None
startup_generation_completed = False
startup_errors: list[str] = []
# Track asyncio tasks to prevent unawaited coroutine warnings
pending_tasks: set[asyncio.Task[None]] = set()


# Global markdown processor instance
markdown_processor = MarkdownProcessor()

# Documentation service instance
docs_service = DocumentationService(DOCS_DIR, markdown_processor)

# Monotonic start timestamp for accurate uptime calculations
START_TS: float = time.monotonic()


def _format_elapsed(seconds: float) -> str:
    """Return a compact human-readable duration like '1d 2h 3m 4s'."""
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if days or hours:
        parts.append(f"{hours}h")
    if days or hours or minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


async def run_initial_documentation_generation(dir_status: DirectoryStatus, config: dict[str, Any]) -> bool:
    """
    Run initial documentation generation during startup.

    Args:
        dir_status: Directory status information
        config: Environment configuration

    Returns:
        True if generation completed successfully, False otherwise
    """
    global startup_errors

    if not dir_status.apps_exists:
        return False

    logger.info("🚀 Starting initial documentation generation...")

    try:
        # Create batch generator (use mirrored apps directory for generation)
        batch_generator = BatchDocGenerator(MIRRORED_APPS_DIR, DOCS_DIR)

        # Broadcast startup event
        await websocket_manager.broadcast_batch_status(
            EventType.BATCH_STARTED,
            "Starting initial documentation generation on server startup",
            {"phase": "startup", "apps_directory": str(MIRRORED_APPS_DIR)},
        )

        # Progress callback setup
        progress_manager = ProgressCallbackManager(websocket_manager, pending_tasks)

        # Run generation
        results = batch_generator.generate_all_docs(
            force_regenerate=config["force_regenerate"], progress_callback=progress_manager.sync_progress_callback
        )

        # Generate index file
        logger.info("📄 Generating documentation index...")
        index_content = batch_generator.generate_index_file()
        index_path = DOCS_DIR / "README.md"
        index_path.write_text(index_content, encoding="utf-8")

        # Log and broadcast results
        logger.info(
            f"✅ Generation complete: {results['successful']} successful, "
            f"{results['failed']} failed, {results['skipped']} skipped"
        )

        if results["failed"] > 0:
            error_msg = f"Initial generation completed with {results['failed']} failures"
            startup_errors.append(error_msg)
            await websocket_manager.broadcast_batch_status(EventType.BATCH_ERROR, error_msg, results)
            return False
        else:
            await websocket_manager.broadcast_batch_status(
                EventType.BATCH_COMPLETED,
                f"Initial generation completed successfully: {results['successful']} files",
                results,
            )
            return True

    except Exception as e:
        error_msg = f"Initial documentation generation failed: {str(e)}"
        logger.error(error_msg)
        startup_errors.append(error_msg)
        await websocket_manager.broadcast_batch_status(EventType.BATCH_ERROR, error_msg, {"error": str(e)})
        return False


async def start_file_watcher(dir_status: DirectoryStatus, config: dict[str, Any]) -> FileWatcher | None:
    """
    Start the file watcher if conditions are met.

    Args:
        dir_status: Directory status information
        config: Environment configuration

    Returns:
        FileWatcher instance if started successfully, None otherwise
    """
    global startup_errors

    if not dir_status.apps_exists:
        logger.warning("⚠️ File watcher disabled: Apps directory not found")
        return None

    if not config["enable_file_watcher"]:
        logger.info("⚠️ File watcher disabled by configuration")
        return None

    logger.info("👀 Starting file watcher...")

    try:
        # Create watcher configuration
        watch_config = WatchConfig(
            watch_directory=REAL_APPS_DIR,
            generation_directory=MIRRORED_APPS_DIR,
            output_directory=DOCS_DIR,
            debounce_delay=config["watch_debounce_delay"],
            max_retry_attempts=config["watch_max_retries"],
            force_regenerate=config["watch_force_regenerate"],
            log_level=config["watch_log_level"],
        )

        # Initialize and start file watcher
        watcher = FileWatcher(watch_config)
        await watcher.start_watching()

        logger.info(
            f"✅ File watcher started successfully. Watching: {REAL_APPS_DIR} | Generating from: {MIRRORED_APPS_DIR}"
        )

        await websocket_manager.broadcast_batch_status(
            EventType.WATCHER_STATUS,
            "File watcher started successfully",
            {"watch_directory": str(REAL_APPS_DIR), "status": "active"},
        )

        return watcher

    except Exception as e:
        error_msg = f"Failed to start file watcher: {str(e)}"
        logger.error(error_msg)
        startup_errors.append(error_msg)

        await websocket_manager.broadcast_batch_status(
            EventType.WATCHER_STATUS, error_msg, {"error": str(e), "status": "failed"}
        )
        return None


async def broadcast_startup_completion(
    dir_status: DirectoryStatus, watcher: FileWatcher | None, generation_completed: bool
) -> None:
    """
    Broadcast final startup status and log completion.

    Args:
        dir_status: Directory status information
        watcher: File watcher instance (if any)
        generation_completed: Whether generation completed successfully
    """
    global startup_errors

    # Broadcast server ready status
    await websocket_manager.broadcast_batch_status(
        EventType.SERVER_STATUS,
        f"Documentation server ready with {len(startup_errors)} startup errors",
        {
            "generation_completed": generation_completed,
            "file_watcher_active": watcher is not None and watcher.is_watching,
            "startup_errors": startup_errors,
            "docs_count": dir_status.docs_count,
        },
    )

    # Log completion status
    if startup_errors:
        logger.warning(f"⚠️ Server started with {len(startup_errors)} errors:")
        for error in startup_errors:
            logger.warning(f"  - {error}")
    else:
        logger.info("🎉 Documentation server startup completed successfully")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifespan events for startup and shutdown.

    Args:
        app: FastAPI application instance

    Yields:
        None during application lifecycle
    """
    global file_watcher, startup_generation_completed, startup_errors
    cleanup_task = None

    # Startup
    logger.info(f"Starting {APP_TITLE} v{APP_VERSION}")
    logger.info(f"Documentation directory: {DOCS_DIR}")
    logger.info(f"Real apps directory: {REAL_APPS_DIR}")
    logger.info(f"Mirrored apps directory: {MIRRORED_APPS_DIR}")

    # Configure resource limits for security and stability
    logger.info("🔧 Configuring resource limits...")
    resource_limits = configure_resource_limits()
    logger.info(f"Resource limits: {resource_limits}")

    startup_errors.clear()

    try:
        # Initialize directories and check status
        logger.info("📁 Initializing directories...")
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        MIRRORED_APPS_DIR.mkdir(parents=True, exist_ok=True)

        # Get directory status and configuration
        dir_status = DirectoryStatus(REAL_APPS_DIR, DOCS_DIR)
        config = get_environment_config()

        # Log directory status
        if not dir_status.apps_exists:
            error_msg = f"Apps directory not found: {REAL_APPS_DIR}"
            logger.error(error_msg)
            startup_errors.append(error_msg)
        else:
            logger.info(f"Found {dir_status.apps_count} automation files to process")

        # Copy AppDaemon source files for read-only viewing
        try:
            # Create a clean mirror: remove files in APP_SOURCES_DIR that no longer exist in APPS_DIR
            try:
                source_rel_paths = set()
                for s in REAL_APPS_DIR.rglob("*.py"):
                    try:
                        source_rel_paths.add(str(s.relative_to(REAL_APPS_DIR)))
                    except ValueError:
                        source_rel_paths.add(s.name)

                if MIRRORED_APPS_DIR.exists():
                    for existing in MIRRORED_APPS_DIR.rglob("*.py"):
                        rel_existing = str(existing.relative_to(MIRRORED_APPS_DIR))
                        if rel_existing not in source_rel_paths:
                            try:
                                existing.unlink()
                            except Exception as de:
                                logger.debug(f"Skip deleting stale mirror file {existing}: {de}")
            except Exception as cleanup_err:
                logger.debug(f"Mirror cleanup skipped due to error: {cleanup_err}")

            copied = 0
            for src in REAL_APPS_DIR.rglob("*.py"):
                # Preserve relative structure
                try:
                    rel = src.relative_to(REAL_APPS_DIR)
                except ValueError:
                    # If outside APPS_DIR (shouldn't happen), flatten
                    rel = Path(src.name)
                dest = MIRRORED_APPS_DIR / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Always copy latest (overwrite if equal or newer)
                try:
                    if not dest.exists() or src.stat().st_mtime >= dest.stat().st_mtime:
                        shutil.copy2(src, dest)
                        copied += 1
                except Exception as ce:
                    logger.debug(f"Skip copying {src}: {ce}")
            logger.info(f"📄 Prepared {copied} AppDaemon source file(s) for read-only viewing")
        except Exception as copy_err:
            logger.warning(f"Failed to prepare app sources for viewing: {copy_err}")

        # Run initial documentation generation
        startup_generation_completed = await run_initial_documentation_generation(dir_status, config)

        # Start file watcher
        file_watcher = await start_file_watcher(dir_status, config)

        # Final startup status
        dir_status.log_status(logger)
        await broadcast_startup_completion(dir_status, file_watcher, startup_generation_completed)

        # Start background WebSocket cleanup task
        logger.info("🧹 Starting WebSocket cleanup background task...")
        cleanup_task = asyncio.create_task(websocket_manager.periodic_cleanup_loop())

    except Exception as e:
        logger.error(f"Critical startup error: {e}")
        startup_errors.append(f"Critical startup error: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down documentation server")

    try:
        # Stop WebSocket cleanup task
        if cleanup_task and not cleanup_task.done():
            logger.info("Stopping WebSocket cleanup task...")
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

        # Stop file watcher
        if file_watcher:
            logger.info("Stopping file watcher...")
            await file_watcher.stop_watching()
            logger.info("File watcher stopped")

        # Wait for pending tasks to complete or cancel them
        if pending_tasks:
            logger.info(f"Waiting for {len(pending_tasks)} pending tasks to complete...")
            await asyncio.gather(*pending_tasks, return_exceptions=True)
            pending_tasks.clear()

        # Clear markdown processor cache
        try:
            markdown_processor.clear_cache()
        except Exception:
            # Fallback for backward compatibility
            markdown_processor._cache.clear()

        # Broadcast shutdown event
        await websocket_manager.broadcast_batch_status(
            EventType.SERVER_STATUS, "Documentation server shutting down", {"status": "shutdown"}
        )

        logger.info("Documentation server shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Initialize FastAPI app with proper configuration and lifespan
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Add GZip compression for large responses
app.add_middleware(GZipMiddleware, minimum_size=500)


# Basic security headers middleware (CSP allows CDN and inline for current templates)
@app.middleware("http")  # type: ignore[misc]
async def add_security_headers(request: Request, call_next: Any) -> Response:
    response: Response = await call_next(request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self' https:; script-src 'self' 'unsafe-inline' https:; "
        "style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:; connect-src 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


# ----------------------
# Response Models
# ----------------------


class FilesResponse(BaseModel):  # type: ignore[misc]
    # Use loose typing here to allow passthrough of mocked/test data and avoid over-constraining API shape
    files: list[dict[str, Any]]
    total_count: int
    docs_available: bool
    docs_directory: str
    limit: int | None = None
    offset: int | None = None


class HealthResponse(BaseModel):  # type: ignore[misc]
    status: str
    service: str
    version: str
    docs_directory_exists: bool
    apps_directory_exists: bool
    docs_files_count: int
    startup_generation_completed: bool
    file_watcher_active: bool
    startup_errors_count: int
    startup_errors: list[str]
    uptime: str
    uptime_seconds: float


class FileContentResponse(BaseModel):  # type: ignore[misc]
    filename: str
    title: str
    content: str
    type: str


class AppSourceInfo(BaseModel):  # type: ignore[misc]
    module: str
    rel_path: str
    abs_path: str | None = None
    size: int
    modified: float


class AppSourceListResponse(BaseModel):  # type: ignore[misc]
    apps: list[AppSourceInfo]
    total_count: int


class AppSourceContentResponse(BaseModel):  # type: ignore[misc]
    module: str
    rel_path: str
    abs_path: str | None = None
    content: str


# API Routes with proper error handling and response models


@app.get("/", response_class=RedirectResponse)  # type: ignore[misc]
async def root() -> RedirectResponse:
    """Root endpoint - redirect to documentation index."""
    return RedirectResponse(url="/docs/", status_code=307)


@app.get("/health", operation_id="health", response_model=HealthResponse)  # type: ignore[misc]
async def health_check() -> HealthResponse:
    """
    Health check endpoint for monitoring server status.

    Returns:
        Health status information including startup generation status
    """
    global file_watcher, startup_generation_completed, startup_errors

    docs_exists = DOCS_DIR.exists()
    apps_exists = REAL_APPS_DIR.exists()
    docs_count = 0

    if docs_exists:
        try:
            docs_count = len(list(DOCS_DIR.glob("*.md")))
        except Exception as e:
            logger.warning(f"Error counting docs files: {e}")

    # Determine overall health status
    status = "healthy"
    if startup_errors:
        status = "degraded" if startup_generation_completed else "unhealthy"
    elif not startup_generation_completed and apps_exists:
        status = "starting"

    # Compute uptime using monotonic clock
    uptime_seconds = time.monotonic() - START_TS

    return HealthResponse(
        status=status,
        service="appdaemon-docs-server",
        version=APP_VERSION,
        docs_directory_exists=docs_exists,
        apps_directory_exists=apps_exists,
        docs_files_count=docs_count,
        startup_generation_completed=startup_generation_completed,
        file_watcher_active=file_watcher is not None and file_watcher.is_watching,
        startup_errors_count=len(startup_errors),
        startup_errors=startup_errors,
        uptime=_format_elapsed(uptime_seconds),
        uptime_seconds=uptime_seconds,
    )


@app.get("/api/files", operation_id="list_files", response_model=FilesResponse)  # type: ignore[misc]
async def list_documentation_files(
    limit: int | None = Query(None, ge=1, le=1000), offset: int | None = Query(None, ge=0, le=100000)
) -> FilesResponse:
    """
    List all available documentation files with metadata.

    Returns:
        Dictionary containing file list and metadata
    """
    try:
        files = await docs_service.get_file_list()
        total = len(files)
        if offset is not None or limit is not None:
            start = offset or 0
            end = start + (limit or total)
            files = files[start:end]

        # Ensure clients do not receive unexpected fields when optional ones are None
        sanitized_files = [{k: v for k, v in f.items() if v is not None} for f in files]

        return FilesResponse(
            files=sanitized_files,
            total_count=total,
            docs_available=DOCS_DIR.exists(),
            docs_directory=str(DOCS_DIR),
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail="Error listing documentation files") from e


@app.get("/api/file/{filename}", operation_id="get_file", response_model=FileContentResponse)  # type: ignore[misc]
async def get_file_content(filename: str) -> FileContentResponse:
    """
    Get processed content for a specific documentation file.

    Args:
        filename: Name of the markdown file (with or without .md extension)

    Returns:
        Dictionary containing processed HTML content and metadata
    """
    try:
        html_content, title = await docs_service.get_file_content(filename)
        return FileContentResponse(filename=filename, title=title, content=html_content, type="markdown")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file content for {filename}: {e}")
        raise HTTPException(status_code=500, detail="Error processing file content") from e


@app.get("/api/app-source/{module}", operation_id="get_app_source")  # type: ignore[misc]
async def get_app_source(module: str, fmt: str = Query("text"), theme: str = Query("light")) -> Response:
    """
    Return the read-only Python source file for a given module name (stem).

    Args:
        module: The module stem (without .py)

    Returns:
        Plain text response with the source code
    """
    try:
        # Validate path to prevent traversal attacks
        safe_path = validate_safe_path(module, MIRRORED_APPS_DIR)
        if not safe_path:
            raise HTTPException(status_code=400, detail="Invalid module name")

        # Extract safe module name for search
        safe_module = safe_path.stem
        source_path = None
        # Search for matching file in MIRRORED_APPS_DIR
        candidates = list(MIRRORED_APPS_DIR.rglob(f"{safe_module}.py"))
        if candidates:
            # Prefer root-level match; else pick first
            candidates.sort(key=lambda p: len(p.parts))
            source_path = candidates[0]
        if source_path is None or not source_path.exists():
            raise HTTPException(status_code=404, detail=f"Source for '{module}' not found")

        with open(source_path, "r", encoding="utf-8") as f:
            content = f.read()

        if fmt == "html":
            style_name = "default" if theme != "dark" else "monokai"
            container_id = "app-source-viewer"
            formatter = HtmlFormatter(noclasses=False, style=style_name)
            # Scope style to this viewer only
            scoped_css = formatter.get_style_defs(f"#{container_id} .highlight")
            highlighted = highlight(content, PythonLexer(), formatter)
            html = f'<style>{scoped_css}</style><div id="{container_id}">{highlighted}</div>'
            return HTMLResponse(content=html)

        return Response(content=content, media_type="text/plain; charset=utf-8")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading app source for {module}: {e}")
        raise HTTPException(status_code=500, detail="Error reading app source") from e


@app.get("/api/app-sources", operation_id="list_app_sources", response_model=AppSourceListResponse)  # type: ignore[misc]
async def list_app_sources() -> AppSourceListResponse:
    """List mirrored AppDaemon source files available for AI analysis."""
    apps: list[AppSourceInfo] = []
    try:
        if MIRRORED_APPS_DIR.exists():
            for py in MIRRORED_APPS_DIR.rglob("*.py"):
                rel = str(py.relative_to(MIRRORED_APPS_DIR))
                info_kwargs: dict[str, Any] = {
                    "module": py.stem,
                    "rel_path": rel,
                    "size": py.stat().st_size,
                    "modified": py.stat().st_mtime,
                }
                if EXPOSE_ABS_PATHS_IN_API:
                    info_kwargs["abs_path"] = str(py.resolve())
                apps.append(AppSourceInfo(**info_kwargs))
    except Exception as e:
        logger.warning(f"Error listing app sources: {e}")
    return AppSourceListResponse(apps=apps, total_count=len(apps))


@app.get("/api/app-source/raw/{module}", operation_id="get_app_source_raw", response_model=AppSourceContentResponse)  # type: ignore[misc]
async def get_app_source_raw(module: str) -> AppSourceContentResponse:
    """Return raw app source content for AI/MCP consumption."""
    try:
        # Validate path to prevent traversal attacks
        safe_path = validate_safe_path(module, MIRRORED_APPS_DIR)
        if not safe_path:
            raise HTTPException(status_code=400, detail="Invalid module name")

        # Extract safe module name for search
        safe_module = safe_path.stem
        candidates = list(MIRRORED_APPS_DIR.rglob(f"{safe_module}.py"))
        if not candidates:
            raise HTTPException(status_code=404, detail=f"Source for '{module}' not found")
        candidates.sort(key=lambda p: len(p.parts))
        source_path = candidates[0]
        content = source_path.read_text(encoding="utf-8")
        resp_kwargs: dict[str, Any] = {
            "module": safe_module,
            "rel_path": str(source_path.relative_to(MIRRORED_APPS_DIR)),
            "content": content,
        }
        if EXPOSE_ABS_PATHS_IN_API:
            resp_kwargs["abs_path"] = str(source_path.resolve())
        return AppSourceContentResponse(**resp_kwargs)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading app source (raw) for {module}: {e}")
        raise HTTPException(status_code=500, detail="Error reading app source") from e


@app.get("/partials/app-sources", response_class=HTMLResponse)  # type: ignore[misc]
async def partial_app_sources() -> HTMLResponse:
    """Return HTML fragment listing configured app sources (for HTMX)."""
    try:
        active_modules = set()
        try:
            files = await docs_service.get_file_list()
            doc_stems = [str(file.get("stem", Path(str(file["name"])).stem)) for file in files]
            app_counts = count_active_apps(REAL_APPS_DIR, doc_stems=doc_stems)
            active_modules_value = app_counts.get("active_modules", [])
            active_modules = set(active_modules_value if isinstance(active_modules_value, list) else [])
        except Exception:
            active_modules = set()

        apps = []
        if MIRRORED_APPS_DIR.exists():
            for py in MIRRORED_APPS_DIR.rglob("*.py"):
                try:
                    mod = py.stem
                    if active_modules and mod not in active_modules:
                        continue
                    rel = str(py.relative_to(MIRRORED_APPS_DIR))
                    size_kb = f"{py.stat().st_size / 1024:.1f}"
                    apps.append((mod, rel, size_kb))
                except Exception:
                    continue

        apps.sort(key=lambda x: x[1])

        # Simple HTML list fragment
        html_parts = [
            '<div class="p-2">',
            '<div class="text-sm text-gray-500 mb-2">Configured Apps</div>',
            '<ul class="divide-y divide-gray-200">',
        ]
        for mod, rel, size_kb in apps:
            # Escape HTML content to prevent XSS attacks
            escaped_mod = html.escape(mod)
            escaped_rel = html.escape(rel)
            html_parts.append(
                f'<li class="py-2"><button class="text-left w-full hover:underline" onclick="window.openSourceViewer(\'{escaped_mod}\')"><strong>{escaped_mod}.py</strong><div class="text-xs text-gray-500">{escaped_rel} • {size_kb} KB</div></button></li>'
            )
        if not apps:
            html_parts.append('<li class="py-2 text-sm text-gray-500">No configured apps found</li>')
        html_parts.append("</ul></div>")
        return HTMLResponse("".join(html_parts))
    except Exception as e:
        logger.error(f"Error rendering app sources partial: {e}")
        raise HTTPException(status_code=500, detail="Error rendering partial") from e


@app.get("/docs/", response_class=HTMLResponse)  # type: ignore[misc]
async def documentation_index(request: Request) -> HTMLResponse:
    """
    Serve the documentation index page.

    Args:
        request: FastAPI request object

    Returns:
        HTML response with documentation index
    """
    try:
        files = await docs_service.get_file_list()

        # Filter to only apps configured in apps.yaml (read from real apps dir)
        doc_stems = [str(file.get("stem", Path(str(file["name"])).stem)) for file in files]
        app_counts = count_active_apps(REAL_APPS_DIR, doc_stems=doc_stems)
        active_modules_value = app_counts.get("active_modules", [])
        active_modules = set(active_modules_value if isinstance(active_modules_value, list) else [])
        files = [f for f in files if str(f.get("stem")) in active_modules]

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "title": "AppDaemon Documentation",
                "files": files,
                # Only configured apps are shown, so total_files reflects configured apps count
                "total_files": len(files),
                # Provide active modules for client-side filtering on dynamic refresh
                "active_modules": sorted(list(active_modules)),
            },
        )
    except Exception as e:
        logger.error(f"Error rendering documentation index: {e}")
        raise HTTPException(status_code=500, detail="Error loading documentation index") from e


@app.get("/docs/{filename}", response_class=HTMLResponse)  # type: ignore[misc]
async def documentation_file(request: Request, filename: str) -> HTMLResponse:
    """
    Serve a specific documentation file with rendered markdown.

    Args:
        request: FastAPI request object
        filename: Name of the documentation file

    Returns:
        HTML response with rendered documentation
    """
    try:
        html_content, title = await docs_service.get_file_content(filename)

        return templates.TemplateResponse(
            request,
            "document.html",
            {
                "title": title,
                "content": html_content,
                "filename": filename,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rendering documentation file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Error rendering documentation") from e


@app.get("/api/search", operation_id="search_docs")  # type: ignore[misc]
async def search_documentation(q: str = Query("", max_length=500)) -> dict[str, list[dict[str, Any]] | str | int]:
    """
    Search through documentation content for matching files.

    Args:
        q: Search query string

    Returns:
        Dictionary containing search results and metadata
    """
    if not q or len(q.strip()) < 2:
        return {
            "query": q,
            "results": [],
            "total_results": 0,
            "message": "Search query must be at least 2 characters long",
        }

    try:
        query = q.strip().lower()
        results = []

        if not DOCS_DIR.exists():
            return {"query": q, "results": [], "total_results": 0, "message": "Documentation directory not found"}

        for file_path in DOCS_DIR.glob("*.md"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read().lower()

                # Calculate relevance score
                title_match = query in file_path.stem.lower().replace("_", " ").replace("-", " ")
                content_matches = content.count(query)

                if title_match or content_matches > 0:
                    # Extract context around matches
                    context = ""
                    if content_matches > 0:
                        # Find first occurrence and extract surrounding context
                        start_pos = content.find(query)
                        if start_pos != -1:
                            context_start = max(0, start_pos - 100)
                            context_end = min(len(content), start_pos + len(query) + 100)
                            raw = content[context_start:context_end].strip()
                            # Escape HTML to prevent injection in UI, then highlight query
                            escaped = html.escape(raw)
                            # Highlight the search term (case-insensitive match on escaped text is tricky; use original query lower)
                            context = escaped.replace(html.escape(query), f"<mark>{html.escape(query)}</mark>")

                    title = await docs_service.extract_title(file_path)

                    # Calculate relevance score
                    relevance = (10 if title_match else 0) + content_matches

                    results.append({
                        "filename": file_path.name,
                        "stem": file_path.stem,
                        "title": title,
                        "matches": content_matches,
                        "relevance": relevance,
                        "context": context[:200] + "..." if len(context) > 200 else context,
                        "url": f"/docs/{file_path.stem}",
                    })

            except Exception as e:
                logger.warning(f"Error searching file {file_path}: {e}")
                continue

        # Sort by relevance (title matches first, then by number of content matches)
        results.sort(key=lambda x: int(x["relevance"]) if isinstance(x["relevance"], (int, float)) else 0, reverse=True)

        return {
            "query": q,
            "results": results,
            "total_results": len(results),
            "message": f"Found {len(results)} result(s) for '{q}'",
        }

    except Exception as e:
        logger.error(f"Error performing search: {e}")
        raise HTTPException(status_code=500, detail="Error performing search") from e


@app.get("/api/css/pygments.css")  # type: ignore[misc]
async def pygments_css() -> Response:
    """
    Generate Pygments CSS for syntax highlighting.

    Returns:
        CSS response with syntax highlighting styles
    """
    try:
        formatter = HtmlFormatter(style="default", noclasses=False)
        css_content = formatter.get_style_defs(".highlight")

        return Response(content=css_content, media_type="text/css", headers={"Cache-Control": "public, max-age=3600"})
    except Exception as e:
        logger.error(f"Error generating Pygments CSS: {e}")
        raise HTTPException(status_code=500, detail="Error generating CSS") from e


# WebSocket Routes


@app.websocket("/ws")  # type: ignore[misc]
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time documentation updates.

    Handles client connections and provides real-time notifications for:
    - File changes (created, modified, deleted)
    - Documentation generation progress
    - Batch processing status
    - System status updates

    Args:
        websocket: The WebSocket connection
    """
    await websocket_manager.connect(websocket)

    try:
        while True:
            # Listen for client messages
            message = await websocket.receive_text()
            await websocket_manager.handle_client_message(websocket, message)

    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket_manager.disconnect(websocket)


@app.get("/sse", include_in_schema=False)  # type: ignore[misc]
async def sse_endpoint() -> StreamingResponse:
    """
    Server-Sent Events endpoint streaming the same events as WebSocket.
    Useful for simpler clients or proxies.
    """
    broker = websocket_manager.get_sse_broker()
    queue = await broker.subscribe()

    async def event_stream() -> AsyncGenerator[bytes, None]:
        try:
            # Initial hello
            yield b"event: system_status\n"
            yield b'data: {"message": "SSE connected"}\n\n'

            while True:
                event = await queue.get()
                data = json.dumps(event).encode()
                # Optional: include event name
                yield b"event: " + event.get("event_type", "message").encode() + b"\n"
                yield b"data: " + data + b"\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await broker.unsubscribe(queue)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "text/event-stream",
    }
    return StreamingResponse(event_stream(), headers=headers, media_type="text/event-stream")


@app.head("/sse", include_in_schema=False)  # type: ignore[misc]
async def sse_head() -> Response:
    """HEAD for SSE to allow header validation without opening a stream."""
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "text/event-stream",
    }
    return Response(status_code=200, headers=headers, media_type="text/event-stream")


@app.get("/api/ws/status", operation_id="ws_status")  # type: ignore[misc]
async def websocket_status() -> dict[str, Any]:
    """
    Get WebSocket connection status and statistics.

    Returns:
        Dictionary containing connection information and statistics
    """
    try:
        connection_info = websocket_manager.get_connection_info()
        return {
            "status": "active",
            "websocket_enabled": True,
            "connection_info": connection_info,
        }
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {e}")
        raise HTTPException(status_code=500, detail="Error getting WebSocket status") from e


@app.get("/api/watcher/status", operation_id="watcher_status")  # type: ignore[misc]
async def watcher_status() -> dict[str, Any]:
    """
    Get file watcher status and statistics.

    Returns:
        Dictionary containing watcher information and statistics
    """
    global file_watcher

    try:
        if file_watcher is None:
            return {
                "status": "disabled",
                "message": "File watcher not initialized",
                "is_watching": False,
            }

        status = file_watcher.get_status()
        return {
            "status": "active" if status["is_watching"] else "stopped",
            "watcher_info": status,
        }

    except Exception as e:
        logger.error(f"Error getting watcher status: {e}")
        raise HTTPException(status_code=500, detail="Error getting watcher status") from e


@app.post("/api/generate/all", operation_id="generate_all")  # type: ignore[misc]
async def trigger_full_generation(force: bool = False) -> dict[str, Any]:
    """
    Manually trigger full documentation generation.

    Args:
        force: Force regeneration even if docs already exist

    Returns:
        Dictionary with generation results
    """
    global file_watcher

    try:
        # Backward-compat: validate against APPS_DIR so tests can patch it
        if not APPS_DIR.exists():
            raise HTTPException(status_code=404, detail=f"Apps directory not found: {APPS_DIR}")

        logger.info(f"Manual full generation triggered (force={force})")

        if file_watcher:
            # Use file watcher's generation method for consistency
            results = await file_watcher.generate_all_docs(force=force)
        else:
            # Fallback to direct batch generation (use APPS_DIR for compatibility)
            batch_generator = BatchDocGenerator(APPS_DIR, DOCS_DIR)

            await websocket_manager.broadcast_batch_status(
                EventType.BATCH_STARTED,
                "Manual full generation started",
                {"force_regenerate": force, "trigger": "manual"},
            )

            results = batch_generator.generate_all_docs(force_regenerate=force)

            # Generate index file
            index_content = batch_generator.generate_index_file()
            index_path = DOCS_DIR / "README.md"
            index_path.write_text(index_content, encoding="utf-8")

            if results["failed"] > 0:
                await websocket_manager.broadcast_batch_status(
                    EventType.BATCH_ERROR, f"Manual generation completed with {results['failed']} failures", results
                )
            else:
                await websocket_manager.broadcast_batch_status(
                    EventType.BATCH_COMPLETED,
                    f"Manual generation completed successfully: {results['successful']} files",
                    results,
                )

        return {
            "success": True,
            "message": "Documentation generation completed",
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in manual generation: {e}")

        await websocket_manager.broadcast_batch_status(
            EventType.BATCH_ERROR, f"Manual generation failed: {str(e)}", {"error": str(e)}
        )

        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}") from e


@app.post("/api/generate/file/{filename}", operation_id="generate_file")  # type: ignore[misc]
async def trigger_single_file_generation(filename: str, force: bool = False) -> dict[str, Any]:
    """
    Manually trigger documentation generation for a single file.

    Args:
        filename: Name of the Python file (with or without .py extension)
        force: Force regeneration even if docs already exist

    Returns:
        Dictionary with generation results
    """
    try:
        if not filename.endswith(".py"):
            filename += ".py"

        # Use APPS_DIR for compatibility with tests that patch it
        file_path = APPS_DIR / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")

        logger.info(f"Manual single file generation triggered for {filename} (force={force})")

        # Create batch generator and generate for single file
        batch_generator = BatchDocGenerator(APPS_DIR, DOCS_DIR)

        output_file = DOCS_DIR / f"{file_path.stem}.md"

        # Check if should skip
        if not force and output_file.exists():
            return {
                "success": True,
                "message": f"Documentation already exists for {filename}",
                "output_file": str(output_file),
                "skipped": True,
            }

        # Broadcast start event
        await websocket_manager.broadcast_batch_status(
            EventType.DOC_GENERATION_STARTED,
            f"Generating documentation for {filename}",
            {"file_path": str(file_path), "current_file": filename, "trigger": "manual"},
        )

        # Generate documentation
        docs, success = batch_generator.generate_single_file_docs(file_path)

        if success:
            # Write to output file
            output_file.write_text(docs, encoding="utf-8")

            await websocket_manager.broadcast_batch_status(
                EventType.DOC_GENERATION_COMPLETED,
                f"Successfully generated documentation for {filename}",
                {"file_path": str(file_path), "output_path": str(output_file), "current_file": filename},
            )

            return {
                "success": True,
                "message": f"Documentation generated successfully for {filename}",
                "output_file": str(output_file),
                "skipped": False,
            }
        else:
            error_msg = f"Generation failed for {filename}"

            await websocket_manager.broadcast_batch_status(
                EventType.DOC_GENERATION_ERROR, error_msg, {"file_path": str(file_path), "current_file": filename}
            )

            raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in single file generation: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}") from e


@app.post("/api/generate/index", operation_id="generate_index")  # type: ignore[misc]
async def regenerate_index() -> dict[str, Any]:
    """
    Regenerate only the index file from current automation files.
    """
    try:
        batch_generator = BatchDocGenerator(MIRRORED_APPS_DIR, DOCS_DIR)
        index_content = batch_generator.generate_index_file()
        index_path = DOCS_DIR / "README.md"
        index_path.write_text(index_content, encoding="utf-8")

        await websocket_manager.broadcast_batch_status(
            EventType.BATCH_COMPLETED, "Index file regenerated", {"index_path": str(index_path)}
        )

        return {"success": True, "message": "Index regenerated", "index_path": str(index_path)}
    except Exception as e:
        await websocket_manager.broadcast_batch_status(
            EventType.BATCH_ERROR, f"Failed to regenerate index: {str(e)}", {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail="Failed to regenerate index") from e


@app.post("/api/ws/broadcast", operation_id="broadcast_test")  # type: ignore[misc]
async def broadcast_test_message(message: str = "Test message") -> dict[str, Any]:
    """
    Send a test broadcast message to all connected WebSocket clients.

    Args:
        message: The test message to broadcast

    Returns:
        Dictionary with broadcast results
    """
    try:
        event = WebSocketEvent(event_type=EventType.SYSTEM_STATUS, data={"message": message, "type": "test_broadcast"})

        clients_notified = await websocket_manager.broadcast(event)

        return {
            "success": True,
            "message": message,
            "clients_notified": clients_notified,
            "total_connections": websocket_manager.get_connection_count(),
        }
    except Exception as e:
        logger.error(f"Error broadcasting test message: {e}")
        raise HTTPException(status_code=500, detail="Error broadcasting message") from e


# Initialize MCP integration with proper error handling
try:
    mcp = FastApiMCP(app)
    mcp.mount_http()
    logger.info("✅ MCP integration initialized successfully")
except Exception as e:
    logger.warning(f"⚠️ MCP integration failed to initialize: {e}")
    logger.warning("Server will continue without MCP functionality")
    # Continue without MCP - this is not a critical failure


def main() -> None:
    """
    Main entry point for the documentation server.

    Configures and starts the uvicorn server with optimal settings.

    Environment Variables:
        HOST: Server host (default: 0.0.0.0)
        PORT: Server port (default: 8080)
        RELOAD: Enable auto-reload (default: true)
        LOG_LEVEL: Logging level (default: info)
        DOCS_DIR: Documentation output directory (default: /app/docs)
        APPS_DIR: AppDaemon source directory (default: /app/appdaemon-apps)
        FORCE_REGENERATE: Force regenerate all docs on startup (default: false)
        ENABLE_FILE_WATCHER: Enable file watching (default: true)
        WATCH_DEBOUNCE_DELAY: File watcher debounce delay in seconds (default: 2.0)
        WATCH_MAX_RETRIES: Maximum retry attempts for failed generations (default: 3)
        WATCH_FORCE_REGENERATE: Force regenerate on file changes (default: false)
        WATCH_LOG_LEVEL: File watcher log level (default: INFO)
    """
    # Get configuration from centralized utilities
    server_config = get_server_config()
    env_config = get_environment_config()
    dir_status = DirectoryStatus(REAL_APPS_DIR, DOCS_DIR)

    # Print comprehensive startup information
    print_startup_info(dir_status, server_config, env_config)

    # Create uvicorn configuration
    config = uvicorn.Config(
        "server.main:app",
        host=server_config["host"],
        port=server_config["port"],
        reload=server_config["reload"],
        log_level=server_config["log_level"],
        access_log=True,
        use_colors=True,
    )

    server = uvicorn.Server(config)

    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        logger.info("\n👋 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        raise


if __name__ == "__main__":
    main()
