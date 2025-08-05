# AppDaemon Documentation Server

FastAPI-based documentation web server that automatically generates comprehensive documentation from your AppDaemon automation files. Features real-time file monitoring, modern web interface, and AI agent integration through MCP (Model Context Protocol).

## Overview

This containerized service transforms your AppDaemon Python automation files into beautiful, searchable documentation with automatic generation, real-time updates, and professional presentation. The service provides both web-based access and programmatic access through MCP for AI agents.

## Key Features

- 🚀 **Auto-Generation** - Automatically creates documentation from AppDaemon Python files on startup
- 👀 **Real-Time Monitoring** - Watches for file changes and regenerates documentation automatically
- 🔄 **Live Updates** - WebSocket integration provides instant notifications of changes
- 📱 **Modern Web Interface** - Responsive design with syntax highlighting and search
- 🔍 **Full-Text Search** - Built-in search functionality across all documentation
- 🤖 **MCP Integration** - AI agent support through Model Context Protocol
- 📈 **Health Monitoring** - Comprehensive status reporting and error tracking
- 🐳 **Docker Ready** - Production-ready containerized deployment

## Quick Start

### Local Development

For local development and testing:

```bash
git clone <repository-url>
cd appdaemon-docs-server
uv sync
```

Create a `.dev_env` file with your configuration:

```bash
# Example .dev_env file
APPS_DIR=/path/to/your/appdaemon/apps
HOST=127.0.0.1
PORT=8080
LOG_LEVEL=info
RELOAD=true
FORCE_REGENERATE=false
ENABLE_FILE_WATCHER=true
WATCH_DEBOUNCE_DELAY=2.0
```

Run the development server:

```bash
uv run server/run-dev.py
```

The server will be available at http://127.0.0.1:8080

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed local development instructions.

### Production Deployment with Docker

#### 1. Build the Docker Image

```bash
docker build -t appdaemon-docs-server .
```

#### 2. Run with Docker

```bash
docker run -d \
  --name appdaemon-docs \
  -p 8080:8080 \
  -e APPS_DIR=/app/appdaemon-apps \
  -v /path/to/your/appdaemon/apps:/app/appdaemon-apps:ro \
  appdaemon-docs-server
```

#### 3. Run with Docker Compose (Recommended)

Use the provided `docker-compose.yml` file and customize the volume path:

```yaml
services:
  appdaemon-docs-server:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: appdaemon-docs-server
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - /path/to/your/appdaemon/apps:/app/appdaemon-apps:ro
    environment:
      - APPS_DIR=/app/appdaemon-apps
      - HOST=0.0.0.0
      - PORT=8080
      - LOG_LEVEL=info
      - FORCE_REGENERATE=false
      - ENABLE_FILE_WATCHER=true
      - WATCH_DEBOUNCE_DELAY=2.0
```

Start the service:

```bash
docker compose up -d
```

Access your documentation at http://localhost:8080

## Configuration

All configuration is handled through environment variables:

### Required Environment Variables

| Variable   | Description                                      | Example                        |
| ---------- | ------------------------------------------------ | ------------------------------ |
| `APPS_DIR` | Path to AppDaemon source files                   | `/app/appdaemon-apps`          |

### Optional Environment Variables

| Variable               | Default    | Description                                      |
| ---------------------- | ---------- | ------------------------------------------------ |
| `HOST`                 | `0.0.0.0`  | Server bind address                              |
| `PORT`                 | `8080`     | Server port                                      |
| `LOG_LEVEL`            | `info`     | Logging level (debug, info, warning, error)     |
| `RELOAD`               | `false`    | Enable auto-reload for development              |
| `FORCE_REGENERATE`     | `false`    | Force regenerate all docs on startup            |
| `ENABLE_FILE_WATCHER`  | `true`     | Enable real-time file monitoring                |
| `WATCH_DEBOUNCE_DELAY` | `2.0`      | Delay before processing file changes (seconds)  |
| `WATCH_MAX_RETRIES`    | `3`        | Maximum retry attempts for failed generations   |
| `WATCH_FORCE_REGENERATE` | `false`  | Force regenerate on file changes                |
| `WATCH_LOG_LEVEL`      | `INFO`     | File watcher log level                           |
| `APP_TITLE`            | `AppDaemon Documentation Server` | Application title |
| `APP_DESCRIPTION`      | `Web interface for AppDaemon...` | Application description |

## How It Works

1. **Startup** - Service scans your AppDaemon apps directory for Python files
2. **Generation** - Creates comprehensive markdown documentation for each automation file
3. **Web Interface** - Serves documentation through FastAPI with modern UI
4. **File Watching** - Monitors for changes and regenerates documentation automatically
5. **Real-time Updates** - WebSocket connections notify browsers of changes instantly

## Web Interface

### Main Features

- **Documentation Index** - Browse all generated documentation files at `/docs/`
- **Individual Files** - View specific documentation at `/docs/{filename}`
- **Search** - Full-text search across all documentation
- **Syntax Highlighting** - Python code blocks with proper formatting
- **Responsive Design** - Works on desktop, tablet, and mobile devices

### Available Pages

- `/` - Redirects to documentation index
- `/docs/` - Main documentation index page
- `/docs/{filename}` - Individual documentation file viewer
- `/health` - Service health check endpoint

## API Endpoints

### Core API

```bash
# Health and status
GET /health                          # Service health check
GET /api/watcher/status             # File watcher status
GET /api/ws/status                  # WebSocket connection status

# Documentation access
GET /api/files                      # List all documentation files
GET /api/file/{filename}            # Get processed file content
GET /api/search?q=query            # Search documentation

# Manual operations
POST /api/generate/all?force=true   # Force regenerate all documentation
POST /api/generate/file/{filename}?force=true  # Regenerate specific file
```

