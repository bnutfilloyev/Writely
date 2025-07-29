#!/bin/bash

# IELTS Telegram Bot Initial Setup Script
# This script prepares a fresh server for deployment

set -e  # Exit on any error

# Configuration
APP_NAME="ielts-telegram-bot"
PYTHON_VERSION="3.11"
NODE_VERSION="18"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get >/dev/null 2>&1; then
            OS="ubuntu"
        elif command -v yum >/dev/null 2>&1; then
            OS="centos"
        else
            OS="linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        OS="unknown"
    fi
    
    log "Detected OS: $OS"
}

# Check if running as root (for Linux)
check_permissions() {
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "centos" ]]; then
        if [[ $EUID -ne 0 ]] && [[ -z "$SUDO_USER" ]]; then
            error "This script must be run as root or with sudo on Linux"
        fi
    fi
}

# Update system packages
update_system() {
    log "Updating system packages..."
    
    case $OS in
        ubuntu)
            apt-get update
            apt-get upgrade -y
            ;;
        centos)
            yum update -y
            ;;
        macos)
            if command -v brew >/dev/null 2>&1; then
                brew update
                brew upgrade
            else
                warn "Homebrew not found. Please install it manually."
            fi
            ;;
        *)
            warn "Unknown OS. Skipping system update."
            ;;
    esac
}

# Install Python
install_python() {
    log "Installing Python $PYTHON_VERSION..."
    
    if command -v python3 >/dev/null 2>&1; then
        local current_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
        if [[ "$current_version" == "$PYTHON_VERSION" ]]; then
            log "Python $PYTHON_VERSION already installed"
            return
        fi
    fi
    
    case $OS in
        ubuntu)
            apt-get install -y software-properties-common
            add-apt-repository -y ppa:deadsnakes/ppa
            apt-get update
            apt-get install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-pip python${PYTHON_VERSION}-dev
            
            # Create symlinks
            update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1
            update-alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip${PYTHON_VERSION} 1
            ;;
        centos)
            yum install -y python${PYTHON_VERSION//.} python${PYTHON_VERSION//.}-pip python${PYTHON_VERSION//.}-devel
            ;;
        macos)
            if command -v brew >/dev/null 2>&1; then
                brew install python@${PYTHON_VERSION}
            else
                error "Please install Python $PYTHON_VERSION manually on macOS"
            fi
            ;;
        *)
            error "Cannot install Python on unknown OS"
            ;;
    esac
    
    # Verify installation
    python3 --version || error "Python installation failed"
    pip3 --version || error "Pip installation failed"
}

# Install Docker
install_docker() {
    log "Installing Docker..."
    
    if command -v docker >/dev/null 2>&1; then
        log "Docker already installed"
        return
    fi
    
    case $OS in
        ubuntu)
            # Install Docker's official GPG key
            apt-get install -y ca-certificates curl gnupg
            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            chmod a+r /etc/apt/keyrings/docker.gpg
            
            # Add Docker repository
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
            
            # Install Docker
            apt-get update
            apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        centos)
            yum install -y yum-utils
            yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        macos)
            if command -v brew >/dev/null 2>&1; then
                brew install --cask docker
                warn "Please start Docker Desktop manually on macOS"
            else
                error "Please install Docker Desktop manually on macOS"
            fi
            ;;
        *)
            error "Cannot install Docker on unknown OS"
            ;;
    esac
    
    # Start and enable Docker (Linux only)
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "centos" ]]; then
        systemctl start docker
        systemctl enable docker
        
        # Add user to docker group
        if [[ -n "$SUDO_USER" ]]; then
            usermod -aG docker "$SUDO_USER"
            log "Added $SUDO_USER to docker group"
        fi
    fi
    
    # Verify installation
    docker --version || error "Docker installation failed"
}

# Install Docker Compose (if not included with Docker)
install_docker_compose() {
    log "Checking Docker Compose..."
    
    if docker compose version >/dev/null 2>&1; then
        log "Docker Compose already available"
        return
    fi
    
    if command -v docker-compose >/dev/null 2>&1; then
        log "Docker Compose (standalone) already installed"
        return
    fi
    
    log "Installing Docker Compose..."
    
    case $OS in
        ubuntu|centos)
            # Install standalone docker-compose
            local compose_version=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
            curl -L "https://github.com/docker/compose/releases/download/${compose_version}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose
            ;;
        macos)
            if command -v brew >/dev/null 2>&1; then
                brew install docker-compose
            else
                error "Please install Docker Compose manually on macOS"
            fi
            ;;
        *)
            error "Cannot install Docker Compose on unknown OS"
            ;;
    esac
    
    # Verify installation
    docker-compose --version || docker compose version || error "Docker Compose installation failed"
}

