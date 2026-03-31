FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Install dependencies (no dev)
RUN uv sync --no-dev --no-editable

# Expose web UI port
EXPOSE 8585

# Run modelarr serve
CMD ["uv", "run", "modelarr", "serve", "--host", "0.0.0.0", "--port", "8585"]
