"""
Documentation Web Server

FastAPI application to serve AppDaemon automation documentation with
markdown rendering, syntax highlighting, and responsive UI.
"""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_mcp import FastApiMCP
from pygments.formatters import HtmlFormatter

from server.generators.batch_doc_generator import BatchDocGenerator
from server.processors.markdown import MarkdownProcessor
from server.services.docs import DocumentationService
from server.utils.utils import (
    DirectoryStatus,
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

# Application metadata - configurable via environment variables
APP_VERSION = "1.0.0"
APP_TITLE = os.getenv("APP_TITLE", "AppDaemon Documentation Server")
APP_DESCRIPTION = os.getenv(
    "APP_DESCRIPTION", "Web interface for AppDaemon automation documentation with markdown rendering"
)


# Base paths - resolve at startup for better performance
APPS_DIR_FROM_ENV = os.getenv("APPS_DIR")

if not APPS_DIR_FROM_ENV:
    raise ValueError("APPS_DIR environment variable not set")

APPS_DIR = Path(APPS_DIR_FROM_ENV).resolve()
DOCS_DIR = Path(os.getenv("DOCS_DIR", "data/generated-docs")).resolve()
TEMPLATES_DIR = Path(os.getenv("TEMPLATES_DIR", "server/templates")).resolve()
STATIC_DIR = Path(os.getenv("STATIC_DIR", "server/static")).resolve()

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
        # Create batch generator
        batch_generator = BatchDocGenerator(APPS_DIR, DOCS_DIR)

        # Broadcast startup event
        await websocket_manager.broadcast_batch_status(
            EventType.BATCH_STARTED,
            "Starting initial documentation generation on server startup",
            {"phase": "startup", "apps_directory": str(APPS_DIR)},
        )

        # Progress callback setup
        async def progress_callback(current: int, total: int, current_file: str, stage: str) -> None:
            logger.debug(f"Generation progress: {current}/{total} - {current_file} ({stage})")
            await websocket_manager.broadcast_generation_progress(
                current=current, total=total, current_file=current_file, stage=stage
            )

        def sync_progress_callback(current: int, total: int, current_file: str, stage: str) -> None:
            """Sync wrapper for async progress callback with proper task tracking."""
            task = asyncio.create_task(progress_callback(current, total, current_file, stage))
            pending_tasks.add(task)
            task.add_done_callback(pending_tasks.discard)

        # Run generation
        results = batch_generator.generate_all_docs(
            force_regenerate=config["force_regenerate"], progress_callback=sync_progress_callback
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
            watch_directory=APPS_DIR,
            output_directory=DOCS_DIR,
            debounce_delay=config["watch_debounce_delay"],
            max_retry_attempts=config["watch_max_retries"],
            force_regenerate=config["watch_force_regenerate"],
            log_level=config["watch_log_level"],
        )

        # Initialize and start file watcher
        watcher = FileWatcher(watch_config)
        await watcher.start_watching()

        logger.info(f"✅ File watcher started successfully for {APPS_DIR}")

        await websocket_manager.broadcast_batch_status(
            EventType.WATCHER_STATUS,
            "File watcher started successfully",
            {"watch_directory": str(APPS_DIR), "status": "active"},
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

    # Startup
    logger.info(f"Starting {APP_TITLE} v{APP_VERSION}")
    logger.info(f"Documentation directory: {DOCS_DIR}")
    logger.info(f"Apps directory: {APPS_DIR}")

    startup_errors.clear()

    try:
        # Initialize directories and check status
        logger.info("📁 Initializing directories...")
        DOCS_DIR.mkdir(parents=True, exist_ok=True)

        # Get directory status and configuration
        dir_status = DirectoryStatus(APPS_DIR, DOCS_DIR)
        config = get_environment_config()

        # Log directory status
        if not dir_status.apps_exists:
            error_msg = f"Apps directory not found: {APPS_DIR}"
            logger.error(error_msg)
            startup_errors.append(error_msg)
        else:
            logger.info(f"Found {dir_status.apps_count} automation files to process")

        # Run initial documentation generation
        startup_generation_completed = await run_initial_documentation_generation(dir_status, config)

        # Start file watcher
        file_watcher = await start_file_watcher(dir_status, config)

        # Final startup status
        dir_status.log_status(logger)
        await broadcast_startup_completion(dir_status, file_watcher, startup_generation_completed)

    except Exception as e:
        logger.error(f"Critical startup error: {e}")
        startup_errors.append(f"Critical startup error: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down documentation server")

    try:
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


# API Routes with proper error handling and response models


@app.get("/", response_class=RedirectResponse)  # type: ignore[misc]
async def root() -> RedirectResponse:
    """Root endpoint - redirect to documentation index."""
    return RedirectResponse(url="/docs/", status_code=307)


@app.get("/health", operation_id="health")  # type: ignore[misc]
async def health_check() -> dict[str, str | bool | int | list[str]]:
    """
    Health check endpoint for monitoring server status.

    Returns:
        Health status information including startup generation status
    """
    global file_watcher, startup_generation_completed, startup_errors

    docs_exists = DOCS_DIR.exists()
    apps_exists = APPS_DIR.exists()
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

    return {
        "status": status,
        "service": "appdaemon-docs-server",
        "version": APP_VERSION,
        "docs_directory_exists": docs_exists,
        "apps_directory_exists": apps_exists,
        "docs_files_count": docs_count,
        "startup_generation_completed": startup_generation_completed,
        "file_watcher_active": file_watcher is not None and file_watcher.is_watching,
        "startup_errors_count": len(startup_errors),
        "startup_errors": startup_errors,
        "uptime": "running",
    }


@app.get("/api/files", operation_id="list_files")  # type: ignore[misc]
async def list_documentation_files() -> dict[str, list[dict[str, Any]] | int | bool | str]:
    """
    List all available documentation files with metadata.

    Returns:
        Dictionary containing file list and metadata
    """
    try:
        files = await docs_service.get_file_list()
        return {
            "files": files,
            "total_count": len(files),
            "docs_available": DOCS_DIR.exists(),
            "docs_directory": str(DOCS_DIR),
        }
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail="Error listing documentation files") from e


@app.get("/api/file/{filename}", operation_id="get_file")  # type: ignore[misc]
async def get_file_content(filename: str) -> dict[str, str]:
    """
    Get processed content for a specific documentation file.

    Args:
        filename: Name of the markdown file (with or without .md extension)

    Returns:
        Dictionary containing processed HTML content and metadata
    """
    try:
        html_content, title = await docs_service.get_file_content(filename)
        return {"filename": filename, "title": title, "content": html_content, "type": "markdown"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file content for {filename}: {e}")
        raise HTTPException(status_code=500, detail="Error processing file content") from e


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
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "title": "AppDaemon Documentation",
                "files": files,
                "total_files": len(files),
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
            "document.html",
            {
                "request": request,
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
async def search_documentation(q: str = "") -> dict[str, list[dict[str, Any]] | str | int]:
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
                            context = content[context_start:context_end].strip()
                            # Highlight the search term
                            context = context.replace(query, f"**{query}**")

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
        if not APPS_DIR.exists():
            raise HTTPException(status_code=404, detail=f"Apps directory not found: {APPS_DIR}")

        logger.info(f"Manual full generation triggered (force={force})")

        if file_watcher:
            # Use file watcher's generation method for consistency
            results = await file_watcher.generate_all_docs(force=force)
        else:
            # Fallback to direct batch generation
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
    dir_status = DirectoryStatus(APPS_DIR, DOCS_DIR)

    # Print comprehensive startup information
    print_startup_info(dir_status, server_config, env_config)

    # Create uvicorn configuration
    config = uvicorn.Config(
        "main:app",
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
