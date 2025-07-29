# IELTS Telegram Bot Deployment Checklist

Use this checklist to ensure a successful deployment to DigitalOcean.

## 📋 Pre-Deployment Checklist

### Required Information
- [ ] **Telegram Bot Token** - Get from [@BotFather](https://t.me/botfather)
- [ ] **OpenRouter API Key** - Get from [OpenRouter Platform](https://openrouter.ai/)
- [ ] **DigitalOcean Account** - With billing enabled
- [ ] **Domain Name** (optional) - For SSL/HTTPS setup
- [ ] **SSH Key** (recommended) - For secure server access

### Local Setup
- [ ] Git installed and configured
- [ ] SSH client available
- [ ] Repository cloned locally
- [ ] Environment variables prepared

## 🖥️ Server Setup Checklist

### DigitalOcean Droplet Creation
- [ ] **Image**: Ubuntu 22.04 (LTS) x64
- [ ] **Size**: 2 GB RAM, 1 vCPU, 50 GB SSD ($12/month)
- [ ] **Datacenter**: Closest to your users
- [ ] **Authentication**: SSH Key configured
- [ ] **Hostname**: Set to meaningful name (e.g., `ielts-bot-server`)
- [ ] **Firewall**: Default (will be configured later)

### Initial Server Access
- [ ] SSH connection successful: `ssh root@YOUR_DROPLET_IP`
- [ ] Server responding and accessible
- [ ] Internet connectivity working
- [ ] Sufficient disk space available (check with `df -h`)

## 🔧 Installation Checklist

### System Preparation
- [ ] System packages updated: `apt update && apt upgrade -y`
- [ ] Repository cloned: `git clone https://github.com/yourusername/ielts-telegram-bot.git`
- [ ] Changed to project directory: `cd ielts-telegram-bot`
- [ ] Setup script executable: `chmod +x setup.sh`

### Run Setup Script
- [ ] Setup script executed: `sudo ./setup.sh`
- [ ] Python 3.11+ installed and working
- [ ] Docker installed and running
- [ ] Docker Compose available
- [ ] Git installed and configured
- [ ] Firewall configured (UFW enabled)
- [ ] Application user created (`ieltsbot`)
- [ ] Directories created (`/opt/ielts-telegram-bot`)

### Optional Components (if enabled)
- [ ] Nginx installed and running (if `INSTALL_NGINX=true`)
- [ ] SSL certificates configured (if `SETUP_SSL=true` and domain provided)
- [ ] Domain pointing to server IP

## ⚙️ Configuration Checklist

### Environment Configuration
- [ ] Environment file created: `cp .env.production .env`
- [ ] Environment file edited: `nano .env`
- [ ] **TELEGRAM_BOT_TOKEN** set with actual token
- [ ] **OPENAI_API_KEY** set with actual OpenRouter API key
- [ ] **DATABASE_URL** configured (default SQLite is fine)
- [ ] **DEBUG** set to `False`
- [ ] **LOG_LEVEL** set to `INFO`
- [ ] All placeholder values replaced

### Validate Configuration
- [ ] No placeholder values remain (`your_*_here`)
- [ ] No empty values for required variables
- [ ] Telegram token format correct (looks like `1234567890:ABCdef...`)
- [ ] OpenRouter API key format correct (starts with `sk-or-v1-`)

## 🚀 Deployment Checklist

### Run Deployment Script
- [ ] Deployment script executable: `chmod +x deploy/deploy.sh`
- [ ] Deployment executed: `sudo ./deploy/deploy.sh`
- [ ] Docker images built successfully
- [ ] Containers started and running
- [ ] No error messages in deployment log
- [ ] Health check passed during deployment

### Verify Deployment
- [ ] Verification script executed: `./deploy/verify-deployment.sh`
- [ ] All tests passed
- [ ] Health endpoint responding: `curl http://localhost:8000/health`
- [ ] API endpoint responding: `curl http://localhost:8000`
- [ ] Container status healthy: `docker-compose ps`
- [ ] Application logs clean: `docker-compose logs --tail=50`

## 🤖 Bot Testing Checklist

### Basic Functionality
- [ ] Bot found in Telegram search
- [ ] `/start` command works
- [ ] Welcome message displays correctly
- [ ] Main menu buttons appear
- [ ] Bot responds to button clicks

### Task 1 Testing
- [ ] "Submit Writing Task 1" button works
- [ ] Task 1 instructions display
- [ ] Sample Task 1 text submission works
- [ ] Evaluation completes successfully
- [ ] Band scores displayed (4 criteria + overall)
- [ ] Feedback and suggestions provided
- [ ] Results formatted correctly

### Task 2 Testing
- [ ] "Submit Writing Task 2" button works
- [ ] Task 2 instructions display
- [ ] Sample Task 2 text submission works
- [ ] Evaluation completes successfully
- [ ] Band scores displayed (4 criteria + overall)
- [ ] Feedback and suggestions provided
- [ ] Results formatted correctly

### Advanced Features
- [ ] History viewing works
- [ ] Progress tracking displays
- [ ] Rate limiting enforced (try 4+ submissions)
- [ ] Error handling works (submit very short text)
- [ ] Task type clarification works (submit ambiguous text)
- [ ] Back to menu navigation works

## 🔒 Security Checklist

### Firewall Configuration
- [ ] UFW enabled and active: `ufw status`
- [ ] SSH port allowed (22 or custom)
- [ ] HTTP port allowed (80)
- [ ] HTTPS port allowed (443)
- [ ] API port allowed (8000)
- [ ] Unnecessary ports blocked

### Access Control
- [ ] Root login disabled (if using non-root user)
- [ ] SSH key authentication working
- [ ] Password authentication disabled (if using keys)
- [ ] Application running as non-root user (`ieltsbot`)
- [ ] File permissions properly set

### SSL/HTTPS (if configured)
- [ ] SSL certificate installed
- [ ] HTTPS redirect working
- [ ] Certificate auto-renewal configured
- [ ] Domain resolving correctly

## 📊 Monitoring Setup Checklist

### Automated Monitoring
- [ ] Health check script configured: `/usr/local/bin/ielts-telegram-bot-health.sh`
- [ ] Health checks running every 5 minutes (crontab)
- [ ] Backup script configured: `/usr/local/bin/ielts-telegram-bot-backup.sh`
- [ ] Daily backups scheduled (crontab at 2 AM)
- [ ] Log rotation configured: `/etc/logrotate.d/ielts-telegram-bot`

### System Service
- [ ] Systemd service created: `/etc/systemd/system/ielts-telegram-bot.service`
- [ ] Service enabled: `systemctl is-enabled ielts-telegram-bot`
- [ ] Service can start: `systemctl start ielts-telegram-bot`
- [ ] Service can stop: `systemctl stop ielts-telegram-bot`
- [ ] Service can restart: `systemctl restart ielts-telegram-bot`

## 🔍 Performance Checklist

### Resource Usage
- [ ] Memory usage reasonable: `free -h` (< 80% used)
- [ ] CPU usage normal: `htop` (< 50% average)
- [ ] Disk space sufficient: `df -h` (< 80% used)
- [ ] No memory leaks detected
- [ ] Response times acceptable (< 2 seconds)

### Load Testing
- [ ] Multiple concurrent users tested
- [ ] Rate limiting working under load
- [ ] Database performance acceptable
- [ ] No crashes under normal load
- [ ] Error handling graceful

## 📝 Documentation Checklist

### Deployment Documentation
- [ ] Server details documented (IP, credentials, etc.)
- [ ] Environment variables documented
- [ ] Backup procedures documented
- [ ] Recovery procedures documented
- [ ] Monitoring setup documented

### Operational Procedures
- [ ] Update procedure tested: `./deploy/update.sh`
- [ ] Rollback procedure tested: `./deploy/update.sh --rollback`
- [ ] Backup restoration tested
- [ ] Log access documented
- [ ] Troubleshooting guide available

## 🎉 Go-Live Checklist

### Final Verification
- [ ] All previous checklist items completed
- [ ] Comprehensive tests passed: `python tests/run_comprehensive_tests.py`
- [ ] Performance benchmarks met
- [ ] Security scan completed
- [ ] Backup and recovery tested

### Launch Preparation
- [ ] Bot username finalized
- [ ] Bot description and about text set
- [ ] Bot profile picture uploaded
- [ ] Commands list configured in BotFather
- [ ] Privacy settings configured

### Post-Launch Monitoring
- [ ] Real user testing completed
- [ ] Monitoring alerts configured
- [ ] Support procedures established
- [ ] Usage analytics tracking (if desired)
- [ ] Cost monitoring setup (OpenRouter API usage)

## 🚨 Troubleshooting Quick Reference

### Common Issues
- **Container won't start**: Check logs with `docker-compose logs`
- **Health check fails**: Verify environment variables and API keys
- **Bot not responding**: Check Telegram token and network connectivity
- **OpenAI errors**: Verify API key and check usage limits
- **Database errors**: Check file permissions and disk space

### Emergency Contacts
- [ ] Server access credentials secured
- [ ] API key backup stored safely
- [ ] Emergency contact list prepared
- [ ] Escalation procedures defined

## ✅ Deployment Complete

Once all items are checked:

- [ ] **Deployment successful** - All tests passed
- [ ] **Bot operational** - Responding to users
- [ ] **Monitoring active** - Health checks and backups running
- [ ] **Documentation complete** - All procedures documented
- [ ] **Team notified** - Stakeholders informed of successful deployment

**Congratulations! Your IELTS Telegram Bot is now live and ready to help users improve their writing skills! 🎉**

---

## 📞 Support Information

- **Health Check**: `curl http://YOUR_SERVER_IP:8000/health`
- **Application Logs**: `docker-compose -f /opt/ielts-telegram-bot/docker-compose.yml logs -f`
- **System Status**: `systemctl status ielts-telegram-bot`
- **Resource Usage**: `htop` and `df -h`

For issues, check the troubleshooting section in `DIGITALOCEAN_DEPLOYMENT_GUIDE.md`.