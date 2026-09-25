# Docker Setup for Zwift Racing Scraper

Complete Docker containerization with PostgreSQL database and optional pgAdmin interface.

## 📋 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- `.env` file with required credentials (see Environment Variables section)

## 🚀 Quick Start

### 1. Configure Environment Variables

Create or update your `.env` file with the following variables:

```bash
# Database Configuration
DB_NAME=zwift_racing
DB_USER=zwift_user
DB_PASS=your_secure_password
DB_HOST=postgres  # Use 'postgres' for Docker, 'localhost' for local dev
DB_PORT=5432

# ZwiftPower Authentication Cookies
PHPBB3_SID=your_phpbb_session_id
PHPBB3_U=your_phpbb_user_id
CLOUDFRONT_KEY_PAIR_ID=your_cloudfront_key_pair_id
CLOUDFRONT_POLICY=your_cloudfront_policy
CLOUDFRONT_SIGNATURE=your_cloudfront_signature

# Zwift Credentials (for automatic cookie refresh)
ZWIFT_USER=your_zwift_email@example.com
ZWIFT_PASS=your_zwift_password

# Optional: pgAdmin Configuration
PGADMIN_EMAIL=admin@zwift.local
PGADMIN_PASSWORD=admin
PGADMIN_PORT=5050
```

### 2. Build and Run

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f scraper

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes database data)
docker-compose down -v
```

### 3. Run with pgAdmin (Optional)

```bash
# Start with database management interface
docker-compose --profile tools up -d

# Access pgAdmin at http://localhost:5050
# Login with PGADMIN_EMAIL and PGADMIN_PASSWORD from .env
```

## 🏗️ Architecture

### Services

1. **postgres** - PostgreSQL 15 database
   - Port: 5432 (configurable)
   - Data persisted in `postgres_data` volume
   - Health checks enabled

2. **scraper** - Python application
   - Depends on PostgreSQL
   - Mounts `.env` for cookie updates
   - Mounts `output/` for CSV exports
   - Mounts `zids.txt` for rider IDs

3. **pgadmin** (optional) - Database management UI
   - Port: 5050 (configurable)
   - Only starts with `--profile tools` flag

### Volumes

- `postgres_data` - Database persistence
- `pgadmin_data` - pgAdmin settings persistence
- `./output` - CSV export directory (bind mount)
- `./.env` - Environment file (bind mount, allows cookie updates)
- `./zids.txt` - Rider IDs list (bind mount, read-only)

## 📝 Usage Examples

### One-Time Execution

```bash
# Run scraper once and exit
docker-compose up scraper
```

### Scheduled Execution

Uncomment the `command` line in `docker-compose.yml`:

```yaml
command: sh -c "while true; do python all_in_one.py && sleep 3600; done"
```

Then run:

```bash
docker-compose up -d scraper
```

This runs the scraper every hour (3600 seconds).

### Manual Execution

```bash
# Execute scraper in running container
docker-compose exec scraper python all_in_one.py

# Run with custom zids
docker-compose exec scraper python -c "
from all_in_one import ZwiftPowerClient
client = ZwiftPowerClient()
profiles = client.get_profiles([1714370, 1815308])
print(profiles)
"
```

### Update Rider IDs

```bash
# Edit zids.txt on host machine
echo "1714370" >> zids.txt
echo "1815308" >> zids.txt

# Restart scraper to pick up changes
docker-compose restart scraper
```

## 🔧 Maintenance

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f scraper
docker-compose logs -f postgres

# Last 100 lines
docker-compose logs --tail=100 scraper
```

### Database Access

```bash
# Connect to PostgreSQL via psql
docker-compose exec postgres psql -U zwift_user -d zwift_racing

# Backup database
docker-compose exec postgres pg_dump -U zwift_user zwift_racing > backup.sql

# Restore database
docker-compose exec -T postgres psql -U zwift_user zwift_racing < backup.sql
```

### Rebuild After Code Changes

```bash
# Rebuild scraper image
docker-compose build scraper

# Rebuild and restart
docker-compose up -d --build scraper
```

### Clean Up

```bash
# Remove stopped containers
docker-compose rm

# Remove unused images
docker image prune -a

# Remove all project resources (WARNING: deletes data)
docker-compose down -v --rmi all
```

## 🐛 Troubleshooting

### Scraper Can't Connect to Database

**Symptom:** `connection refused` or `could not connect to server`

**Solution:**
```bash
# Check if postgres is healthy
docker-compose ps

# View postgres logs
docker-compose logs postgres

# Ensure DB_HOST=postgres in .env (not localhost)
```

### Cookie Refresh Fails

**Symptom:** `Playwright timeout` or `login page detected`

**Solution:**
```bash
# Check Zwift credentials in .env
# View detailed logs
docker-compose logs scraper | grep -i cookie

# Manually refresh cookies
docker-compose exec scraper python cookie_refresher.py
```

### Permission Denied on Output Directory

**Symptom:** `Permission denied: '/app/output/...'`

**Solution:**
```bash
# Fix permissions on host
chmod -R 777 output/

# Or run container as root (not recommended)
# Add to docker-compose.yml under scraper service:
# user: "0:0"
```

### Playwright Browser Not Found

**Symptom:** `Executable doesn't exist at /root/.cache/ms-playwright/...`

**Solution:**
```bash
# Rebuild image (browsers are installed during build)
docker-compose build --no-cache scraper
docker-compose up -d scraper
```

## 🔒 Security Best Practices

1. **Never commit `.env` file** - Add to `.gitignore`
2. **Use strong database passwords** - Change default `DB_PASS`
3. **Restrict network access** - Use firewall rules for exposed ports
4. **Run as non-root** - Already configured in Dockerfile
5. **Keep images updated** - Regularly rebuild with latest base images
6. **Scan for vulnerabilities** - Use `docker scan zwift_scraper`

## 📊 Monitoring

### Resource Usage

```bash
# View resource consumption
docker stats zwift_scraper zwift_postgres

# View disk usage
docker system df
```

### Health Checks

```bash
# Check service health
docker-compose ps

# Manual health check
docker-compose exec scraper python -c "import all_in_one, cookie_refresher, database"
```

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t zwift-scraper:latest .
      
      - name: Run tests
        run: |
          docker run --rm zwift-scraper:latest python -m pytest tests/
```

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [Playwright Docker Documentation](https://playwright.dev/docs/docker)

## 🆘 Support

For issues related to:
- **Docker setup** - Check this README and troubleshooting section
- **Application logic** - See main project README
- **Database schema** - Check `database.py` and `init_db.sql`
