#!/bin/bash

# Simplified IELTS Telegram Bot Deployment Script
# This script handles deployment on an already configured server

set -e

# Configuration
APP_NAME="ielts-telegram-bot"
APP_DIR="/opt/$APP_NAME"
LOG_FILE="/var/log/${APP_NAME}_deploy.log"

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

# Create directory structure
create_directories() {
    log "Creating directory structure..."
    
    # Create main directories
    mkdir -p "$APP_DIR"
    mkdir -p "$APP_DIR/data"
    mkdir -p "$APP_DIR/logs"
    
    # Create log directory
    mkdir -p /var/log
    
    log "Directory structure created successfully"
}

# Copy application files
copy_application_files() {
    log "Copying application files..."
    
    local source_dir=$(pwd)
    
    # Copy main application files
    cp -r "$source_dir/src" "$APP_DIR/"
    cp "$source_dir/requirements.txt" "$APP_DIR/"
    cp "$source_dir/Dockerfile" "$APP_DIR/"
    cp "$source_dir/docker-compose.yml" "$APP_DIR/"
    cp "$source_dir/main.py" "$APP_DIR/"
    
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
    
    warn "Health check failed after $max_attempts attempts, but continuing..."
    return 0
}

# Display deployment summary
display_summary() {
    log "Deployment completed!"
    
    echo ""
    echo "=========================================="
    echo "🎉 IELTS Telegram Bot Deployed"
    echo "=========================================="
    echo ""
    echo "📍 Application Directory: $APP_DIR"
    echo "🔗 Health Check URL: http://localhost:8000/health"
    echo ""
    echo "🔧 Management Commands:"
    echo "  Logs:    docker-compose -f $APP_DIR/docker-compose.yml logs -f"
    echo "  Status:  docker-compose -f $APP_DIR/docker-compose.yml ps"
    echo "  Stop:    docker-compose -f $APP_DIR/docker-compose.yml down"
    echo "  Start:   docker-compose -f $APP_DIR/docker-compose.yml up -d"
    echo ""
    echo "🚀 Your IELTS bot should now be running!"
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
    
    # Set up application
    create_directories
    copy_application_files
    validate_environment
    
    # Deploy application
    build_and_start
    
    # Verify deployment
    run_health_check
    display_summary
    
    return 0
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
        ;;
    --force)
        log "Force deployment requested"
        main "$@"
        ;;
    *)
        main "$@"
        ;;
esac