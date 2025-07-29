#!/bin/bash

# IELTS Telegram Bot Deployment Script for DigitalOcean
# This script handles fresh deployment and updates

set -e

# Configuration
APP_NAME="ielts-telegram-bot"
APP_DIR="/opt/$APP_NAME"
BACKUP_DIR="/opt/backups/$APP_NAME"
LOG_FILE="/var/log/${APP_NAME}_deploy.log"
DOCKER_COMPOSE_VERSION="2.20.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}" | tee -a "$LOG_FILE"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check system requirements
check_requirements() {
    log "Checking system requirements..."
    
    # Check OS
    if [[ ! -f /etc/os-release ]]; then
        error "Cannot determine OS version"
        exit 1
    fi
    
    source /etc/os-release
    if [[ "$ID" != "ubuntu" ]] && [[ "$ID" != "debian" ]]; then
        warn "This script is optimized for Ubuntu/Debian. Proceeding anyway..."
    fi
    
    # Check available space
    # local available_space=$(df / | awk 'NR==2 {print $4}')
    # if [[ $available_space -lt 5242880 ]]; then # 5GB in KB
    #     error "Insufficient disk space. At least 5GB required."
    #     exit 1
    # fi
    
    # Check memory
    local available_memory=$(free -m | awk 'NR==2{print $7}')
    if [[ $available_memory -lt 512 ]]; then
        warn "Low available memory (${available_memory}MB). Consider upgrading your droplet."
    fi
    
    log "System requirements check passed"
}

# Install Docker if not present
install_docker() {
    if command -v docker >/dev/null 2>&1; then
        log "Docker already installed: $(docker --version)"
        return 0
    fi
    
    log "Installing Docker..."
    
    # Update package index
    apt-get update
    
    # Install prerequisites
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Add Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Update package index again
    apt-get update
    
    # Install Docker
    apt-get install -y docker-ce docker-ce-cli containerd.io
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    # Add current user to docker group if not root
    if [[ -n "$SUDO_USER" ]]; then
        usermod -aG docker "$SUDO_USER"
        log "Added $SUDO_USER to docker group"
    fi
    
    log "Docker installed successfully: $(docker --version)"
}

# Install Docker Compose if not present
install_docker_compose() {
    if command -v docker-compose >/dev/null 2>&1; then
        log "Docker Compose already installed: $(docker-compose --version)"
        return 0
    fi
    
    log "Installing Docker Compose..."
    
    # Download Docker Compose
    curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    
    # Make executable
    chmod +x /usr/local/bin/docker-compose
    
    # Create symlink for easier access
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    
    log "Docker Compose installed successfully: $(docker-compose --version)"
}

# Create application user
create_app_user() {
    local app_user="ieltsbot"
    
    if id "$app_user" &>/dev/null; then
        log "Application user '$app_user' already exists"
        return 0
    fi
    
    log "Creating application user '$app_user'..."
    
    # Create user with home directory
    useradd -m -s /bin/bash "$app_user"
    
    # Add to docker group
    usermod -aG docker "$app_user"
    
    log "Application user '$app_user' created successfully"
}

# Create directory structure
create_directories() {
    log "Creating directory structure..."
    
    # Create main directories
    mkdir -p "$APP_DIR"
    mkdir -p "$APP_DIR/data"
    mkdir -p "$APP_DIR/logs"
    mkdir -p "$BACKUP_DIR"
    
    # Create log directory
    mkdir -p /var/log
    
    # Set permissions
    chown -R ieltsbot:ieltsbot "$APP_DIR"
    chown -R ieltsbot:ieltsbot "$BACKUP_DIR"
    
    log "Directory structure created successfully"
}

# Copy application files
copy_application_files() {
    log "Copying application files..."
    
    local source_dir=$(pwd)
    
    # Copy main application files
    cp -r "$source_dir/src" "$APP_DIR/"
    cp -r "$source_dir/tests" "$APP_DIR/"
    cp "$source_dir/requirements.txt" "$APP_DIR/"
    cp "$source_dir/Dockerfile" "$APP_DIR/"
    cp "$source_dir/docker-compose.yml" "$APP_DIR/"
    cp "$source_dir/pytest.ini" "$APP_DIR/"
    
    # Copy deployment files
    cp -r "$source_dir/deploy" "$APP_DIR/"
    
    # Copy environment file if it exists
    if [[ -f "$source_dir/.env" ]]; then
        cp "$source_dir/.env" "$APP_DIR/"
    elif [[ -f "$source_dir/.env.production" ]]; then
        cp "$source_dir/.env.production" "$APP_DIR/.env"
        warn "Copied .env.production as .env - please update with your actual values"
    else
        error "No environment file found. Please create .env file with your configuration"
        exit 1
    fi
    
    # Set permissions
    chown -R ieltsbot:ieltsbot "$APP_DIR"
    
    log "Application files copied successfully"
}