### WebSocket

```bash
# Real-time updates
WS /ws                              # WebSocket for live updates
```

### MCP Integration

```bash
# Model Context Protocol for AI agents
GET/POST /mcp/                      # MCP HTTP endpoint
GET /mcp/sse                        # MCP Server-Sent Events
```

## MCP Integration for AI Agents

The service includes built-in Model Context Protocol (MCP) support for AI agent integration.

### Available MCP Tools

The server automatically generates MCP tools from FastAPI endpoints. Tools are named based on the endpoint pattern and include:

- **HTTP endpoint tools** - Auto-generated from API routes (e.g., `trigger_full_generation_api_generate_all_post`)
- **Documentation access** - List files, get content, and search functionality
- **System management** - Health checks, watcher status, and WebSocket monitoring
- **File operations** - Regenerate documentation for all files or specific files

Tool names follow the FastAPI endpoint pattern: `{method}_{path_components}_{http_method}`

### Connecting AI Agents

To connect an MCP-compatible AI agent:

1. **Verify server is running:**
   ```bash
   # Check server health
   curl http://your-server-ip:port/health

   # Test MCP connection directly
   npx mcp-remote your-server-ip:port/mcp --allow-http
   ```

2. **Configure Claude Code CLI** with the MCP server:

   **For Local Server:**
   ```json
   {
     "mcpServers": {
       "appdaemon-docs-local": {
         "command": "npx",
         "args": [
           "mcp-remote",
           "http://localhost:8080/mcp"
         ]
       }
     }
   }
   ```

   **For Remote Server:**
   ```json
   {
     "mcpServers": {
       "appdaemon-docs": {
         "command": "npx",
         "args": [
           "mcp-remote",
           "http://your-server-ip:port/mcp",
           "--allow-http"
         ]
       }
     }
   }
   ```

   **Note:** The `--allow-http` flag is required when connecting to remote HTTP servers (non-HTTPS).

3. **Test the connection** by asking Claude to list your automation files

### Benefits for AI Assistance

- **Code Understanding** - AI can analyze your automation logic and suggest improvements
- **Documentation Search** - Natural language queries to find relevant automations
- **Development Help** - Get assistance with debugging and new automation patterns
- **Architecture Analysis** - Understand relationships between automation modules

## Testing

The project includes comprehensive test suites:

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest server/tests/api/        # API functionality tests
uv run pytest server/tests/ui/         # UI and accessibility tests

# Run with coverage
uv run pytest --cov=server
```

### Test Categories

- **API Tests** - Documentation generation, file watching, and API endpoints
- **UI Tests** - Color contrast, accessibility, and interface functionality using Playwright

## Monitoring and Health Checks

### Health Check Response

```json
{
  "status": "healthy",
  "service": "appdaemon-docs-server",
  "version": "1.0.0",
  "docs_directory_exists": true,
  "apps_directory_exists": true,
  "docs_files_count": 45,
  "startup_generation_completed": true,
  "file_watcher_active": true,
  "startup_errors_count": 0,
  "startup_errors": [],
  "uptime": "running"
}
```

### Status Values

- `healthy` - Service operational, documentation current
- `starting` - Service initializing, generation in progress
- `degraded` - Service operational with some generation errors
- `unhealthy` - Critical errors preventing operation

### Monitoring Commands

```bash
# Check overall health
curl http://localhost:8080/health

# Monitor file watcher
curl http://localhost:8080/api/watcher/status

# Check WebSocket status
curl http://localhost:8080/api/ws/status

# Count documentation files
curl http://localhost:8080/api/files | jq '.total_count'
```

## Performance and Resource Requirements

### System Requirements

- **CPU**: 1+ cores (2+ recommended for production)
- **Memory**: 256MB minimum, 512MB recommended
- **Storage**: 100MB + size of generated documentation
- **Network**: HTTP/HTTPS access for web interface

### Performance Tuning

For large AppDaemon installations:

```yaml
environment:
  - WATCH_DEBOUNCE_DELAY=5.0     # Reduce CPU usage during file changes
  - FORCE_REGENERATE=false       # Faster startup times
  - LOG_LEVEL=warning            # Reduce log verbosity
```

## Security Considerations

- **Read-Only Mounts** - Always mount AppDaemon apps directory as read-only (`:ro`)
- **Non-Root User** - Container runs as non-root user (UID 1000)
- **Network Access** - Consider firewall rules for port 8080
- **MCP Access** - MCP integration provides full API access including documentation regeneration capabilities

## Troubleshooting

### Common Issues

**Service won't start:**
- Check that `APPS_DIR` environment variable is set
- Verify the apps directory exists and is readable
- Check Docker logs: `docker logs appdaemon-docs-server`

**Documentation not generating:**
- Ensure AppDaemon files exist in the mounted directory
- Check file permissions on the apps directory
- Force regeneration: `curl -X POST http://localhost:8080/api/generate/all?force=true`

**File watcher not working:**
- Verify `ENABLE_FILE_WATCHER=true` is set
- Check watcher status: `curl http://localhost:8080/api/watcher/status`
- Review container logs for file system events

**MCP integration issues:**
- Test MCP endpoint: `curl http://localhost:8080/mcp/`
- Verify AI agent configuration includes correct URL
- Check server logs for MCP-related errors

### Debug Mode

Enable detailed logging for troubleshooting:

```yaml
environment:
  - LOG_LEVEL=debug
  - WATCH_LOG_LEVEL=DEBUG
```


## License

This project provides documentation generation services for AppDaemon automation systems.
