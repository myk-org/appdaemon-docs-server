# AppDaemon Documentation Server

Containerized documentation service that automatically generates comprehensive documentation from your AppDaemon automation files. Features real-time file monitoring, a modern web interface, and zero-configuration deployment.

## Overview

This Docker-based service transforms your AppDaemon Python automation files into beautiful, searchable documentation with automatic generation, real-time updates, and professional presentation. Simply mount your AppDaemon apps directory and access instant documentation through a responsive web interface.

## Key Features

- 🐳 **Docker-Only Deployment** - Production-ready containerized service, no local Python setup required
- 🚀 **Auto-Generation** - Automatically creates documentation from AppDaemon Python files on startup
- 👀 **Real-Time Monitoring** - Watches for file changes and regenerates documentation automatically
- 🔄 **Live Updates** - WebSocket integration provides instant notifications of changes
- 📱 **Mobile Responsive** - Modern web interface that works on all devices
- 🔍 **Full-Text Search** - Built-in search functionality across all documentation
- 📊 **Mermaid Diagrams** - Automatic generation of architecture and flow diagrams
- 🎨 **Professional UI** - Clean, modern interface with dark/light theme support
- 📈 **Health Monitoring** - Comprehensive status reporting and error tracking

## Quick Start

### Local Development

For local development and testing:

```bash
git clone https://github.com/myk-org/appdaemon-docs-server
cd appdaemon-docs-server
uv sync
uv run server/run-dev.py
```

Then open http://127.0.0.1:8080 in your browser.

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed local development instructions.

### Testing

Run the test suite:

```bash
# Run all tests
uv run pytest server/tests/

# Run API tests only
uv run pytest server/tests/api/

# Run UI tests only (requires system dependencies)
uv run pytest server/tests/ui/

# Run with test runner script
uv run python run-tests.py
```

The test suite includes:
- **API Tests** (`server/tests/api/`): Documentation generation and file watching
- **UI Tests** (`server/tests/ui/`): Color contrast, accessibility, and interface functionality using Playwright

### Production Deployment

### 1. Clone the Repository

```bash
git clone https://github.com/myk-org/appdaemon-docs-server
cd appdaemon-docs-server
```

### 2. Build the Docker Image

```bash
docker build -t appdaemon-docs-server .
```

### 3. Run with Docker

```bash
docker run -d \
  --name appdaemon-docs \
  -p 8080:8080 \
  -v /path/to/your/appdaemon/apps:/app/appdaemon-apps:ro \
  appdaemon-docs-server
```

### 4. Run with Docker Compose (Recommended)

Copy the provided `docker-compose.yml` file and customize the volume path:

```bash
# Edit docker-compose.yml to set your AppDaemon apps path
docker compose up -d
```

**Podman users:**

```bash
podman-compose up -d
# or
podman compose up -d  # (if using podman 4.0+)
```

See the [docker-compose.yml](./docker-compose.yml) file for a complete example with all configuration options.

## How It Works

1. **Mount Your Apps** - Point the container to your AppDaemon apps directory
2. **Automatic Scanning** - Service discovers all Python automation files
3. **Documentation Generation** - Creates comprehensive markdown documentation
4. **Web Interface** - Access your docs at <http://localhost:8080>
5. **Live Updates** - Changes to your Python files automatically regenerate docs

## Configuration

All configuration is handled through environment variables:

### Core Settings

| Variable    | Default   | Description                                 |
| ----------- | --------- | ------------------------------------------- |
| `HOST`      | `0.0.0.0` | Server bind address                         |
| `PORT`      | `8080`    | Server port                                 |
| `LOG_LEVEL` | `info`    | Logging level (debug, info, warning, error) |

### Directory Configuration

| Variable   | Default               | Description                                      |
| ---------- | --------------------- | ------------------------------------------------ |
| `APPS_DIR` | `/app/appdaemon-apps` | Container mount point for AppDaemon source files |
| `DOCS_DIR` | `/app/docs`           | Generated documentation directory (auto-created) |

### Generation Settings

| Variable               | Default | Description                                    |
| ---------------------- | ------- | ---------------------------------------------- |
| `FORCE_REGENERATE`     | `false` | Force regenerate all docs on startup           |
| `ENABLE_FILE_WATCHER`  | `true`  | Enable real-time file monitoring               |
| `WATCH_DEBOUNCE_DELAY` | `2.0`   | Delay before processing file changes (seconds) |

### Production Example