# Validate environment configuration
validate_environment() {
    log "Validating environment configuration..."
    
    if [[ ! -f "$APP_DIR/.env" ]]; then
        error "Environment file not found at $APP_DIR/.env"
        exit 1
    fi
    
    # Check required variables
    local required_vars=(
        "TELEGRAM_BOT_TOKEN"
        "OPENAI_API_KEY"
        "DATABASE_URL"
    )
    
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" "$APP_DIR/.env" 2>/dev/null; then
            missing_vars+=("$var")
        elif grep -q "^$var=your_.*_here" "$APP_DIR/.env" 2>/dev/null; then
            missing_vars+=("$var (placeholder value)")
        elif grep -q "^$var=$" "$APP_DIR/.env" 2>/dev/null; then
            missing_vars+=("$var (empty value)")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        error "Missing or invalid environment variables:"
        for var in "${missing_vars[@]}"; do
            error "  - $var"
        done
        error "Please update $APP_DIR/.env with valid values"
        exit 1
    fi
    
    log "Environment configuration validated successfully"
}

# Build and start application
build_and_start() {
    log "Building and starting application..."
    
    cd "$APP_DIR"
    
    # Stop existing containers if running
    if docker-compose ps -q 2>/dev/null | grep -q .; then
        log "Stopping existing containers..."
        docker-compose down
    fi
    
    # Build images
    log "Building Docker images..."
    docker-compose build --no-cache
    
    # Start containers
    log "Starting containers..."
    docker-compose up -d
    
    # Wait for containers to be ready
    log "Waiting for containers to be ready..."
    sleep 30
    
    # Check container status
    if ! docker-compose ps | grep -q "Up"; then
        error "Containers failed to start properly"
        docker-compose logs
        exit 1
    fi
    
    log "Application started successfully"
}

# Set up systemd service
setup_systemd_service() {
    log "Setting up systemd service..."
    
    cat > "/etc/systemd/system/${APP_NAME}.service" << EOF
[Unit]
Description=IELTS Telegram Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0
User=ieltsbot
Group=ieltsbot

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable "${APP_NAME}.service"
    
    log "Systemd service configured successfully"
}

# Set up log rotation
setup_log_rotation() {
    log "Setting up log rotation..."
    
    cat > "/etc/logrotate.d/${APP_NAME}" << EOF
$APP_DIR/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 ieltsbot ieltsbot
    postrotate
        docker-compose -f $APP_DIR/docker-compose.yml restart > /dev/null 2>&1 || true
    endscript
}
EOF
    
    log "Log rotation configured successfully"
}

