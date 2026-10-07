#!/bin/bash

################################################################################
# Zwift Power Scraper - Automated Server Setup Script
# 
# This script automates the complete setup of the Zwift Power Scraper on
# Ubuntu Server with CasaOS. It installs dependencies, configures Docker,
# sets up the application, and configures automated execution.
#
# Usage: sudo ./server-setup.sh
# Requirements: Ubuntu Server 20.04+ with sudo access
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration Variables
INSTALL_DIR="/opt/zwift-scraper"
REPO_URL="https://github.com/pablo-87/zwift-power-scraper.git"
WEBHOOK_PORT=9000
CRON_SCHEDULE="0 3 * * *"  # Daily at 3:00 AM

################################################################################
# Helper Functions
################################################################################

# Print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Error handler
error_exit() {
    print_error "$1"
    exit 1
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

################################################################################
# Pre-flight Checks
################################################################################

print_info "Starting Zwift Power Scraper server setup..."
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    error_exit "This script must be run as root. Please use: sudo ./server-setup.sh"
fi

# Check Ubuntu version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    print_info "Detected OS: $NAME $VERSION"
    if [[ ! "$ID" =~ ^(ubuntu|debian)$ ]]; then
        print_warning "This script is designed for Ubuntu/Debian. Proceed with caution."
    fi
else
    print_warning "Cannot detect OS version. Proceeding anyway..."
fi

################################################################################
# System Dependencies Installation
################################################################################

print_info "Updating package lists..."
apt-get update || error_exit "Failed to update package lists"

print_info "Installing system dependencies..."
PACKAGES=(
    "git"
    "docker.io"
    "docker-compose"
    "curl"
    "wget"
    "ca-certificates"
    "gnupg"
    "lsb-release"
)

for package in "${PACKAGES[@]}"; do
    if dpkg -l | grep -q "^ii  $package "; then
        print_success "$package is already installed"
    else
        print_info "Installing $package..."
        apt-get install -y "$package" || error_exit "Failed to install $package"
        print_success "$package installed successfully"
    fi
done

################################################################################
# Docker Configuration
################################################################################

print_info "Configuring Docker service..."

# Enable Docker service
if systemctl is-enabled docker >/dev/null 2>&1; then
    print_success "Docker service is already enabled"
else
    systemctl enable docker || error_exit "Failed to enable Docker service"
    print_success "Docker service enabled"
fi

# Start Docker service
if systemctl is-active docker >/dev/null 2>&1; then
    print_success "Docker service is already running"
else
    systemctl start docker || error_exit "Failed to start Docker service"
    print_success "Docker service started"
fi

# Verify Docker installation
docker --version || error_exit "Docker installation verification failed"
docker-compose --version || error_exit "Docker Compose installation verification failed"

################################################################################
# Project Directory Setup
################################################################################

print_info "Setting up project directory..."

# Create installation directory
if [ -d "$INSTALL_DIR" ]; then
    print_warning "Installation directory already exists: $INSTALL_DIR"
else
    mkdir -p "$INSTALL_DIR" || error_exit "Failed to create installation directory"
    print_success "Created installation directory: $INSTALL_DIR"
fi

################################################################################
# Repository Clone/Update
################################################################################

print_info "Setting up repository..."

if [ -d "$INSTALL_DIR/.git" ]; then
    print_info "Repository already exists. Pulling latest changes..."
    cd "$INSTALL_DIR" || error_exit "Failed to navigate to installation directory"
    
    # Stash any local changes
    git stash || true
    
    # Pull latest changes
    git pull origin main || error_exit "Failed to pull latest changes"
    print_success "Repository updated successfully"
else
    print_info "Cloning repository from $REPO_URL..."
    
    # Check if REPO_URL is still placeholder
    if [[ "$REPO_URL" == *"YOUR_USERNAME"* ]]; then
        print_error "Repository URL is not configured!"
        print_info "Please edit this script and replace YOUR_USERNAME with your GitHub username"
        print_info "Or clone manually: git clone <your-repo-url> $INSTALL_DIR"
        error_exit "Repository URL configuration required"
    fi
    
    git clone "$REPO_URL" "$INSTALL_DIR" || error_exit "Failed to clone repository"
    print_success "Repository cloned successfully"
fi

cd "$INSTALL_DIR" || error_exit "Failed to navigate to installation directory"

################################################################################
# Environment Configuration
################################################################################

print_info "Configuring environment..."

# Copy .env.example to .env if it doesn't exist
if [ -f "$INSTALL_DIR/.env" ]; then
    print_warning ".env file already exists. Skipping creation."
    print_info "Please ensure your .env file is properly configured"
else
    if [ -f "$INSTALL_DIR/.env.example" ]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env" || error_exit "Failed to copy .env.example"
        print_success "Created .env file from .env.example"
        print_warning "IMPORTANT: You must edit $INSTALL_DIR/.env with your credentials!"
    else
        error_exit ".env.example file not found in repository"
    fi
fi

# Set proper permissions for .env
chmod 600 "$INSTALL_DIR/.env" || error_exit "Failed to set .env permissions"
print_success "Set secure permissions on .env file (600)"

################################################################################
# Directory Structure
################################################################################

print_info "Creating required directories..."

# Create logs directory
mkdir -p "$INSTALL_DIR/logs" || error_exit "Failed to create logs directory"
chmod 755 "$INSTALL_DIR/logs"
print_success "Created logs directory"

# Create output directory
mkdir -p "$INSTALL_DIR/output" || error_exit "Failed to create output directory"
chmod 755 "$INSTALL_DIR/output"
print_success "Created output directory"

################################################################################
# Script Permissions
################################################################################

print_info "Setting script permissions..."

# Make scripts executable
if [ -f "$INSTALL_DIR/scripts/run-scraper.sh" ]; then
    chmod +x "$INSTALL_DIR/scripts/run-scraper.sh"
    print_success "Made run-scraper.sh executable"
else
    print_warning "run-scraper.sh not found"
fi

if [ -f "$INSTALL_DIR/webhook/deploy.sh" ]; then
    chmod +x "$INSTALL_DIR/webhook/deploy.sh"
    print_success "Made deploy.sh executable"
else
    print_warning "deploy.sh not found"
fi

################################################################################
# Docker Network Setup
################################################################################

print_info "Setting up Docker network..."

# Create Docker network if it doesn't exist
if docker network ls | grep -q "zwift_network"; then
    print_success "Docker network 'zwift_network' already exists"
else
    docker network create zwift_network || error_exit "Failed to create Docker network"
    print_success "Created Docker network 'zwift_network'"
fi

################################################################################
# Webhook Service Setup
################################################################################

print_info "Setting up GitHub webhook service..."

if [ -f "$INSTALL_DIR/webhook/docker-compose.webhook.yml" ]; then
    cd "$INSTALL_DIR/webhook" || error_exit "Failed to navigate to webhook directory"
    
    # Check if webhook container is already running
    if docker ps | grep -q "zwift_webhook"; then
        print_info "Webhook container is already running. Restarting..."
        docker-compose -f docker-compose.webhook.yml restart || print_warning "Failed to restart webhook"
    else
        print_info "Starting webhook container..."
        docker-compose -f docker-compose.webhook.yml up -d || print_warning "Failed to start webhook service"
    fi
    
    print_success "Webhook service configured"
    print_warning "Remember to configure webhook secret in webhook/webhook-config.json"
    print_info "Webhook will be available on port $WEBHOOK_PORT"
else
    print_warning "Webhook configuration not found. Skipping webhook setup."
fi

cd "$INSTALL_DIR" || error_exit "Failed to return to installation directory"

################################################################################
# Cron Job Setup
################################################################################

print_info "Setting up cron job for automated execution..."

CRON_COMMAND="$CRON_SCHEDULE $INSTALL_DIR/scripts/run-scraper.sh >> $INSTALL_DIR/logs/cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "run-scraper.sh"; then
    print_warning "Cron job already exists. Skipping cron setup."
    print_info "Current cron jobs:"
    crontab -l | grep "run-scraper.sh" || true
else
    # Add cron job
    (crontab -l 2>/dev/null; echo "# Zwift Power Scraper - Daily execution at 3:00 AM"; echo "$CRON_COMMAND") | crontab - || error_exit "Failed to add cron job"
    print_success "Cron job added successfully"
    print_info "Schedule: Daily at 3:00 AM (server time)"
fi

################################################################################
# Main Application Startup
################################################################################

print_info "Starting main application containers..."

cd "$INSTALL_DIR" || error_exit "Failed to navigate to installation directory"

# Build and start containers
print_info "Building Docker images (this may take a few minutes)..."
docker-compose build || error_exit "Failed to build Docker images"

print_info "Starting containers..."
docker-compose up -d || error_exit "Failed to start containers"

# Wait for containers to initialize
print_info "Waiting for containers to initialize..."
sleep 10

# Check container status
print_info "Verifying container status..."
docker-compose ps

################################################################################
# Firewall Configuration (Optional)
################################################################################

print_info "Checking firewall configuration..."

if command_exists ufw; then
    if ufw status | grep -q "Status: active"; then
        print_info "UFW firewall is active"
        
        # Allow webhook port
        if ufw status | grep -q "$WEBHOOK_PORT"; then
            print_success "Port $WEBHOOK_PORT is already allowed"
        else
            print_warning "Port $WEBHOOK_PORT is not allowed in firewall"
            print_info "To allow webhook access, run: sudo ufw allow $WEBHOOK_PORT/tcp"
        fi
    else
        print_info "UFW firewall is not active"
    fi
else
    print_info "UFW firewall not installed"
fi

################################################################################
# Setup Complete
################################################################################

echo ""
echo "========================================================================"
print_success "Zwift Power Scraper setup completed successfully!"
echo "========================================================================"
echo ""
print_info "Installation directory: $INSTALL_DIR"
print_info "Webhook endpoint: http://YOUR_SERVER_IP:$WEBHOOK_PORT/hooks/zwift-scraper-deploy"
print_info "Cron schedule: Daily at 3:00 AM"
echo ""
print_warning "IMPORTANT NEXT STEPS:"
echo ""
echo "1. Configure your credentials in the .env file:"
echo "   sudo nano $INSTALL_DIR/.env"
echo ""
echo "2. Update the webhook secret in webhook configuration:"
echo "   sudo nano $INSTALL_DIR/webhook/webhook-config.json"
echo ""
echo "3. Configure GitHub webhook in your repository:"
echo "   - URL: http://YOUR_SERVER_IP:$WEBHOOK_PORT/hooks/zwift-scraper-deploy"
echo "   - Content type: application/json"
echo "   - Secret: (use the same secret from webhook-config.json)"
echo "   - Events: Just the push event"
echo ""
echo "4. Test the scraper manually:"
echo "   cd $INSTALL_DIR"
echo "   docker-compose exec scraper python main.py"
echo ""
echo "5. View logs:"
echo "   - Application logs: $INSTALL_DIR/logs/"
echo "   - Cron logs: $INSTALL_DIR/logs/cron.log"
echo "   - Deployment logs: $INSTALL_DIR/logs/deployment.log"
echo ""
echo "6. Manage containers:"
echo "   - View status: docker-compose ps"
echo "   - View logs: docker-compose logs -f"
echo "   - Restart: docker-compose restart"
echo "   - Stop: docker-compose down"
echo ""
print_info "For detailed documentation, see: $INSTALL_DIR/docs/DEPLOYMENT.md"
echo ""
echo "========================================================================"

exit 0
