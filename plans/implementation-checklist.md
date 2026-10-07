# Implementation Checklist - CasaOS Deployment

## 📋 Files to Create/Update

### Docker Configuration Files

#### ✅ Update: `Dockerfile`
**Current issues:**
- References old file structure (`scraper.py`, `cookie_refresher.py`, `database.py`)
- Missing new directory structure (core/, database/, scripts/)
- Healthcheck imports wrong modules

**Changes needed:**
```dockerfile
# Update COPY commands to:
COPY --chown=scraper:scraper main.py .
COPY --chown=scraper:scraper core/ ./core/
COPY --chown=scraper:scraper database/ ./database/
COPY --chown=scraper:scraper scripts/ ./scripts/
COPY --chown=scraper:scraper zids.txt .

# Update healthcheck to:
HEALTHCHECK CMD python -c "from core.client import ZwiftPowerClient; from database.engine import engine" || exit 1

# Add logs directory:
RUN mkdir -p /app/logs && chown -R scraper:scraper /app/logs
```

#### ✅ Update: `docker-compose.yml`
**Current issues:**
- References old command structure
- Missing logs volume mount
- Missing CasaOS labels
- Configured for one-time execution instead of cron-triggered

**Changes needed:**
```yaml
# Update scraper service:
scraper:
  build:
    context: .
    dockerfile: Dockerfile
  container_name: zwift_scraper
  restart: unless-stopped
  command: tail -f /dev/null  # Keep container running for cron exec
  volumes:
    - ./.env:/app/.env
    - ./logs:/app/logs
    - ./zids.txt:/app/zids.txt:ro
  labels:
    # CasaOS integration
    icon: https://zwiftpower.com/favicon.ico
    description: Zwift Power Racing Data Scraper
    
# Update postgres volumes to ensure persistence
volumes:
  postgres_data:
    driver: local
    name: zwift_postgres_data  # Named volume for easier backup
```

#### ✅ Update: `.dockerignore`
**Add:**
```
logs/
*.log
.git/
.github/
tests/
docs/
plans/
__pycache__/
*.pyc
.pytest_cache/
```

---

### Webhook Auto-Deployment System

#### ✅ Create: `webhook/docker-compose.webhook.yml`
**Purpose:** Separate webhook listener service

```yaml
version: '3.8'

services:
  webhook:
    image: almir/webhook:latest
    container_name: zwift_webhook
    restart: unless-stopped
    ports:
      - "9000:9000"
    volumes:
      - ./webhook-config.json:/etc/webhook/hooks.json:ro
      - ./deploy.sh:/scripts/deploy.sh:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /opt/zwift-scraper:/opt/zwift-scraper
    command: -verbose -hooks=/etc/webhook/hooks.json -hotreload
    networks:
      - zwift_network

networks:
  zwift_network:
    external: true
```

#### ✅ Create: `webhook/webhook-config.json`
**Purpose:** Webhook configuration with GitHub signature verification

```json
[
  {
    "id": "zwift-scraper-deploy",
    "execute-command": "/scripts/deploy.sh",
    "command-working-directory": "/opt/zwift-scraper",
    "response-message": "Deployment triggered",
    "trigger-rule": {
      "and": [
        {
          "match": {
            "type": "payload-hmac-sha256",
            "secret": "YOUR_WEBHOOK_SECRET_HERE",
            "parameter": {
              "source": "header",
              "name": "X-Hub-Signature-256"
            }
          }
        },
        {
          "match": {
            "type": "value",
            "value": "refs/heads/main",
            "parameter": {
              "source": "payload",
              "name": "ref"
            }
          }
        }
      ]
    }
  }
]
```

#### ✅ Create: `webhook/deploy.sh`
**Purpose:** Deployment script triggered by webhook

```bash
#!/bin/bash
set -e

# Configuration
PROJECT_DIR="/opt/zwift-scraper"
LOG_FILE="$PROJECT_DIR/logs/deployment.log"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Deployment Started ==="

# Navigate to project directory
cd "$PROJECT_DIR" || exit 1

# Pull latest changes
log "Pulling latest code from GitHub..."
git pull origin main 2>&1 | tee -a "$LOG_FILE"

# Check if Dockerfile or requirements changed
if git diff HEAD@{1} --name-only | grep -qE 'Dockerfile|requirements.txt'; then
    log "Dependencies changed, rebuilding images..."
    docker-compose -f "$COMPOSE_FILE" build --no-cache scraper 2>&1 | tee -a "$LOG_FILE"
else
    log "No dependency changes, using existing image..."
fi

# Restart scraper container (database stays running)
log "Restarting scraper container..."
docker-compose -f "$COMPOSE_FILE" up -d scraper 2>&1 | tee -a "$LOG_FILE"

# Verify containers are running
if docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
    log "=== Deployment Successful ==="
else
    log "ERROR: Containers failed to start"
    exit 1
fi

log "Container status:"
docker-compose -f "$COMPOSE_FILE" ps 2>&1 | tee -a "$LOG_FILE"
```

---

### Cron Configuration

#### ✅ Create: `scripts/run-scraper.sh`
**Purpose:** Wrapper script for cron execution