```yaml
version: "3.8"
services:
  docs-server:
    image: appdaemon-docs-server
    container_name: appdaemon-docs
    ports:
      - "8080:8080"
    volumes:
      - /opt/appdaemon/apps:/app/appdaemon-apps:ro
    environment:
      - LOG_LEVEL=warning
      - FORCE_REGENERATE=false
      - ENABLE_FILE_WATCHER=true
      - WATCH_DEBOUNCE_DELAY=3.0
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
```

## Service Architecture

### Startup Process

1. **Container Initialization** - Service starts and validates configuration
2. **Directory Setup** - Creates documentation output directory
3. **File Discovery** - Scans apps directory for Python automation files
4. **Batch Generation** - Generates documentation for all discovered files
5. **File Watcher** - Starts monitoring for changes
6. **Web Server** - Launches FastAPI server with documentation interface

### Real-Time Updates

- **File Monitoring** - Detects changes to Python files
- **Debounced Processing** - Prevents excessive regeneration during rapid changes
- **WebSocket Notifications** - Broadcasts updates to connected clients
- **Automatic Refresh** - Browser automatically updates when documentation changes

## Web Interface

### Documentation Browser

- **File List** - Browse all generated documentation files
- **Search** - Full-text search across all documentation
- **Syntax Highlighting** - Code blocks with proper Python highlighting
- **Mobile Responsive** - Optimized for phones and tablets

### Features

- **Mermaid Diagrams** - Automatic architecture and flow diagrams
- **Code Analysis** - Function signatures, class hierarchies, and dependencies
- **Cross-References** - Links between related automation files
- **Error Reporting** - Clear indication of generation issues

## API Endpoints

### Health and Status

```bash
# Service health check
GET /health

# File watcher status
GET /api/watcher/status

# WebSocket connection status
GET /api/ws/status
```

### Documentation Access

```bash
# Main documentation index
GET /docs/

# Specific documentation file
GET /docs/{filename}

# Search documentation
GET /api/search?q=query

# List all files
GET /api/files
```

### Manual Operations

```bash
# Force regenerate all documentation
POST /api/generate/all?force=true

# Regenerate specific file
POST /api/generate/file/{filename}?force=true
```

## Monitoring

### Health Check Responses

- `healthy` - Service operational, documentation current
- `starting` - Service initializing, generation in progress
- `degraded` - Service operational with some generation errors
- `unhealthy` - Critical errors preventing operation

### Log Levels

- `debug` - Detailed processing information
- `info` - General operational status
- `warning` - Non-critical issues
- `error` - Critical errors requiring attention

### Monitoring Commands

```bash
# Check service health
curl -s http://localhost:8080/health | jq

# Monitor file watcher
curl -s http://localhost:8080/api/watcher/status | jq

# View documentation count
curl -s http://localhost:8080/api/files | jq '.files | length'
```

### Debug Mode

Enable detailed logging:

```yaml
environment:
  - LOG_LEVEL=debug
  - WATCH_LOG_LEVEL=DEBUG
```

### Performance Tuning

For large AppDaemon installations:

```yaml
environment:
  - WATCH_DEBOUNCE_DELAY=5.0 # Reduce CPU usage
  - FORCE_REGENERATE=false # Faster startups
```

## Security Considerations

- **Read-Only Mounts** - Always mount apps directory as read-only (`:ro`)
- **Network Access** - Consider restricting container network access
- **User Permissions** - Run container with non-root user when possible
- **File Permissions** - Ensure AppDaemon files have appropriate permissions

## Integration Examples

### Home Assistant Add-on

```yaml
# configuration.yaml
services:
  appdaemon:
    image: acockburn/appdaemon:latest
    volumes:
      - /config/appdaemon:/conf

  docs-server:
    image: appdaemon-docs-server
    ports:
      - "8080:8080"
    volumes:
      - /config/appdaemon/apps:/app/appdaemon-apps:ro
    depends_on:
      - appdaemon
```

### Reverse Proxy

```nginx
# nginx.conf
location /appdaemon-docs/ {
    proxy_pass http://localhost:8080/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## Resource Requirements

### Minimum Requirements

- **CPU**: 1 core
- **Memory**: 256MB RAM
- **Storage**: 100MB + documentation size
- **Network**: HTTP/HTTPS access

### Recommended for Production

- **CPU**: 2 cores
- **Memory**: 512MB RAM
- **Storage**: 1GB + documentation size
- **Network**: Reverse proxy with SSL

## Support and Contributing

This is a production-ready service designed for containerized deployment. For issues, feature requests, or contributions, please follow standard Docker best practices and FastAPI development patterns.

## License

This project provides documentation generation services for AppDaemon automation systems.
