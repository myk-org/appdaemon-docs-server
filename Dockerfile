# Multi-stage build for optimized production image
FROM python:3.13-slim as builder

# Set environment variables for UV
ENV UV_GLOBAL_DIR=/app/.uv
ENV UV_CACHE_DIR=/app/.uv/cache
ENV PATH="/root/.local/bin:$PATH"

# Copy UV from official container
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy UV configuration and dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using UV
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.13-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_GLOBAL_DIR=/app/.uv
ENV PATH="/usr/local/bin:$PATH"

# Copy UV from official container
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install curl for health check and update packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 docs && \
    useradd --uid 1000 --gid docs --shell /bin/bash --create-home docs

# Set working directory
WORKDIR /app

# Copy dependencies from builder stage
COPY --from=builder /app/.uv /app/.uv

# Create application directories first
RUN mkdir -p /app/templates /app/static /app/docs && chown -R docs:docs /app

# Copy application files from server directory
COPY --chown=docs:docs server/ ./
COPY --chown=docs:docs pyproject.toml uv.lock ./

# Switch to non-root user
USER docs

# Expose port
EXPOSE 8080

# Health check using curl (more reliable than Python requests)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the application
CMD ["uv", "run", "main.py"]