# Set up backup script
setup_backup_script() {
    log "Setting up backup script..."
    
    cat > "/usr/local/bin/${APP_NAME}-backup.sh" << 'EOF'
#!/bin/bash

APP_NAME="ielts-telegram-bot"
APP_DIR="/opt/$APP_NAME"
BACKUP_DIR="/opt/backups/$APP_NAME"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
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

echo "$(date): Backup completed: backup_$DATE.tar.gz"
EOF
    
    chmod +x "/usr/local/bin/${APP_NAME}-backup.sh"
    
    # Add to crontab
    (crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/${APP_NAME}-backup.sh >> /var/log/${APP_NAME}_backup.log 2>&1") | crontab -
    
    log "Backup script configured successfully"
}

# Set up health monitoring
setup_health_monitoring() {
    log "Setting up health monitoring..."
    
    cat > "/usr/local/bin/${APP_NAME}-health.sh" << EOF
#!/bin/bash

HEALTH_URL="http://localhost:8000/health"
LOG_FILE="/var/log/${APP_NAME}_health.log"
APP_DIR="$APP_DIR"

if curl -f -s "\$HEALTH_URL" > /dev/null; then
    echo "\$(date): Health check passed" >> "\$LOG_FILE"
else
    echo "\$(date): Health check failed - restarting application" >> "\$LOG_FILE"
    cd "\$APP_DIR"
    docker-compose restart
fi
EOF
    
    chmod +x "/usr/local/bin/${APP_NAME}-health.sh"
    
    # Add to crontab for every 5 minutes
    (crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/${APP_NAME}-health.sh") | crontab -
    
    log "Health monitoring configured successfully"
}

# Configure firewall
configure_firewall() {
    log "Configuring firewall..."
    
    # Install UFW if not present
    if ! command -v ufw >/dev/null 2>&1; then
        apt-get install -y ufw
    fi
    
    # Configure UFW rules
    ufw --force enable
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH (check current SSH port)
    local ssh_port=$(grep -E "^Port" /etc/ssh/sshd_config | awk '{print $2}' || echo "22")
    ufw allow "$ssh_port"
    
    # Allow HTTP and HTTPS
    ufw allow 80
    ufw allow 443
    
    # Allow API port (optional)
    ufw allow 8000
    
    log "Firewall configured successfully"
}

# Run health check
run_health_check() {
    log "Running health check..."
    
    # Wait a bit more for application to be fully ready
    sleep 10
    
    local health_url="http://localhost:8000/health"
    local max_attempts=12
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s "$health_url" > /dev/null 2>&1; then
            log "Health check passed on attempt $attempt"
            return 0
        fi
        
        info "Health check attempt $attempt/$max_attempts failed, retrying in 10 seconds..."
        sleep 10
        ((attempt++))
    done
    
    error "Health check failed after $max_attempts attempts"
    return 1
}

# Display deployment summary
display_summary() {
    log "Deployment completed successfully!"
    
    echo ""
    echo "=========================================="
    echo "🎉 IELTS Telegram Bot Deployment Summary"
    echo "=========================================="
    echo ""
    echo "📍 Application Directory: $APP_DIR"
    echo "🔗 Health Check URL: http://localhost:8000/health"
    echo "🔗 API URL: http://localhost:8000"
    echo "📁 Backup Directory: $BACKUP_DIR"
    echo "📋 Log File: $LOG_FILE"
    echo ""
    echo "🔧 Management Commands:"
    echo "  Start:   systemctl start $APP_NAME"
    echo "  Stop:    systemctl stop $APP_NAME"
    echo "  Restart: systemctl restart $APP_NAME"
    echo "  Status:  systemctl status $APP_NAME"
    echo "  Logs:    docker-compose -f $APP_DIR/docker-compose.yml logs -f"
    echo ""
    echo "🔍 Verification:"
    echo "  Quick:   python $APP_DIR/deploy/quick-verify.py --quick"
    echo "  Full:    $APP_DIR/deploy/verify-deployment.sh"
    echo ""
    echo "📊 Monitoring:"
    echo "  Health checks run every 5 minutes"
    echo "  Backups run daily at 2:00 AM"
    echo "  Logs rotate daily, keeping 7 days"
    echo ""
    echo "🚀 Your IELTS bot is now ready to use!"
    echo "=========================================="
    echo ""
}

# Main deployment function
main() {
    log "Starting IELTS Telegram Bot deployment..."
    log "Timestamp: $(date)"
    log "Host: $(hostname)"
    log "User: $(whoami)"
    
    # Pre-deployment checks
    check_root
    check_requirements
    
    # Install dependencies
    # install_docker
    # install_docker_compose
    
    # Set up application
    create_app_user
    create_directories
    copy_application_files
    validate_environment
    
    # Deploy application
    build_and_start
    
    # Set up system services
    setup_systemd_service
    setup_log_rotation
    setup_backup_script
    setup_health_monitoring
    configure_firewall
    
    # Verify deployment
    if run_health_check; then
        display_summary
        
        # Run verification script if available
        if [[ -f "$APP_DIR/deploy/verify-deployment.sh" ]]; then
            log "Running deployment verification..."
            bash "$APP_DIR/deploy/verify-deployment.sh" --quick
        fi
        
        return 0
    else
        error "Deployment completed but health check failed"
        error "Please check the logs and troubleshoot the issue"
        return 1
    fi
}

# Handle command line arguments
case "${1:-}" in
    --help)
        echo "IELTS Telegram Bot Deployment Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help        Show this help message"
        echo "  --force       Force deployment even if already deployed"
        echo ""
        echo "This script will:"
        echo "  1. Install Docker and Docker Compose"
        echo "  2. Create application user and directories"
        echo "  3. Copy and configure application files"
        echo "  4. Build and start the application"
        echo "  5. Set up monitoring and backups"
        echo "  6. Configure firewall and security"
        echo ""
        ;;
    --force)
        log "Force deployment requested"
        main "$@"
        ;;
    *)
        # Check if already deployed
        if [[ -d "$APP_DIR" ]] && [[ -f "$APP_DIR/docker-compose.yml" ]] && [[ "${1:-}" != "--force" ]]; then
            warn "Application appears to already be deployed at $APP_DIR"
            warn "Use --force to redeploy or run the update script instead"
            warn "Update command: $APP_DIR/deploy/update.sh"
            exit 1
        fi
        
        main "$@"
        ;;
esac