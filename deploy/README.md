# IELTS Telegram Bot Deployment Guide

This directory contains all the necessary scripts and configurations for deploying the IELTS Telegram Bot to production environments, specifically optimized for DigitalOcean droplets.

## 📁 Files Overview

- **`deploy.sh`** - Main deployment script for fresh installations
- **`fast-update.sh`** - Fast update script for existing deployments
- **`verify-deployment.sh`** - Comprehensive deployment verification
- **`quick-verify.py`** - Quick Python-based verification script
- **`monitoring.yml`** - Docker Compose monitoring configuration
- **`README.md`** - This deployment guide

## 🚀 Quick Start

### 1. Initial Server Setup

For a fresh server, run the setup script first:

```bash
# Make setup script executable
chmod +x setup.sh

# Run setup (requires sudo on Linux)
sudo ./setup.sh

# Optional: Install Nginx and SSL
sudo INSTALL_NGINX=true SETUP_SSL=true DOMAIN=your-domain.com ./setup.sh
```

### 2. Deploy the Application

```bash
# Make deployment script executable
chmod +x deploy/deploy.sh

# Run deployment (requires sudo on Linux)
sudo ./deploy/deploy.sh
```

### 3. Verify Deployment

```bash
# Quick verification
python deploy/quick-verify.py --quick

# Comprehensive verification
./deploy/verify-deployment.sh

# Health check only
./deploy/verify-deployment.sh --health-only
```

## 📋 Prerequisites

### System Requirements

- **OS**: Ubuntu 20.04+ or CentOS 8+ (recommended)
- **RAM**: Minimum 1GB, recommended 2GB+
- **Storage**: Minimum 10GB free space
- **Network**: Internet connection for API calls

### Required Software

The setup script will install these automatically:

- Docker & Docker Compose
- Python 3.11+
- Git
- Nginx (optional)
- UFW/Firewalld (for firewall)

### Required API Keys

- **Telegram Bot Token**: Get from [@BotFather](https://t.me/botfather)
- **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/)

## 🔧 Configuration

### Environment Variables

Copy `.env.production` to `.env` and update with your values:

```bash
# Copy template
cp .env.production .env

# Edit with your API keys
nano .env
```

Required variables:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
DATABASE_URL=sqlite:///./data/ielts_bot.db
DEBUG=False
LOG_LEVEL=INFO
ENABLE_API=true
```

### Docker Configuration

The deployment uses Docker Compose with the following services:

- **ielts-bot**: Main application container
- **nginx**: Reverse proxy (optional)
- **monitoring**: Health checks and metrics (optional)

## 🔄 Deployment Process

### Fresh Deployment

1. **Server Preparation**
   ```bash
   sudo ./setup.sh
   ```

2. **Code Deployment**
   ```bash
   sudo ./deploy/deploy.sh
   ```

3. **Verification**
   ```bash
   ./deploy/verify-deployment.sh
   ```

### Updates

For existing deployments, use the fast update script:

```bash
# Quick update (auto-detects if rebuild needed)
./deploy/fast-update.sh

# Or use the shortcut
./update

# Fast restart only (no code pull)
./deploy/fast-update.sh --fast

# Full rebuild and restart
./deploy/fast-update.sh --full

# Check status
./deploy/fast-update.sh --status

# View logs
./deploy/fast-update.sh --logs=100
```

**Note**: The fast update script doesn't require sudo and works in the current directory.

## 🏥 Health Monitoring

### Health Check Endpoints

- **Health**: `http://your-server:8000/health`
- **API Root**: `http://your-server:8000/`

### Monitoring Features

- Container health checks
- Application health endpoint
- Log rotation and management
- Automatic restart on failure
- Resource usage monitoring

### Log Files

Logs are stored in `/opt/ielts-telegram-bot/logs/`:

- `bot.log` - Main application logs
- `error.log` - Error-specific logs
- `access.log` - API access logs

View logs:
```bash
# Real-time logs
docker-compose logs -f

# Application logs
tail -f /opt/ielts-telegram-bot/logs/bot.log

# Error logs
tail -f /opt/ielts-telegram-bot/logs/error.log
```

## 🔒 Security

### Firewall Configuration

