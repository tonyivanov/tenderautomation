# TenderAutomation — production Dockerfile
# Build: docker build -t tenderautomation:latest .
# Run: docker-compose up -d

FROM python:3.12-slim-bookworm

ARG APP_COMMIT_SHA=unknown

# System dependencies for Playwright & psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt requirements-dev.txt pyproject.toml /app/
RUN python -m pip install --no-cache-dir --upgrade pip==26.1.2 \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

# Copy application code
COPY src/ /app/src/
COPY filters/ /app/filters/
COPY prompts/ /app/prompts/
COPY migrations/ /app/migrations/
COPY scripts/ /app/scripts/
COPY alembic.ini /app/

# Install project in development mode
RUN pip install -e .

# Create data directory
RUN mkdir -p /app/data

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV APP_COMMIT_SHA=${APP_COMMIT_SHA}

# Default command: start web server
# Override with: docker run tenderautomation:latest python -m core.cli run-pipeline
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
