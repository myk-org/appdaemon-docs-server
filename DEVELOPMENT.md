# Local Development Guide

This guide helps you set up and run the AppDaemon Documentation Server locally for development and testing.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## Quick Start

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository-url>
   cd appdaemon-docs-server
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Run the development server:**
   ```bash
   uv run server/run-dev.py
   ```

4. **Access the server:**
   Open your browser to: http://127.0.0.1:8080

## Development Server Features

The `server/run-dev.py` script automatically:
- Creates local directories (`local-docs/` and `local-apps/`)
- Sets up proper environment variables for local development
- Enables hot reload for code changes
- Configures file watching for automatic documentation regeneration

## Local Directory Structure

```
appdaemon-docs-server/
├── local-docs/          # Generated documentation (auto-created)
├── local-apps/          # Place your AppDaemon files here for testing
├── .env.example         # Environment variable examples
└── server/              # Main application code
    ├── run-dev.py       # Development server launcher
    ├── main.py          # Server entry point
    └── ...              # Other server modules
```

## Testing with Real AppDaemon Files

To test the documentation generation with actual AppDaemon automation files:

1. Copy your AppDaemon Python files to the `local-apps/` directory
2. The server will automatically detect changes and regenerate documentation
3. View the generated docs at http://127.0.0.1:8080

## Environment Configuration

Copy `.env.example` to `.env` and customize as needed:

```bash
cp .env.example .env
```

Available environment variables:
- `HOST`: Server host (default: 127.0.0.1)
- `PORT`: Server port (default: 8080)
- `DOCS_DIR`: Documentation output directory
- `APPS_DIR`: AppDaemon source files directory
- `RELOAD`: Enable auto-reload for development
- `LOG_LEVEL`: Logging verbosity (debug, info, warning, error)

## Development Commands

```bash
# Start development server
uv run server/run-dev.py

# Run tests
uv run pytest

# Type checking
uv run mypy server/

# Code formatting
uv run ruff format

# Linting
uv run ruff check
```

## Hot Reload

The development server includes hot reload capabilities:
- Code changes trigger automatic server restart
- File changes in `local-apps/` trigger documentation regeneration
- WebSocket connections provide real-time update notifications

## Troubleshooting

### Permission Issues
If you encounter permission errors, ensure the `local-docs/` and `local-apps/` directories are writable.

### Port Already in Use
If port 8080 is occupied, modify the `PORT` environment variable in your `.env` file or the `run-dev.py` script.

### Dependencies Issues
Run `uv sync` to ensure all dependencies are properly installed.

## Production vs Development

| Feature | Development | Production (Docker) |
|---------|-------------|-------------------|
| File paths | `./local-*` | `/app/*` |
| Hot reload | Enabled | Disabled |
| Host | 127.0.0.1 | 0.0.0.0 |
| Auto-generation | Optional | Enabled |
| File watching | Enabled | Enabled |