# Install Git
install_git() {
    log "Installing Git..."
    
    if command -v git >/dev/null 2>&1; then
        log "Git already installed"
        return
    fi
    
    case $OS in
        ubuntu)
            apt-get install -y git
            ;;
        centos)
            yum install -y git
            ;;
        macos)
            if command -v brew >/dev/null 2>&1; then
                brew install git
            else
                # Git should be available via Xcode Command Line Tools
                xcode-select --install 2>/dev/null || true
            fi
            ;;
        *)
            error "Cannot install Git on unknown OS"
            ;;
    esac
    
    # Verify installation
    git --version || error "Git installation failed"
}

# Install additional tools
install_tools() {
    log "Installing additional tools..."
    
    case $OS in
        ubuntu)
            apt-get install -y \
                curl \
                wget \
                unzip \
                vim \
                htop \
                tree \
                jq \
                build-essential \
                libssl-dev \
                libffi-dev \
                sqlite3
            ;;
        centos)
            yum install -y \
                curl \
                wget \
                unzip \
                vim \
                htop \
                tree \
                jq \
                gcc \
                openssl-devel \
                libffi-devel \
                sqlite
            ;;
        macos)
            if command -v brew >/dev/null 2>&1; then
                brew install curl wget unzip vim htop tree jq sqlite3
            fi
            ;;
        *)
            warn "Skipping additional tools installation on unknown OS"
            ;;
    esac
}

# Setup firewall (Linux only)
setup_firewall() {
    if [[ "$OS" != "ubuntu" ]] && [[ "$OS" != "centos" ]]; then
        log "Skipping firewall setup on $OS"
        return
    fi
    
    log "Setting up firewall..."
    
    case $OS in
        ubuntu)
            # Install and configure UFW
            apt-get install -y ufw
            
            # Reset UFW to defaults
            ufw --force reset
            
            # Set default policies
            ufw default deny incoming
            ufw default allow outgoing
            
            # Allow SSH
            ufw allow ssh
            ufw allow 22/tcp
            
            # Allow HTTP and HTTPS
            ufw allow 80/tcp
            ufw allow 443/tcp
            
            # Allow application port
            ufw allow 8000/tcp
            
            # Enable firewall
            ufw --force enable
            
            log "UFW firewall configured and enabled"
            ;;
        centos)
            # Configure firewalld
            systemctl start firewalld
            systemctl enable firewalld
            
            # Allow services
            firewall-cmd --permanent --add-service=ssh
            firewall-cmd --permanent --add-service=http
            firewall-cmd --permanent --add-service=https
            firewall-cmd --permanent --add-port=8000/tcp
            
            # Reload firewall
            firewall-cmd --reload
            
            log "Firewalld configured and enabled"
            ;;
    esac
}

# Create application user (Linux only)
create_app_user() {
    if [[ "$OS" != "ubuntu" ]] && [[ "$OS" != "centos" ]]; then
        log "Skipping app user creation on $OS"
        return
    fi
    
    log "Creating application user..."
    
    # Create user if it doesn't exist
    if ! id "$APP_NAME" >/dev/null 2>&1; then
        useradd -r -s /bin/bash -d "/opt/$APP_NAME" -m "$APP_NAME"
        log "Created user: $APP_NAME"
    else
        log "User $APP_NAME already exists"
    fi
    
    # Add to docker group
    usermod -aG docker "$APP_NAME" 2>/dev/null || warn "Could not add $APP_NAME to docker group"
}

# Setup directories
setup_directories() {
    log "Setting up directories..."
    
    local base_dir
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "centos" ]]; then
        base_dir="/opt/$APP_NAME"
    else
        base_dir="$HOME/$APP_NAME"
    fi
    
    # Create directories
    mkdir -p "$base_dir"
    mkdir -p "$base_dir/data"
    mkdir -p "$base_dir/logs"
    mkdir -p "/opt/backups/$APP_NAME" 2>/dev/null || mkdir -p "$HOME/backups/$APP_NAME"
    
    # Set permissions (Linux only)
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "centos" ]]; then
        chown -R "$APP_NAME:$APP_NAME" "$base_dir" 2>/dev/null || true
        chmod -R 755 "$base_dir"
    fi
    
    log "Directories created: $base_dir"
}

