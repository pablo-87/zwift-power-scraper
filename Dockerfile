# Multi-stage Dockerfile for Zwift Racing Scraper
# Optimized for production use with Playwright support

# Stage 1: Base image with system dependencies
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for Playwright and PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    # PostgreSQL client libraries
    libpq-dev \
    # Build tools (needed for some Python packages)
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Dependencies installation
FROM base as dependencies

WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only for cookie refresh)
RUN playwright install chromium && \
    playwright install-deps chromium

# Stage 3: Final production image
FROM base as production

WORKDIR /app

# Copy installed Python packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy Playwright browsers from dependencies stage
COPY --from=dependencies /root/.cache/ms-playwright /root/.cache/ms-playwright

# Create non-root user for security
RUN useradd -m -u 1000 scraper && \
    chown -R scraper:scraper /app

# Copy application code
COPY --chown=scraper:scraper scraper.py .
COPY --chown=scraper:scraper cookie_refresher.py .
COPY --chown=scraper:scraper database.py .
COPY --chown=scraper:scraper zids.txt .

# Create output directory
RUN mkdir -p /app/output && chown -R scraper:scraper /app/output

# Switch to non-root user
USER scraper

# Health check (optional - checks if Python can import main modules)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import scraper, cookie_refresher, database" || exit 1

# Default command
CMD ["python", "scraper.py"]
