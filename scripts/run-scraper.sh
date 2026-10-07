#!/bin/bash

# Zwift Power Scraper - Cron Execution Script
# This script is designed to be run by cron to execute the scraper daily
# It handles container management, logging, and error recovery

set -e  # Exit on error

# Configuration
PROJECT_DIR="/opt/zwift-scraper"
LOG_FILE="$PROJECT_DIR/logs/cron.log"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
LOG_RETENTION_DAYS=30

# Logging function with timestamps
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $1" | tee -a "$LOG_FILE"
}

# Error handler
error_exit() {
    log "ERROR: $1"
    log "=== Cron Job Failed ==="
    exit 1
}

# Main execution
main() {
    log "=== Cron Job Started ==="
    
    # Navigate to project directory
    cd "$PROJECT_DIR" || error_exit "Failed to navigate to project directory: $PROJECT_DIR"
    log "Working directory: $(pwd)"
    
    # Check if containers are running
    log "Checking container status..."
    if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log "Containers are not running. Starting containers..."
        docker-compose -f "$COMPOSE_FILE" up -d || error_exit "Failed to start containers"
        log "Waiting 10 seconds for containers to initialize..."
        sleep 10
    else
        log "Containers are already running"
    fi
    
    # Execute the scraper
    log "Executing scraper..."
    if docker-compose -f "$COMPOSE_FILE" exec -T scraper python main.py; then
        log "Scraper execution completed successfully"
    else
        error_exit "Scraper execution failed with exit code $?"
    fi
    
    # Cleanup old logs
    log "Cleaning up old log files (older than $LOG_RETENTION_DAYS days)..."
    find "$PROJECT_DIR/logs" -name "*.log" -type f -mtime +$LOG_RETENTION_DAYS -delete 2>/dev/null || true
    log "Log cleanup completed"
    
    log "=== Cron Job Completed ==="
    exit 0
}

# Run main function
main