# Install Nginx (optional)
install_nginx() {
    if [[ "${INSTALL_NGINX:-false}" != "true" ]]; then
        log "Skipping Nginx installation (set INSTALL_NGINX=true to enable)"
        return
    fi
    
    log "Installing Nginx..."
    
    case $OS in
        ubuntu)
            apt-get install -y nginx
            systemctl start nginx
            systemctl enable nginx
            ;;
        centos)
            yum install -y nginx
            systemctl start nginx
            systemctl enable nginx
            ;;
        macos)
            if command -v brew >/dev/null 2>&1; then
                brew install nginx
                brew services start nginx
            fi
            ;;
        *)
            warn "Cannot install Nginx on unknown OS"
            return
            ;;
    esac
    
    log "Nginx installed and started"
}

# Setup SSL certificates (optional)
setup_ssl() {
    if [[ "${SETUP_SSL:-false}" != "true" ]] || [[ -z "${DOMAIN:-}" ]]; then
        log "Skipping SSL setup (set SETUP_SSL=true and DOMAIN=your-domain.com to enable)"
        return
    fi
    
    log "Setting up SSL certificates for $DOMAIN..."
    
    case $OS in
        ubuntu)
            # Install Certbot
            apt-get install -y certbot python3-certbot-nginx
            
            # Get certificate
            certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "${EMAIL:-admin@$DOMAIN}"
            
            # Setup auto-renewal
            (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
            ;;
        centos)
            # Install Certbot
            yum install -y certbot python3-certbot-nginx
            
            # Get certificate
            certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "${EMAIL:-admin@$DOMAIN}"
            
            # Setup auto-renewal
            (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
            ;;
        *)
            warn "SSL setup not supported on $OS"
            ;;
    esac
}

# Create environment file template
create_env_template() {
    log "Creating environment file template..."
    
    local base_dir
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "centos" ]]; then
        base_dir="/opt/$APP_NAME"
    else
        base_dir="$HOME/$APP_NAME"
    fi
    
    cat > "$base_dir/.env.template" << 'EOF'
# IELTS Telegram Bot Configuration
# Copy this file to .env and update with your actual values

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# OpenRouter Configuration (AI Service)
OPENAI_API_KEY=your_openrouter_api_key_here
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
EOF
    
    log "Environment template created at $base_dir/.env.template"
}

# Display setup summary
display_summary() {
    log "Setup completed successfully!"
    
    local base_dir
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "centos" ]]; then
        base_dir="/opt/$APP_NAME"
    else
        base_dir="$HOME/$APP_NAME"
    fi
    
    info "Setup Summary:"
    info "- OS: $OS"
    info "- Python: $(python3 --version 2>/dev/null || echo 'Not installed')"
    info "- Docker: $(docker --version 2>/dev/null || echo 'Not installed')"
    info "- Git: $(git --version 2>/dev/null || echo 'Not installed')"
    info "- Application directory: $base_dir"
    
    warn "Next steps:"
    warn "1. Clone your application repository to $base_dir"
    warn "2. Copy $base_dir/.env.template to $base_dir/.env"
    warn "3. Update .env with your actual API keys and configuration"
    warn "4. Run the deployment script: $base_dir/deploy/deploy.sh"
    
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "centos" ]]; then
        warn "5. You may need to log out and back in for Docker group membership to take effect"
    fi
}

# Main setup function
main() {
    log "Starting IELTS Telegram Bot setup..."
    log "This will install and configure all required dependencies"
    
    detect_os
    check_permissions
    
    # Core installations
    update_system
    install_python
    install_git
    install_docker
    install_docker_compose
    install_tools
    
    # System configuration
    setup_firewall
    create_app_user
    setup_directories
    
    # Optional components
    install_nginx
    setup_ssl
    
    # Final setup
    create_env_template
    display_summary
    
    log "Setup script completed!"
}

# Handle command line arguments
case "${1:-}" in
    --help)
        echo "IELTS Telegram Bot Setup Script"
        echo ""
        echo "This script prepares a server for deploying the IELTS Telegram Bot"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help        Show this help message"
        echo ""
        echo "Environment Variables:"
        echo "  INSTALL_NGINX=true    Install and configure Nginx"
        echo "  SETUP_SSL=true        Setup SSL certificates (requires DOMAIN)"
        echo "  DOMAIN=example.com    Domain name for SSL certificates"
        echo "  EMAIL=admin@domain    Email for SSL certificate registration"
        echo ""
        echo "Examples:"
        echo "  sudo ./setup.sh"
        echo "  sudo INSTALL_NGINX=true ./setup.sh"
        echo "  sudo INSTALL_NGINX=true SETUP_SSL=true DOMAIN=bot.example.com ./setup.sh"
        ;;
    *)
        main "$@"
        ;;
esac