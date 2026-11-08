# Stage 1: Build dependencies and virtual environment using uv
FROM ghcr.io/astral-sh/uv:python3.11-slim-bookworm AS builder

WORKDIR /app

# Enable bytecode compilation and disable uv installer warnings
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy dependency definition files
COPY pyproject.toml uv.lock* ./

# Install dependencies into /app/.venv without dev dependencies
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

# Copy application source code
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev || uv sync --no-dev

# Stage 2: Runtime image
FROM python:3.11-slim-bookworm

WORKDIR /app

# Create a non-privileged user for security
RUN groupadd -g 1000 appuser && useradd -u 1000 -g appuser -m appuser

# Copy virtual environment and application code from builder
COPY --from=builder --chown=appuser:appuser /app /app

# Ensure data directory exists with correct permissions for SQLite storage
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# Switch to non-root user
USER appuser

# Set PATH to include the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Run uvicorn server in production mode
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