The deployment automatically configures UFW (Ubuntu) or firewalld (CentOS):

- **SSH**: Port 22 (allowed)
- **HTTP**: Port 80 (allowed)
- **HTTPS**: Port 443 (allowed)
- **API**: Port 8000 (allowed)

### SSL/TLS (Optional)

Enable SSL during setup:
```bash
sudo INSTALL_NGINX=true SETUP_SSL=true DOMAIN=your-domain.com ./setup.sh
```

### Data Protection

- Environment variables stored securely
- Database file permissions restricted
- No sensitive data in logs
- API keys never logged

## 🔧 Troubleshooting

### Common Issues

1. **Container won't start**
   ```bash
   # Check logs
   docker-compose logs ielts-bot
   
   # Check environment
   cat .env
   
   # Restart containers
   docker-compose restart
   ```

2. **Health check fails**
   ```bash
   # Test health endpoint
   curl http://localhost:8000/health
   
   # Check container health
   docker-compose ps
   
   # Check application logs
   docker-compose logs --tail=50
   ```

3. **API errors**
   ```bash
   # Verify API keys
   grep -E "(TELEGRAM_BOT_TOKEN|OPENAI_API_KEY)" .env
   
   # Test API connectivity
   python -c "import openai; print('OpenAI client works')"
   ```

4. **Database issues**
   ```bash
   # Check database file
   ls -la data/ielts_bot.db
   
   # Check database permissions
   docker-compose exec ielts-bot ls -la /app/data/
   ```

### Debug Mode

Enable debug mode for troubleshooting:
```bash
# Edit .env
DEBUG=True
LOG_LEVEL=DEBUG

# Restart application
docker-compose restart
```

### Recovery Procedures

1. **Restore from backup**
   ```bash
   # List backups
   ls -la /opt/backups/ielts-telegram-bot/
   
   # Restore backup
   tar -xzf /opt/backups/ielts-telegram-bot/backup_YYYYMMDD_HHMMSS.tar.gz
   ```

2. **Reset deployment**
   ```bash
   # Stop and remove containers
   docker-compose down
   
   # Remove application data (careful!)
   sudo rm -rf /opt/ielts-telegram-bot/data/*
   
   # Redeploy
   sudo ./deploy/deploy.sh
   ```

## 📊 Performance Optimization

### Resource Limits

Configure in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
```

### Database Optimization

For high-traffic deployments, consider:
- Migrating to PostgreSQL
- Implementing connection pooling
- Adding database indexes

### API Rate Limiting

Monitor OpenAI API usage:
- Check daily limits
- Implement request queuing
- Add retry logic with backoff

## 🔄 Backup and Recovery

### Automated Backups

Backups are created automatically:
- **Schedule**: Daily at 2:00 AM
- **Location**: `/opt/backups/ielts-telegram-bot/`
- **Retention**: 7 days
- **Contents**: Database, logs, configuration

### Manual Backup

```bash
# Create manual backup
/usr/local/bin/ielts-telegram-bot-backup.sh

# Restore from backup
cd /opt/ielts-telegram-bot
tar -xzf /opt/backups/ielts-telegram-bot/backup_YYYYMMDD_HHMMSS.tar.gz
```

## 🌐 Scaling

### Horizontal Scaling

For multiple instances:
1. Use external database (PostgreSQL)
2. Implement session storage (Redis)
3. Load balancer configuration
4. Shared file storage

### Vertical Scaling

Increase resources:
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'
```

## 📞 Support

### Getting Help

1. **Check logs**: Always start with application logs
2. **Run verification**: Use verification scripts to identify issues
3. **Check documentation**: Review this guide and code comments
4. **Test components**: Isolate and test individual components

### Useful Commands

```bash
# Application status
docker-compose ps

# Resource usage
docker stats

# System resources
htop
df -h

# Network connectivity
curl -I http://localhost:8000/health

# Database check
sqlite3 data/ielts_bot.db ".tables"
```

## 📝 Changelog

### Version 1.0.0
- Initial deployment configuration
- Docker containerization
- Health monitoring
- Automated backups
- SSL support
- Comprehensive verification

---

For more information, see the main project README or contact the development team.