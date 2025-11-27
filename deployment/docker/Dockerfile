# Use Python 3.12 as specified in your .python-version file
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from the uv.lock file
COPY pyproject.toml uv.lock /app/

# Install dependencies
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN uv sync --locked

# Copy application code
COPY . /app/

# Expose the port Dash runs on
EXPOSE 8050

# Add uv env
ENV PATH="$PATH:/app/.venv/bin/activate"

# Command to run the application
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8050", "app:app", "--workers", "4", "--timeout", "120"]