# Deployment Guide - Ubuntu Server with CasaOS

Complete guide for deploying the Zwift Power Scraper on Ubuntu Server with CasaOS integration.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Manual Installation](#manual-installation)
- [GitHub Webhook Configuration](#github-webhook-configuration)
- [CasaOS Integration](#casaos-integration)
- [Cron Job Verification](#cron-job-verification)
- [Environment Variables](#environment-variables)
- [Monitoring & Logs](#monitoring--logs)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)
- [Updating the Application](#updating-the-application)

---

## Prerequisites

Before deploying the Zwift Power Scraper, ensure your server meets the following requirements:

### System Requirements

- **Operating System**: Ubuntu Server 20.04 LTS or later (also compatible with Debian-based distributions)
- **RAM**: Minimum 2GB (4GB recommended)
- **Storage**: At least 10GB free space
- **Network**: Internet connection with access to GitHub and ZwiftPower
- **User Access**: Root or sudo privileges

### Required Software

The following software will be installed automatically by the setup script:

- **Docker**: Version 20.10 or later
- **Docker Compose**: Version 1.29 or later
- **Git**: For repository management
- **Curl/Wget**: For downloading dependencies

### ZwiftPower Account

- Active ZwiftPower account with valid credentials
- Browser access to obtain authentication cookies

---

## Quick Start

The fastest way to deploy the application is using the automated setup script.

### 1. Clone the Repository

```bash
cd /opt
sudo git clone https://github.com/YOUR_USERNAME/zwift-power-scraper.git zwift-scraper
cd zwift-scraper
```

### 2. Run the Setup Script

```bash
sudo chmod +x server-setup.sh
sudo ./server-setup.sh
```

The script will:
- Install all system dependencies
- Configure Docker and Docker Compose
- Set up the project directory structure
- Create necessary configuration files
- Configure the webhook service
- Set up the cron job for automated execution
- Start all Docker containers

### 3. Configure Environment Variables

After the setup script completes, edit the `.env` file with your credentials:

```bash
sudo nano /opt/zwift-scraper/.env
```

**Required configurations:**

```bash
# Database Configuration
DB_NAME=zwift_racing
DB_USER=zwift_user
DB_PASS=your_secure_password_here  # CHANGE THIS!

# ZwiftPower Authentication Cookies
PHPBB3_SID=your_phpbb_session_id_here
PHPBB3_U=your_phpbb_user_id_here
CLOUDFRONT_KEY_PAIR_ID=your_cloudfront_key_pair_id_here
CLOUDFRONT_POLICY=your_cloudfront_policy_here
CLOUDFRONT_SIGNATURE=your_cloudfront_signature_here

# Zwift Account Credentials
ZWIFT_USER=your_zwift_email@example.com
ZWIFT_PASS=your_zwift_password_here
```

**How to obtain ZwiftPower cookies:**

1. Open your browser and log into [ZwiftPower](https://zwiftpower.com)
2. Open Developer Tools (F12)
3. Go to the "Application" or "Storage" tab
4. Navigate to "Cookies" → "https://zwiftpower.com"
5. Copy the values for the required cookies

### 4. Restart Containers

After configuring the `.env` file:

```bash
cd /opt/zwift-scraper
sudo docker-compose restart
```

### 5. Test the Installation

Run the scraper manually to verify everything works:

```bash
sudo docker-compose exec scraper python main.py
```

Check the logs for any errors:

```bash
tail -f /opt/zwift-scraper/logs/scraper.log
```

---

## Manual Installation

If you prefer to install manually or the automated script fails, follow these steps.

### Step 1: Install System Dependencies

```bash
# Update package lists
sudo apt-get update

# Install required packages
sudo apt-get install -y git docker.io docker-compose curl wget ca-certificates

# Enable and start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Verify installation
docker --version
docker-compose --version
```

### Step 2: Create Project Directory

```bash
# Create installation directory
sudo mkdir -p /opt/zwift-scraper
cd /opt/zwift-scraper

# Clone repository
sudo git clone https://github.com/YOUR_USERNAME/zwift-power-scraper.git .
```

### Step 3: Configure Environment

```bash
# Copy environment template
sudo cp .env.example .env

# Set secure permissions
sudo chmod 600 .env

# Edit with your credentials
sudo nano .env
```

### Step 4: Create Required Directories

```bash
# Create logs and output directories
sudo mkdir -p /opt/zwift-scraper/logs
sudo mkdir -p /opt/zwift-scraper/output

# Set permissions
sudo chmod 755 /opt/zwift-scraper/logs
sudo chmod 755 /opt/zwift-scraper/output
```

### Step 5: Make Scripts Executable

```bash
sudo chmod +x /opt/zwift-scraper/scripts/run-scraper.sh
sudo chmod +x /opt/zwift-scraper/webhook/deploy.sh
```

### Step 6: Create Docker Network

```bash
sudo docker network create zwift_network
```

### Step 7: Build and Start Containers

```bash
cd /opt/zwift-scraper

# Build Docker images
sudo docker-compose build

# Start containers
sudo docker-compose up -d

# Verify containers are running
sudo docker-compose ps
```

### Step 8: Setup Webhook Service

```bash
cd /opt/zwift-scraper/webhook

# Configure webhook secret (edit the file)
sudo nano webhook-config.json

# Start webhook service
sudo docker-compose -f docker-compose.webhook.yml up -d
```

### Step 9: Configure Cron Job

```bash
# Edit crontab
sudo crontab -e

# Add the following line (runs daily at 3:00 AM)
0 3 * * * /opt/zwift-scraper/scripts/run-scraper.sh >> /opt/zwift-scraper/logs/cron.log 2>&1
```

---

## GitHub Webhook Configuration

The webhook enables automatic deployment when you push changes to your GitHub repository.

### Step 1: Configure Webhook Secret

Generate a secure secret:

```bash
# Generate a random secret
openssl rand -hex 32
```

Edit the webhook configuration:

```bash
sudo nano /opt/zwift-scraper/webhook/webhook-config.json
```

Replace `CHANGE_THIS_SECRET` with your generated secret:

```json
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
          "secret": "your_generated_secret_here",
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
```

Restart the webhook service:

```bash
cd /opt/zwift-scraper/webhook
sudo docker-compose -f docker-compose.webhook.yml restart
```

### Step 2: Configure GitHub Repository

1. Go to your GitHub repository
2. Navigate to **Settings** → **Webhooks** → **Add webhook**
3. Configure the webhook:

   - **Payload URL**: `http://YOUR_SERVER_IP:9000/hooks/zwift-scraper-deploy`
   - **Content type**: `application/json`
   - **Secret**: (paste the secret from webhook-config.json)
   - **SSL verification**: Enable if using HTTPS
   - **Which events**: Select "Just the push event"
   - **Active**: Check this box

4. Click **Add webhook**

### Step 3: Test the Webhook

Make a small change to your repository and push:

```bash
git commit --allow-empty -m "Test webhook"
git push origin main
```

Check the deployment logs:

```bash
tail -f /opt/zwift-scraper/logs/deployment.log
```

### Step 4: Verify Webhook Deliveries

In GitHub:
1. Go to **Settings** → **Webhooks**
2. Click on your webhook
3. Check the **Recent Deliveries** tab
4. Verify the response is `200 OK`

---

## CasaOS Integration

CasaOS provides a user-friendly interface for managing Docker containers.

### Viewing Containers in CasaOS

1. Open CasaOS web interface (usually `http://YOUR_SERVER_IP:80`)
2. Navigate to the **Docker** or **Apps** section
3. You should see the following containers:
   - `zwift_scraper` - Main application
   - `zwift_postgres` - PostgreSQL database
   - `zwift_webhook` - GitHub webhook listener
   - `zwift_pgadmin` - Database management UI (optional)

### Managing Containers via CasaOS

**Start/Stop Containers:**
- Click on the container
- Use the Start/Stop buttons

**View Logs:**
- Click on the container
- Select "Logs" tab
- View real-time logs

**Container Statistics:**
- CPU usage
- Memory usage
- Network I/O
- Storage usage

### Custom Labels for CasaOS

The containers are configured with custom labels for better CasaOS integration:

```yaml
labels:
  icon: "https://zwiftpower.com/favicon.ico"
  description: "Zwift Power Racing Data Scraper"
  name: "Zwift Scraper"
```

### Accessing Services via CasaOS

**pgAdmin (Database Management):**
- URL: `http://YOUR_SERVER_IP:5050`
- Default credentials (change in `.env`):
  - Email: `admin@zwift.local`
  - Password: `admin`

**Note**: pgAdmin is in the `tools` profile and must be started explicitly:

```bash
cd /opt/zwift-scraper
sudo docker-compose --profile tools up -d pgadmin
```

---

## Cron Job Verification

The cron job executes the scraper automatically on a daily schedule.

### Check Cron Configuration

View the current crontab:

```bash
sudo crontab -l
```

You should see:

```bash
# Zwift Power Scraper - Daily execution at 3:00 AM
0 3 * * * /opt/zwift-scraper/scripts/run-scraper.sh >> /opt/zwift-scraper/logs/cron.log 2>&1
```

### Cron Schedule Explanation

- `0 3 * * *` - Runs at 3:00 AM every day
- `*` fields: minute, hour, day of month, month, day of week

**Common schedules:**

```bash
# Every 6 hours
0 */6 * * * /opt/zwift-scraper/scripts/run-scraper.sh

# Twice daily (6 AM and 6 PM)
0 6,18 * * * /opt/zwift-scraper/scripts/run-scraper.sh

# Every Monday at 2 AM
0 2 * * 1 /opt/zwift-scraper/scripts/run-scraper.sh
```

### Test Cron Execution

Run the script manually to test:

```bash
sudo /opt/zwift-scraper/scripts/run-scraper.sh
```

Check the cron log:

```bash
tail -f /opt/zwift-scraper/logs/cron.log
```

### Modify Cron Schedule

Edit the crontab:

```bash
sudo crontab -e
```

Change the schedule and save.

### Disable Cron Job

Comment out the line in crontab:

```bash
sudo crontab -e

# Add # at the beginning of the line:
# 0 3 * * * /opt/zwift-scraper/scripts/run-scraper.sh >> /opt/zwift-scraper/logs/cron.log 2>&1
```

---

## Environment Variables

Complete reference of all environment variables used by the application.

### Database Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DB_NAME` | PostgreSQL database name | `zwift_racing` | Yes |
| `DB_USER` | Database username | `zwift_user` | Yes |
| `DB_PASS` | Database password | `changeme` | Yes |
| `DB_HOST` | Database host (use `postgres` for Docker) | `postgres` | Yes |
| `DB_PORT` | Database port | `5432` | Yes |

### ZwiftPower Authentication

| Variable | Description | Required |
|----------|-------------|----------|
| `PHPBB3_SID` | phpBB session ID cookie | Yes |
| `PHPBB3_U` | phpBB user ID cookie | Yes |
| `CLOUDFRONT_KEY_PAIR_ID` | CloudFront key pair ID | Yes |
| `CLOUDFRONT_POLICY` | CloudFront policy | Yes |
| `CLOUDFRONT_SIGNATURE` | CloudFront signature | Yes |

**Note**: These cookies are automatically refreshed by the [`cookie_refresher.py`](../scripts/cookie_refresher.py) script.

### Zwift Account Credentials

| Variable | Description | Required |
|----------|-------------|----------|
| `ZWIFT_USER` | Zwift account email | Yes |
| `ZWIFT_PASS` | Zwift account password | Yes |

**Security Note**: These credentials are used only for automatic cookie refresh and are never transmitted outside the container.

### pgAdmin Configuration (Optional)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PGADMIN_EMAIL` | pgAdmin login email | `admin@zwift.local` | No |
| `PGADMIN_PASSWORD` | pgAdmin login password | `admin` | No |
| `PGADMIN_PORT` | pgAdmin web interface port | `5050` | No |

### Example .env File

```bash
# Database Configuration
DB_NAME=zwift_racing
DB_USER=zwift_user
DB_PASS=MySecurePassword123!
DB_HOST=postgres
DB_PORT=5432

# ZwiftPower Authentication Cookies
PHPBB3_SID=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
PHPBB3_U=123456
CLOUDFRONT_KEY_PAIR_ID=APKAXXXXXXXXXXXXXXXXX
CLOUDFRONT_POLICY=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly8qLmNsb3VkZnJvbnQubmV0LyoiLCJDb25kaXRpb24iOnsiRGF0ZUxlc3NUaGFuIjp7IkFXUzpFcG9jaFRpbWUiOjE3MDAwMDAwMDB9fX1dfQ__
CLOUDFRONT_SIGNATURE=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_~

# Zwift Account Credentials
ZWIFT_USER=myemail@example.com
ZWIFT_PASS=MyZwiftPassword123!

# Optional: pgAdmin Configuration
PGADMIN_EMAIL=admin@zwift.local
PGADMIN_PASSWORD=SecureAdminPassword123!
PGADMIN_PORT=5050
```

---

## Monitoring & Logs

Comprehensive logging is implemented throughout the application.

### Log Locations

| Log File | Description | Location |
|----------|-------------|----------|
| Application logs | Main scraper execution logs | `/opt/zwift-scraper/logs/scraper.log` |
| Cron logs | Automated execution logs | `/opt/zwift-scraper/logs/cron.log` |
| Deployment logs | Webhook deployment logs | `/opt/zwift-scraper/logs/deployment.log` |
| Docker logs | Container stdout/stderr | `docker-compose logs` |

### Viewing Logs

**Application logs:**

```bash
# View latest logs
tail -f /opt/zwift-scraper/logs/scraper.log

# View last 100 lines
tail -n 100 /opt/zwift-scraper/logs/scraper.log

# Search for errors
grep -i error /opt/zwift-scraper/logs/scraper.log
```

**Cron logs:**

```bash
# View cron execution logs
tail -f /opt/zwift-scraper/logs/cron.log

# View today's cron executions
grep "$(date +%Y-%m-%d)" /opt/zwift-scraper/logs/cron.log
```

**Deployment logs:**

```bash
# View webhook deployment logs
tail -f /opt/zwift-scraper/logs/deployment.log

# View last deployment
tail -n 50 /opt/zwift-scraper/logs/deployment.log
```

**Docker container logs:**

```bash
cd /opt/zwift-scraper

# View all container logs
sudo docker-compose logs

# Follow logs in real-time
sudo docker-compose logs -f

# View specific container logs
sudo docker-compose logs scraper
sudo docker-compose logs postgres

# View last 50 lines
sudo docker-compose logs --tail=50 scraper
```

### Log Rotation

Automatic log cleanup is implemented in [`run-scraper.sh`](../scripts/run-scraper.sh):

- Logs older than 30 days are automatically deleted
- Runs during each cron execution
- Prevents disk space issues

**Manual log cleanup:**

```bash
# Remove logs older than 30 days
find /opt/zwift-scraper/logs -name "*.log" -type f -mtime +30 -delete

# Remove all logs (use with caution)
sudo rm -f /opt/zwift-scraper/logs/*.log
```

### Monitoring Container Health

**Check container status:**

```bash
cd /opt/zwift-scraper
sudo docker-compose ps
```

**Check container resource usage:**

```bash
sudo docker stats
```

**Check PostgreSQL health:**

```bash
sudo docker-compose exec postgres pg_isready -U zwift_user -d zwift_racing
```

### Database Monitoring

**Connect to PostgreSQL:**

```bash
sudo docker-compose exec postgres psql -U zwift_user -d zwift_racing
```

**Check database size:**

```sql
SELECT pg_size_pretty(pg_database_size('zwift_racing'));
```

**Check table sizes:**

```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Check recent data:**

```sql
SELECT COUNT(*), MAX(created_at) as last_update 
FROM race_results;
```

---

## Maintenance

Regular maintenance tasks to keep the system running smoothly.

### Manual Scraper Execution

Run the scraper manually outside of the cron schedule:

```bash
cd /opt/zwift-scraper

# Execute scraper
sudo docker-compose exec scraper python main.py

# Execute with verbose output
sudo docker-compose exec scraper python main.py --verbose
```

### Database Backup

**Create a backup:**

```bash
# Create backup directory
sudo mkdir -p /opt/zwift-scraper/backups

# Backup database
sudo docker-compose exec -T postgres pg_dump -U zwift_user zwift_racing > /opt/zwift-scraper/backups/backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
sudo docker-compose exec -T postgres pg_dump -U zwift_user zwift_racing | gzip > /opt/zwift-scraper/backups/backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

**Restore from backup:**

```bash
# Restore from SQL file
sudo docker-compose exec -T postgres psql -U zwift_user zwift_racing < /opt/zwift-scraper/backups/backup_20260101_030000.sql

# Restore from compressed file
gunzip -c /opt/zwift-scraper/backups/backup_20260101_030000.sql.gz | sudo docker-compose exec -T postgres psql -U zwift_user zwift_racing
```

**Automated backup script:**

Create `/opt/zwift-scraper/scripts/backup-db.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/zwift-scraper/backups"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# Create backup
docker-compose -f /opt/zwift-scraper/docker-compose.yml exec -T postgres \
    pg_dump -U zwift_user zwift_racing | \
    gzip > "$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql.gz"

# Remove old backups
find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $(date)"
```

Add to crontab for daily backups:

```bash
0 2 * * * /opt/zwift-scraper/scripts/backup-db.sh >> /opt/zwift-scraper/logs/backup.log 2>&1
```

### Container Restart

**Restart all containers:**

```bash
cd /opt/zwift-scraper
sudo docker-compose restart
```

**Restart specific container:**

```bash
sudo docker-compose restart scraper
sudo docker-compose restart postgres
```

**Full rebuild and restart:**

```bash
cd /opt/zwift-scraper
sudo docker-compose down
sudo docker-compose build --no-cache
sudo docker-compose up -d
```

### Update Dependencies

**Update Python packages:**

Edit [`requirements.txt`](../requirements.txt), then:

```bash
cd /opt/zwift-scraper
sudo docker-compose build scraper
sudo docker-compose up -d scraper
```

**Update Docker images:**

```bash
cd /opt/zwift-scraper

# Pull latest base images
sudo docker-compose pull

# Rebuild containers
sudo docker-compose build

# Restart with new images
sudo docker-compose up -d
```

### Clean Up Docker Resources

**Remove unused images:**

```bash
sudo docker image prune -a
```

**Remove unused volumes:**

```bash
sudo docker volume prune
```

**Remove unused networks:**

```bash
sudo docker network prune
```

**Complete cleanup (use with caution):**

```bash
sudo docker system prune -a --volumes
```

### Cookie Refresh

Cookies are automatically refreshed by the application. To manually refresh:

```bash
cd /opt/zwift-scraper
sudo docker-compose exec scraper python scripts/cookie_refresher.py
```

---

## Troubleshooting

Common issues and their solutions.

### Issue: Containers Won't Start

**Symptoms:**
- `docker-compose up` fails
- Containers exit immediately

**Solutions:**

1. Check Docker service:
   ```bash
   sudo systemctl status docker
   sudo systemctl start docker
   ```

2. Check logs:
   ```bash
   sudo docker-compose logs
   ```

3. Verify `.env` file exists and is readable:
   ```bash
   ls -la /opt/zwift-scraper/.env
   ```

4. Check for port conflicts:
   ```bash
   sudo netstat -tulpn | grep -E '5432|5050|9000'
   ```

5. Remove and recreate containers:
   ```bash
   sudo docker-compose down
   sudo docker-compose up -d
   ```

### Issue: Database Connection Failed

**Symptoms:**
- "Connection refused" errors
- "Could not connect to database" messages

**Solutions:**

1. Verify PostgreSQL container is running:
   ```bash
   sudo docker-compose ps postgres
   ```

2. Check database credentials in `.env`:
   ```bash
   grep DB_ /opt/zwift-scraper/.env
   ```

3. Test database connection:
   ```bash
   sudo docker-compose exec postgres psql -U zwift_user -d zwift_racing -c "SELECT 1;"
   ```

4. Check PostgreSQL logs:
   ```bash
   sudo docker-compose logs postgres
   ```

5. Restart PostgreSQL container:
   ```bash
   sudo docker-compose restart postgres
   ```

### Issue: Authentication Failed (ZwiftPower)

**Symptoms:**
- "401 Unauthorized" errors
- "Invalid cookies" messages
- Empty data returned

**Solutions:**

1. Refresh cookies manually:
   - Log into ZwiftPower in your browser
   - Extract new cookies (see [Quick Start](#quick-start))
   - Update `.env` file
   - Restart containers

2. Use automatic cookie refresh:
   ```bash
   sudo docker-compose exec scraper python scripts/cookie_refresher.py
   ```

3. Verify Zwift credentials in `.env`:
   ```bash
   grep ZWIFT_ /opt/zwift-scraper/.env
   ```

4. Check if ZwiftPower is accessible:
   ```bash
   curl -I https://zwiftpower.com
   ```

### Issue: Cron Job Not Running

**Symptoms:**
- No new data in database
- Empty cron logs
- Scraper not executing automatically

**Solutions:**

1. Verify cron job exists:
   ```bash
   sudo crontab -l | grep zwift
   ```

2. Check cron service:
   ```bash
   sudo systemctl status cron
   ```

3. Test script manually:
   ```bash
   sudo /opt/zwift-scraper/scripts/run-scraper.sh
   ```

4. Check script permissions:
   ```bash
   ls -la /opt/zwift-scraper/scripts/run-scraper.sh
   ```

5. View cron logs:
   ```bash
   tail -f /opt/zwift-scraper/logs/cron.log
   ```

6. Check system cron logs:
   ```bash
   sudo grep CRON /var/log/syslog
   ```

### Issue: Webhook Not Triggering

**Symptoms:**
- GitHub shows webhook delivery failed
- No deployment logs
- Changes not deployed automatically

**Solutions:**

1. Verify webhook container is running:
   ```bash
   sudo docker ps | grep zwift_webhook
   ```

2. Check webhook logs:
   ```bash
   cd /opt/zwift-scraper/webhook
   sudo docker-compose -f docker-compose.webhook.yml logs
   ```

3. Test webhook endpoint:
   ```bash
   curl http://localhost:9000/hooks/zwift-scraper-deploy
   ```

4. Verify webhook secret matches:
   - Check `webhook/webhook-config.json`
   - Check GitHub webhook configuration

5. Check firewall:
   ```bash
   sudo ufw status
   sudo ufw allow 9000/tcp
   ```

6. Restart webhook service:
   ```bash
   cd /opt/zwift-scraper/webhook
   sudo docker-compose -f docker-compose.webhook.yml restart
   ```

### Issue: Out of Disk Space

**Symptoms:**
- "No space left on device" errors
- Containers failing to start
- Database write errors

**Solutions:**

1. Check disk usage:
   ```bash
   df -h
   ```

2. Clean up old logs:
   ```bash
   find /opt/zwift-scraper/logs -name "*.log" -mtime +7 -delete
   ```

3. Clean up Docker resources:
   ```bash
   sudo docker system prune -a --volumes
   ```

4. Check database size:
   ```bash
   sudo docker-compose exec postgres psql -U zwift_user -d zwift_racing -c "SELECT pg_size_pretty(pg_database_size('zwift_racing'));"
   ```

5. Archive old data:
   ```bash
   # Backup and remove old data
   sudo docker-compose exec -T postgres pg_dump -U zwift_user zwift_racing > backup.sql
   # Then delete old records from database
   ```

### Issue: High Memory Usage

**Symptoms:**
- System slowdown
- OOM (Out of Memory) errors
- Containers being killed

**Solutions:**

1. Check memory usage:
   ```bash
   free -h
   sudo docker stats
   ```

2. Restart containers:
   ```bash
   sudo docker-compose restart
   ```

3. Limit container memory:
   
   Edit `docker-compose.yml` and add:
   ```yaml
   services:
     scraper:
       mem_limit: 1g
       mem_reservation: 512m
   ```

4. Check for memory leaks in logs:
   ```bash
   sudo docker-compose logs scraper | grep -i memory
   ```

### Getting Help

If you encounter issues not covered here:

1. Check application logs for detailed error messages
2. Review the [main README](../README.md) for additional documentation
3. Check the [test documentation](./README_TESTS.md) for testing procedures
4. Open an issue on GitHub with:
   - Error messages from logs
   - Steps to reproduce
   - System information (`uname -a`, `docker --version`)
   - Container status (`docker-compose ps`)

---

## Security Considerations

Important security practices for production deployment.

### 1. Environment File Security

**Protect the `.env` file:**

```bash
# Set restrictive permissions
sudo chmod 600 /opt/zwift-scraper/.env

# Verify ownership
sudo chown root:root /opt/zwift-scraper/.env

# Verify it's not in git
grep .env /opt/zwift-scraper/.gitignore
```

**Never commit `.env` to version control:**

```bash
# Ensure .env is in .gitignore
echo ".env" >> .gitignore
```

### 2. Webhook Secret

**Use a strong webhook secret:**

```bash
# Generate a secure random secret
openssl rand -hex 32

# Or use:
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Update webhook configuration:**

```bash
sudo nano /opt/zwift-scraper/webhook/webhook-config.json
```

**Verify secret is not exposed:**

```bash
# Check file permissions
ls -la /opt/zwift-scraper/webhook/webhook-config.json

# Should be readable only by root
sudo chmod 600 /opt/zwift-scraper/webhook/webhook-config.json
```

### 3. Database Security

**Use strong database passwords:**

```bash
# Generate strong password
openssl rand -base64 32
```

**Restrict database access:**

- Database is only accessible within Docker network
- Not exposed to external network by default
- Use strong passwords in `.env`

**Regular backups:**

```bash
# Automated backups (see Maintenance section)
0 2 * * * /opt/zwift-scraper/scripts/backup-db.sh
```

### 4. Firewall Configuration

**Configure UFW (Uncomplicated Firewall):**

```bash
# Enable firewall
sudo ufw enable

# Allow SSH (important!)
sudo ufw allow 22/tcp

# Allow webhook port (if needed externally)
sudo ufw allow 9000/tcp

# Allow CasaOS (if applicable)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status verbose
```

**Restrict webhook access:**

If possible, restrict webhook to GitHub IPs:

```bash
# GitHub webhook IP ranges (check GitHub documentation for current ranges)
sudo ufw allow from 140.82.112.0/20 to any port 9000
sudo ufw allow from 143.55.64.0/20 to any port 9000
```
### 5. Docker Security

**Run containers as non-root (when possible):**

The application containers run with minimal privileges. Avoid running containers with `--privileged` flag.

**Keep Docker updated:**

```bash
# Update Docker
sudo apt-get update
sudo apt-get upgrade docker.io docker-compose
```

**Scan images for vulnerabilities:**

```bash
# Install Docker Scout or Trivy
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image zwift-power-scraper_scraper
```

### 6. SSH Security

**Disable root SSH login:**

```bash
sudo nano /etc/ssh/sshd_config

# Set:
PermitRootLogin no
PasswordAuthentication no  # Use SSH keys only

# Restart SSH
sudo systemctl restart sshd
```

**Use SSH keys instead of passwords:**

```bash
# Generate SSH key (on your local machine)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Copy to server
ssh-copy-id user@your_server_ip
```

### 7. Regular Updates

**Keep system updated:**

```bash
# Update system packages
sudo apt-get update
sudo apt-get upgrade -y

# Update Docker images
cd /opt/zwift-scraper
sudo docker-compose pull
sudo docker-compose up -d
```

**Enable automatic security updates:**

```bash
sudo apt-get install unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

### 8. Monitoring and Alerts

**Set up monitoring:**

Consider implementing:
- Log monitoring (e.g., fail2ban for SSH)
- Disk space alerts
- Container health monitoring
- Database backup verification

**Example disk space alert:**

```bash
# Add to crontab
0 */6 * * * df -h | grep -E '^/dev/' | awk '{ if($5+0 > 80) print "Disk usage alert: " $0 }' | mail -s "Disk Space Alert" admin@example.com
```

### 9. Credential Rotation

**Regularly rotate credentials:**

- Database passwords (every 90 days)
- Webhook secrets (every 180 days)
- ZwiftPower cookies (automatically refreshed)
- SSH keys (annually)

**Change database password:**

```bash
# Update .env file
sudo nano /opt/zwift-scraper/.env

# Update database
sudo docker-compose exec postgres psql -U zwift_user -d zwift_racing -c "ALTER USER zwift_user WITH PASSWORD 'new_password';"

# Restart containers
sudo docker-compose restart
```

### 10. Audit Logs

**Enable Docker logging:**

```bash
# Check Docker daemon logs
sudo journalctl -u docker.service

# Enable audit logging
sudo apt-get install auditd
sudo systemctl enable auditd
sudo systemctl start auditd
```

---

## Updating the Application

How to update the application when new versions are released.

### Automatic Updates (via Webhook)

When properly configured, the webhook automatically deploys updates when you push to the `main` branch.

**How it works:**

1. You push changes to GitHub
2. GitHub sends webhook notification to your server
3. Webhook service triggers [`deploy.sh`](../webhook/deploy.sh)
4. Script pulls latest code
5. Rebuilds containers if needed (Dockerfile or requirements.txt changed)
6. Restarts scraper container
7. Logs deployment to `/opt/zwift-scraper/logs/deployment.log`

**Verify automatic deployment:**

```bash
# Check deployment logs
tail -f /opt/zwift-scraper/logs/deployment.log

# Check GitHub webhook deliveries
# Go to: GitHub Repository → Settings → Webhooks → Recent Deliveries
```

### Manual Update Process

If webhook is not configured or you prefer manual updates:

#### Step 1: Pull Latest Code

```bash
cd /opt/zwift-scraper

# Stash any local changes
sudo git stash

# Pull latest changes
sudo git pull origin main
```

#### Step 2: Check for Configuration Changes

```bash
# Compare .env.example with your .env
diff .env.example .env

# Add any new required variables to .env
sudo nano .env
```

#### Step 3: Rebuild Containers (if needed)

**If Dockerfile or requirements.txt changed:**

```bash
# Rebuild with no cache
sudo docker-compose build --no-cache scraper

# Or rebuild all services
sudo docker-compose build --no-cache
```

**If only Python code changed:**

```bash
# No rebuild needed, just restart
sudo docker-compose restart scraper
```

#### Step 4: Apply Database Migrations (if any)

```bash
# Check for migration scripts
ls -la /opt/zwift-scraper/database/migrations/

# Apply migrations if present
sudo docker-compose exec scraper python -m database.migrations
```

#### Step 5: Restart Services

```bash
# Restart all services
sudo docker-compose restart

# Or restart specific service
sudo docker-compose restart scraper
```

#### Step 6: Verify Update

```bash
# Check container status
sudo docker-compose ps

# Check logs for errors
sudo docker-compose logs -f scraper

# Test scraper execution
sudo docker-compose exec scraper python main.py
```

### Rollback to Previous Version

If an update causes issues:

```bash
cd /opt/zwift-scraper

# View commit history
git log --oneline -10

# Rollback to specific commit
sudo git reset --hard <commit-hash>

# Rebuild and restart
sudo docker-compose build scraper
sudo docker-compose restart scraper
```

### Update Checklist

Before updating:

- [ ] Backup database
- [ ] Review changelog/release notes
- [ ] Check for breaking changes
- [ ] Verify `.env` has all required variables
- [ ] Test in development environment (if available)

After updating:

- [ ] Verify containers are running
- [ ] Check logs for errors
- [ ] Test scraper execution
- [ ] Verify data is being collected
- [ ] Monitor for 24 hours

### Version Tracking

**Check current version:**

```bash
cd /opt/zwift-scraper
git log -1 --pretty=format:"%H %s"
```

**Tag releases:**

```bash
# Create a tag for stable releases
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

**View all tags:**

```bash
git tag -l
```

---

## Additional Resources

### Documentation

- [Main README](../README.md) - Project overview and features
- [Docker README](./DOCKER_README.md) - Docker configuration details
- [Test Documentation](./README_TESTS.md) - Testing procedures
- [Test Suite Summary](./TEST_SUITE_SUMMARY.md) - Test coverage details

### Scripts

- [`run-scraper.sh`](../scripts/run-scraper.sh) - Cron execution script
- [`deploy.sh`](../webhook/deploy.sh) - Webhook deployment script
- [`cookie_refresher.py`](../scripts/cookie_refresher.py) - Cookie refresh utility

### Configuration Files

- [`docker-compose.yml`](../docker-compose.yml) - Main Docker Compose configuration
- [`docker-compose.webhook.yml`](../webhook/docker-compose.webhook.yml) - Webhook service configuration
- [`webhook-config.json`](../webhook/webhook-config.json) - Webhook trigger rules
- [`.env.example`](../.env.example) - Environment variables template

### Useful Commands Reference

```bash
# Container Management
docker-compose ps                    # View container status
docker-compose logs -f               # Follow all logs
docker-compose logs -f scraper       # Follow scraper logs
docker-compose restart               # Restart all containers
docker-compose restart scraper       # Restart scraper only
docker-compose down                  # Stop and remove containers
docker-compose up -d                 # Start containers in background

# Database Operations
docker-compose exec postgres psql -U zwift_user -d zwift_racing
docker-compose exec -T postgres pg_dump -U zwift_user zwift_racing > backup.sql
docker-compose exec postgres pg_isready -U zwift_user -d zwift_racing

# Scraper Execution
docker-compose exec scraper python main.py
docker-compose exec scraper python scripts/cookie_refresher.py

# Log Viewing
tail -f /opt/zwift-scraper/logs/scraper.log
tail -f /opt/zwift-scraper/logs/cron.log
tail -f /opt/zwift-scraper/logs/deployment.log

# System Monitoring
docker stats                         # Container resource usage
df -h                               # Disk usage
free -h                             # Memory usage
sudo ufw status                     # Firewall status

# Cron Management
sudo crontab -l                     # List cron jobs
sudo crontab -e                     # Edit cron jobs
grep CRON /var/log/syslog          # View cron execution logs
```

---

## Support and Contributing

### Getting Support

If you need help:

1. Check this deployment guide thoroughly
2. Review the [Troubleshooting](#troubleshooting) section
3. Check application logs for error messages
4. Search existing GitHub issues
5. Open a new issue with detailed information

### Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Reporting Issues

When reporting issues, include:

- Operating system and version
- Docker and Docker Compose versions
- Error messages from logs
- Steps to reproduce
- Expected vs actual behavior

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.

---

## Changelog

### Version 1.0.0 (Current)

- Initial production release
- Automated server setup script
- GitHub webhook integration
- CasaOS compatibility
- Comprehensive documentation
- Automated cookie refresh
- Cron-based scheduling
- PostgreSQL database with pgAdmin
- Docker containerization
- Comprehensive test suite

---

**Last Updated**: 2026-10-07

**Maintained By**: Zwift Power Scraper Team

For questions or support, please open an issue on GitHub.

