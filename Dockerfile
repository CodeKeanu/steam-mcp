# Steam MCP Server Dockerfile
# Multi-stage build for minimal image size

FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Copy only what's needed for installation
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install package into a clean prefix (no venv overhead)
RUN pip install --prefix=/install --no-warn-script-location .

# Production stage - minimal runtime image
FROM python:3.12-slim AS production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/install/lib/python3.12/site-packages \
    PATH="/install/bin:$PATH"

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser

WORKDIR /app

# Copy installed packages from builder (includes steam_mcp and dependencies)
COPY --from=builder /install /install

# Switch to non-root user
USER appuser

# Default command - run the MCP server
CMD ["steam-mcp"]
