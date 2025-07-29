# DigitalOcean Deployment Guide for IELTS Telegram Bot

This comprehensive guide will walk you through deploying the IELTS Writing Evaluation Telegram Bot to a DigitalOcean droplet from scratch.

## 🎯 Quick Start (TL;DR)

For experienced users, here's the quick deployment process:

```bash
# 1. Create DigitalOcean droplet (Ubuntu 22.04, 2GB RAM)
# 2. Connect via SSH
ssh root@YOUR_DROPLET_IP

# 3. Clone repository
git clone https://github.com/yourusername/ielts-telegram-bot.git
cd ielts-telegram-bot

# 4. Run setup
sudo ./setup.sh

# 5. Configure environment
cp .env.production .env
nano .env  # Add your API keys

# 6. Deploy
sudo ./deploy/deploy.sh

# 7. Verify
./deploy/verify-deployment.sh
```

Your bot is now live! 🚀

## 📋 Prerequisites

### Required Information
- **Telegram Bot Token**: Get from [@BotFather](https://t.me/botfather)
- **OpenRouter API Key**: Get from [OpenRouter Platform](https://openrouter.ai/)
- **Domain Name** (optional): For SSL/HTTPS setup
- **DigitalOcean Account**: With billing enabled

### Local Requirements
- SSH client (Terminal on Mac/Linux, PuTTY on Windows)
- Git (for cloning the repository)
- Basic command line knowledge

## 🚀 Step 1: Create DigitalOcean Droplet

### 1.1 Create New Droplet

1. Log into your DigitalOcean account
2. Click "Create" → "Droplets"
3. Choose the following configuration:

**Recommended Configuration:**
- **Image**: Ubuntu 22.04 (LTS) x64
- **Plan**: Basic
- **CPU Options**: Regular Intel with SSD
- **Size**: $12/month (2 GB RAM, 1 vCPU, 50 GB SSD)
- **Datacenter**: Choose closest to your users
- **Authentication**: SSH Key (recommended) or Password
- **Hostname**: `ielts-bot-server` (or your preference)

### 1.2 Configure SSH Access

**Option A: SSH Key (Recommended)**
```bash
# Generate SSH key if you don't have one
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Copy public key content
cat ~/.ssh/id_rsa.pub
```
Paste the public key content in DigitalOcean's SSH key field.

**Option B: Password**
Set a strong password during droplet creation.

### 1.3 Create Droplet
Click "Create Droplet" and wait for it to be ready (usually 1-2 minutes).

## 🔧 Step 2: Initial Server Setup

### 2.1 Connect to Your Droplet

```bash
# Replace YOUR_DROPLET_IP with your actual IP
ssh root@YOUR_DROPLET_IP

# If using SSH key with custom name:
ssh -i ~/.ssh/your_key_name root@YOUR_DROPLET_IP
```

### 2.2 Update System

```bash
# Update package list and upgrade system
apt update && apt upgrade -y

# Install essential packages
apt install -y curl wget git unzip software-properties-common apt-transport-https ca-certificates gnupg lsb-release
```

### 2.3 Create Non-Root User (Recommended)

```bash
# Create new user
adduser ieltsbot

# Add to sudo group
usermod -aG sudo ieltsbot

# Copy SSH keys to new user (if using SSH keys)
rsync --archive --chown=ieltsbot:ieltsbot ~/.ssh /home/ieltsbot
```

### 2.4 Configure Firewall

```bash
# Enable UFW firewall
ufw enable

# Allow SSH
ufw allow ssh

# Allow HTTP and HTTPS
ufw allow 80
ufw allow 443

# Allow API port (optional, for direct API access)
ufw allow 8000

# Check status
ufw status
```

## 🐳 Step 3: Install Docker and Docker Compose

### 3.1 Install Docker

```bash
# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package list
apt update

# Install Docker
apt install -y docker-ce docker-ce-cli containerd.io

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Add user to docker group (replace 'ieltsbot' with your username)
usermod -aG docker ieltsbot
```

### 3.2 Install Docker Compose

```bash
# Download Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Make executable
chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

## 📦 Step 4: Deploy the Application

### 4.1 Switch to Application User

```bash
# Switch to your application user
su - ieltsbot
```

### 4.2 Clone the Repository

```bash
# Clone your repository (replace with your actual repository URL)
git clone https://github.com/yourusername/ielts-telegram-bot.git

# Navigate to project directory
cd ielts-telegram-bot

# Make scripts executable
chmod +x setup.sh
chmod +x deploy/*.sh
```

### 4.3 Run Setup Script

```bash
# Run the setup script
sudo ./setup.sh

# If you want to install Nginx and SSL (optional)
sudo INSTALL_NGINX=true SETUP_SSL=true DOMAIN=yourdomain.com ./setup.sh
```

### 4.4 Configure Environment Variables

```bash
# Copy production environment template
cp .env.production .env

# Edit environment file
nano .env
```

**Update the following variables in `.env`:**

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# OpenRouter Configuration (AI Service)
OPENAI_API_KEY=sk-or-v1-abcdefghijklmnopqrstuvwxyz
OPENAI_MODEL=meta-llama/llama-3.1-8b-instruct:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=https://ielts-telegram-bot.local
OPENROUTER_SITE_NAME=IELTS Writing Bot

# Database Configuration
DATABASE_URL=sqlite:///./data/ielts_bot.db

# Application Configuration
DEBUG=False
LOG_LEVEL=INFO
ENABLE_API=true

# Rate Limiting Configuration
DAILY_SUBMISSION_LIMIT=3
PRO_DAILY_LIMIT=50

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

**Save and exit** (Ctrl+X, then Y, then Enter in nano)

### 4.5 Deploy the Application

```bash
# Run deployment script
sudo ./deploy/deploy.sh
```

The deployment script will:
- Build Docker images
- Create necessary directories
- Set up database
- Start containers
- Configure logging
- Set up automatic backups

## ✅ Step 5: Verify Deployment

### 5.1 Quick Verification

```bash
# Run quick verification
python deploy/quick-verify.py --quick

# Or comprehensive verification
./deploy/verify-deployment.sh
```

### 5.2 Check Application Status

```bash
# Check container status
docker-compose ps

# Check logs
docker-compose logs -f --tail=50

# Test health endpoint
curl http://localhost:8000/health
```

### 5.3 Test Bot Functionality

1. Open Telegram
2. Search for your bot by username
3. Send `/start` command
4. Try submitting a sample IELTS writing task

## 🌐 Step 6: Configure Domain and SSL (Optional)

### 6.1 Point Domain to Droplet

1. In your domain registrar's DNS settings:
   - Create an A record pointing to your droplet's IP address
   - Example: `ielts-bot.yourdomain.com` → `YOUR_DROPLET_IP`

2. Wait for DNS propagation (5-30 minutes)

### 6.2 Install Nginx and SSL

```bash
# Install Nginx
sudo apt install -y nginx

# Install Certbot for Let's Encrypt SSL
sudo apt install -y certbot python3-certbot-nginx

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/ielts-bot
```

**Nginx configuration:**

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/ielts-bot /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## 📊 Step 7: Set Up Monitoring and Maintenance

### 7.1 Set Up Log Rotation

```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/ielts-bot
```

```
/opt/ielts-telegram-bot/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 ieltsbot ieltsbot
    postrotate
        docker-compose -f /opt/ielts-telegram-bot/docker-compose.yml restart > /dev/null 2>&1 || true
    endscript
}
```

### 7.2 Set Up Automatic Backups

```bash
# Create backup script
sudo nano /usr/local/bin/ielts-bot-backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/ielts-telegram-bot"
APP_DIR="/opt/ielts-telegram-bot"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Create backup
cd "$APP_DIR"
tar -czf "$BACKUP_DIR/backup_$DATE.tar.gz" \
    data/ \
    logs/ \
    .env \
    docker-compose.yml

# Keep only last 7 backups
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete

echo "Backup completed: backup_$DATE.tar.gz"
```

```bash
# Make executable
sudo chmod +x /usr/local/bin/ielts-bot-backup.sh

# Add to crontab for daily backups at 2 AM
sudo crontab -e
```

Add this line:
```
0 2 * * * /usr/local/bin/ielts-bot-backup.sh >> /var/log/ielts-bot-backup.log 2>&1
```

### 7.3 Set Up Health Monitoring

```bash
# Create health check script
sudo nano /usr/local/bin/ielts-bot-health.sh
```

```bash
#!/bin/bash
HEALTH_URL="http://localhost:8000/health"
LOG_FILE="/var/log/ielts-bot-health.log"

if curl -f -s "$HEALTH_URL" > /dev/null; then
    echo "$(date): Health check passed" >> "$LOG_FILE"
else
    echo "$(date): Health check failed - restarting application" >> "$LOG_FILE"
    cd /opt/ielts-telegram-bot
    docker-compose restart
fi
```

```bash
# Make executable
sudo chmod +x /usr/local/bin/ielts-bot-health.sh

# Add to crontab for every 5 minutes
sudo crontab -e
```

Add this line:
```
*/5 * * * * /usr/local/bin/ielts-bot-health.sh
```

## 🔧 Step 8: Performance Optimization

### 8.1 Optimize Docker Resources

Edit `docker-compose.yml`:

```yaml
services:
  ielts-bot:
    # ... other configuration
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
```

### 8.2 Enable Docker Logging Limits

```yaml
services:
  ielts-bot:
    # ... other configuration
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

### 8.3 Optimize System Settings

```bash
# Increase file descriptor limits
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Optimize kernel parameters
echo "net.core.somaxconn = 65536" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65536" | sudo tee -a /etc/sysctl.conf

# Apply changes
sudo sysctl -p
```

## 🚨 Step 9: Security Hardening

### 9.1 Secure SSH

```bash
# Edit SSH configuration
sudo nano /etc/ssh/sshd_config
```

Update these settings:
```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
Port 2222  # Change default port
```

```bash
# Update firewall for new SSH port
sudo ufw allow 2222
sudo ufw delete allow ssh

# Restart SSH service
sudo systemctl restart sshd
```

### 9.2 Install Fail2Ban

```bash
# Install fail2ban
sudo apt install -y fail2ban

# Create configuration
sudo nano /etc/fail2ban/jail.local
```

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = 2222
logpath = /var/log/auth.log

[nginx-http-auth]
enabled = true
logpath = /var/log/nginx/error.log
```

```bash
# Start and enable fail2ban
sudo systemctl start fail2ban
sudo systemctl enable fail2ban
```

### 9.3 Set Up Automatic Updates

```bash
# Install unattended-upgrades
sudo apt install -y unattended-upgrades

# Configure automatic updates
sudo dpkg-reconfigure -plow unattended-upgrades
```

## 📱 Step 10: Final Testing and Go-Live

### 10.1 Comprehensive Testing

```bash
# Run comprehensive tests
python tests/run_comprehensive_tests.py

# Test specific functionality
python tests/run_comprehensive_tests.py --suites end_to_end performance
```

### 10.2 Load Testing

```bash
# Test with multiple concurrent users
python tests/run_comprehensive_tests.py --suites performance database_load
```

### 10.3 Bot Testing Checklist

- [ ] `/start` command works
- [ ] Task 1 submission and evaluation
- [ ] Task 2 submission and evaluation
- [ ] History viewing
- [ ] Rate limiting for free users
- [ ] Error handling (invalid input)
- [ ] Task type clarification
- [ ] Progress tracking

## 🔄 Step 11: Maintenance and Updates

### 11.1 Regular Updates

```bash
# Update application code
cd /opt/ielts-telegram-bot
git pull origin main

# Rebuild and restart
sudo docker-compose build --no-cache
sudo docker-compose up -d

# Verify deployment
./deploy/verify-deployment.sh
```

### 11.2 Monitor Resources

```bash
# Check system resources
htop
df -h
free -h

# Check Docker resources
docker stats

# Check application logs
docker-compose logs --tail=100
```

### 11.3 Database Maintenance

```bash
# Backup database
cp data/ielts_bot.db data/ielts_bot.db.backup

# Check database size
ls -lh data/ielts_bot.db

# Vacuum database (if needed)
sqlite3 data/ielts_bot.db "VACUUM;"
```

## 🆘 Troubleshooting

### Common Issues and Solutions

#### 1. Container Won't Start
```bash
# Check logs
docker-compose logs ielts-bot

# Check environment variables
cat .env

# Rebuild container
docker-compose build --no-cache
docker-compose up -d
```

#### 2. Health Check Fails
```bash
# Test health endpoint
curl http://localhost:8000/health

# Check if port is listening
netstat -tlnp | grep 8000

# Check container status
docker-compose ps
```

#### 3. Bot Not Responding
```bash
# Check Telegram token
grep TELEGRAM_BOT_TOKEN .env

# Test token validity
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"

# Check bot logs
docker-compose logs ielts-bot | grep -i telegram
```

#### 4. OpenRouter API Errors
```bash
# Check API key
grep OPENAI_API_KEY .env

# Test API connectivity
curl -H "Authorization: Bearer YOUR_API_KEY" https://openrouter.ai/api/v1/models
```

#### 5. Database Issues
```bash
# Check database file permissions
ls -la data/ielts_bot.db

# Check database connectivity
sqlite3 data/ielts_bot.db ".tables"
```

### Emergency Recovery

#### Restore from Backup
```bash
# Stop application
docker-compose down

# Restore backup
cd /opt/ielts-telegram-bot
tar -xzf /opt/backups/ielts-telegram-bot/backup_YYYYMMDD_HHMMSS.tar.gz

# Start application
docker-compose up -d
```

#### Complete Reset
```bash
# Stop and remove containers
docker-compose down
docker system prune -a

# Remove application data (CAREFUL!)
sudo rm -rf /opt/ielts-telegram-bot/data/*

# Redeploy
sudo ./deploy/deploy.sh
```

## 📞 Support and Monitoring

### Log Locations
- Application logs: `/opt/ielts-telegram-bot/logs/`
- System logs: `/var/log/`
- Docker logs: `docker-compose logs`

### Monitoring Commands
```bash
# Real-time application logs
docker-compose logs -f

# System resource usage
htop

# Disk usage
df -h

# Network connections
netstat -tlnp

# Process list
ps aux | grep python
```

### Performance Metrics
- Response time: < 2 seconds
- Memory usage: < 512MB
- CPU usage: < 50%
- Disk usage: < 80%

## 🎉 Conclusion

Your IELTS Telegram Bot is now successfully deployed on DigitalOcean! The bot should be:

- ✅ Accessible via Telegram
- ✅ Processing IELTS evaluations
- ✅ Storing data persistently
- ✅ Automatically backing up
- ✅ Monitoring its own health
- ✅ Secured with proper firewall rules
- ✅ Optimized for performance

### Next Steps
1. Monitor the bot's performance for the first few days
2. Set up additional monitoring if needed
3. Consider scaling if you get high traffic
4. Regularly update the application and system packages
5. Monitor OpenRouter API usage and costs

### Cost Estimation
- **DigitalOcean Droplet**: $12/month (2GB RAM)
- **Domain** (optional): $10-15/year
- **OpenRouter API**: Variable based on usage (~$5-30/month depending on traffic and model choice)
- **Total**: ~$12-15/month + API costs

Your IELTS bot is now ready to help users improve their writing skills! 🚀