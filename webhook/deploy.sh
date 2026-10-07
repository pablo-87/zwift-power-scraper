#!/bin/bash

# Exit on any error
set -e

# Configuration
PROJECT_DIR="/opt/zwift-scraper"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/deployment.log"

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Logging function with timestamps
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Error handling function
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Start deployment
log "=========================================="
log "Starting deployment process"
log "=========================================="

# Navigate to project directory
cd "${PROJECT_DIR}" || error_exit "Failed to navigate to project directory"

# Store current commit hash
CURRENT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
log "Current commit: ${CURRENT_COMMIT}"

# Pull latest code from GitHub
log "Pulling latest code from GitHub..."
git fetch origin main || error_exit "Failed to fetch from GitHub"
git reset --hard origin/main || error_exit "Failed to reset to origin/main"

# Get new commit hash
NEW_COMMIT=$(git rev-parse HEAD)
log "New commit: ${NEW_COMMIT}"

# Check if there were any changes
if [ "${CURRENT_COMMIT}" = "${NEW_COMMIT}" ]; then
    log "No changes detected. Deployment skipped."
    exit 0
fi

# Check if Dockerfile or requirements.txt changed
DOCKERFILE_CHANGED=$(git diff --name-only "${CURRENT_COMMIT}" "${NEW_COMMIT}" | grep -E '^Dockerfile$' || true)
REQUIREMENTS_CHANGED=$(git diff --name-only "${CURRENT_COMMIT}" "${NEW_COMMIT}" | grep -E '^requirements\.txt$' || true)

REBUILD_NEEDED=false
if [ -n "${DOCKERFILE_CHANGED}" ] || [ -n "${REQUIREMENTS_CHANGED}" ]; then
    REBUILD_NEEDED=true
    log "Detected changes in Dockerfile or requirements.txt"
    log "Full rebuild required"
else
    log "No changes in Dockerfile or requirements.txt"
    log "Skipping rebuild"
fi

# Navigate to project root for docker-compose
cd "${PROJECT_DIR}/zwift-power-scraper" || error_exit "Failed to navigate to docker-compose directory"

# Rebuild if needed
if [ "${REBUILD_NEEDED}" = true ]; then
    log "Building Docker image with --no-cache..."
    docker-compose build --no-cache scraper || error_exit "Failed to build Docker image"
    log "Docker image built successfully"
else
    log "Using existing Docker image"
fi

# Stop and remove only the scraper container (preserve database)
log "Stopping scraper container..."
docker-compose stop scraper || error_exit "Failed to stop scraper container"
docker-compose rm -f scraper || log "Warning: Failed to remove scraper container (may not exist)"

# Start the scraper container
log "Starting scraper container..."
docker-compose up -d scraper || error_exit "Failed to start scraper container"

# Wait a few seconds for container to initialize
sleep 5

# Verify containers are running
log "Verifying container status..."
SCRAPER_STATUS=$(docker-compose ps -q scraper | xargs docker inspect -f '{{.State.Status}}' 2>/dev/null || echo "not found")
POSTGRES_STATUS=$(docker-compose ps -q postgres | xargs docker inspect -f '{{.State.Status}}' 2>/dev/null || echo "not found")

log "Scraper container status: ${SCRAPER_STATUS}"
log "PostgreSQL container status: ${POSTGRES_STATUS}"

# Check if scraper is running
if [ "${SCRAPER_STATUS}" != "running" ]; then
    error_exit "Scraper container failed to start"
fi

# Check if postgres is running
if [ "${POSTGRES_STATUS}" != "running" ]; then
    log "WARNING: PostgreSQL container is not running"
fi

# Log container details
log "Container details:"
docker-compose ps | tee -a "${LOG_FILE}"

# Success
log "=========================================="
log "Deployment completed successfully"
log "=========================================="

exit 0