```bash
#!/bin/bash
set -e

# Configuration
PROJECT_DIR="/opt/zwift-scraper"
LOG_FILE="$PROJECT_DIR/logs/cron.log"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Cron Job Started ==="

# Navigate to project directory
cd "$PROJECT_DIR" || exit 1

# Check if containers are running
if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
    log "ERROR: Containers are not running. Starting them..."
    docker-compose -f "$COMPOSE_FILE" up -d
    sleep 10
fi

# Execute scraper
log "Executing scraper..."
if docker-compose -f "$COMPOSE_FILE" exec -T scraper python main.py 2>&1 | tee -a "$LOG_FILE"; then
    log "=== Scraper Execution Successful ==="
else
    log "ERROR: Scraper execution failed"
    exit 1
fi

# Optional: Cleanup old logs (keep last 30 days)
find "$PROJECT_DIR/logs" -name "*.log" -type f -mtime +30 -delete 2>/dev/null || true

log "=== Cron Job Completed ==="
```

#### ✅ Create: `cron/zwift-scraper.cron`
**Purpose:** Crontab entry for 3 AM execution

```bash
# Zwift Power Scraper - Daily execution at 3:00 AM
# Logs are written to /opt/zwift-scraper/logs/cron.log

0 3 * * * /opt/zwift-scraper/scripts/run-scraper.sh >> /opt/zwift-scraper/logs/cron.log 2>&1
```

---

### Server Setup

#### ✅ Create: `server-setup.sh`
**Purpose:** Automated server initialization script

```bash
#!/bin/bash
set -e

echo "=== Zwift Power Scraper - Server Setup ==="
echo ""

# Configuration
INSTALL_DIR="/opt/zwift-scraper"
REPO_URL="https://github.com/YOUR_USERNAME/zwift-power-scraper.git"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Install dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y git docker.io docker-compose curl

# Enable Docker service
systemctl enable docker
systemctl start docker

# Create project directory
echo "Setting up project directory..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Clone repository
echo "Cloning repository..."
if [ -d ".git" ]; then
    echo "Repository already exists, pulling latest..."
    git pull origin main
else
    git clone "$REPO_URL" .
fi

# Setup environment file
echo "Setting up environment file..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "IMPORTANT: Edit .env file with your credentials"
    echo "Location: $INSTALL_DIR/.env"
else
    echo ".env file already exists, skipping..."
fi

# Create logs directory
mkdir -p logs
chmod 755 logs

# Make scripts executable
chmod +x scripts/run-scraper.sh
chmod +x webhook/deploy.sh

# Setup webhook service
echo "Setting up webhook listener..."
cd webhook
docker-compose -f docker-compose.webhook.yml up -d
cd ..

# Setup cron job
echo "Setting up cron job..."
CRON_ENTRY="0 3 * * * $INSTALL_DIR/scripts/run-scraper.sh >> $INSTALL_DIR/logs/cron.log 2>&1"
(crontab -l 2>/dev/null | grep -v "run-scraper.sh"; echo "$CRON_ENTRY") | crontab -

# Start Docker containers
echo "Starting Docker containers..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Check status
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Container Status:"
docker-compose ps
echo ""
echo "Next Steps:"
echo "1. Edit .env file: nano $INSTALL_DIR/.env"
echo "2. Add your ZwiftPower cookies and database credentials"
echo "3. Configure GitHub webhook:"
echo "   - URL: http://YOUR_SERVER_IP:9000/hooks/zwift-scraper-deploy"
echo "   - Content type: application/json"
echo "   - Secret: (generate a secure token)"
echo "4. Update webhook/webhook-config.json with your secret"
echo "5. Restart webhook service: cd webhook && docker-compose restart"
echo ""
echo "Logs location: $INSTALL_DIR/logs/"
echo "Manual run: docker-compose exec scraper python main.py"
```

---

### Documentation

#### ✅ Create: `docs/DEPLOYMENT.md`
**Purpose:** Complete deployment guide

**Sections:**
1. Prerequisites
2. Initial Server Setup
3. GitHub Webhook Configuration
4. CasaOS Integration
5. Monitoring & Maintenance
6. Troubleshooting
7. Backup & Recovery

---

## 🔄 Implementation Order

1. **Update Docker files** (Dockerfile, docker-compose.yml, .dockerignore)
2. **Create webhook system** (webhook-config.json, deploy.sh, docker-compose.webhook.yml)
3. **Create cron scripts** (run-scraper.sh, zwift-scraper.cron)
4. **Create setup script** (server-setup.sh)
5. **Create documentation** (DEPLOYMENT.md)
6. **Test locally** before server deployment

---

## ✅ Validation Checklist

Before deploying to server:

- [ ] Dockerfile builds successfully
- [ ] docker-compose.yml starts all services
- [ ] Webhook listener responds to test POST
- [ ] Deploy script executes without errors
- [ ] Cron script can execute scraper
- [ ] Logs are written to correct locations
- [ ] Database persists across container restarts
- [ ] .env.example is up to date
- [ ] All scripts have execute permissions
- [ ] Documentation is complete and accurate

---

## 🚀 Ready to Implement

This checklist provides the complete roadmap for implementing the CasaOS deployment. Each file is specified with its purpose and content structure.

**Estimated Implementation Time:** 2-3 hours for all components

**Next Step:** Switch to Code mode to create/update all files
