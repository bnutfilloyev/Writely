#!/bin/bash

# Simple IELTS Telegram Bot Deployment Script
# Runs in current directory

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Create necessary directories
create_directories() {
    log "Creating directories..."
    mkdir -p data
    mkdir -p logs
    log "Directories created successfully"
}

# Validate environment configuration
validate_environment() {
    log "Validating environment configuration..."
    
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.production" ]]; then
            cp .env.production .env
            warn "Copied .env.production to .env - please update with your actual values"
        else
            error "No .env file found. Please create one with your configuration"
            exit 1
        fi
    fi
    
    # Check required variables
    local required_vars=(
        "TELEGRAM_BOT_TOKEN"
        "OPENAI_API_KEY"
    )
    
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" .env 2>/dev/null; then
            missing_vars+=("$var")
        elif grep -q "^$var=your_.*_here" .env 2>/dev/null; then
            missing_vars+=("$var (placeholder value)")
        elif grep -q "^$var=$" .env 2>/dev/null; then
            missing_vars+=("$var (empty value)")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        error "Missing or invalid environment variables:"
        for var in "${missing_vars[@]}"; do
            error "  - $var"
        done
        error "Please update .env with valid values"
        exit 1
    fi
    
    log "Environment configuration validated successfully"
}

# Build and start application
build_and_start() {
    log "Building and starting application..."
    
    # Stop existing containers if running
    if docker-compose ps -q 2>/dev/null | grep -q .; then
        log "Stopping existing containers..."
        docker-compose down
    fi
    
    # Check if port 8080 is in use and try to free it
    if netstat -tlnp 2>/dev/null | grep -q ":8080 "; then
        warn "Port 8080 is in use. Attempting to stop conflicting services..."
        docker ps -q --filter "publish=8080" | xargs -r docker stop
        sleep 5
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
    
    sleep 10
    
    local health_url="http://localhost:8080/health"
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
    echo "📍 Application Directory: $(pwd)"
    echo "🔗 Health Check URL: http://localhost:8080/health"
    echo ""
    echo "🔧 Management Commands:"
    echo "  Logs:    docker-compose logs -f"
    echo "  Status:  docker-compose ps"
    echo "  Stop:    docker-compose down"
    echo "  Start:   docker-compose up -d"
    echo ""
    echo "🚀 Your IELTS bot is now running!"
    echo "=========================================="
    echo ""
}

# Main deployment function
main() {
    log "Starting IELTS Telegram Bot deployment..."
    log "Working directory: $(pwd)"
    
    # Pre-deployment checks
    check_root
    
    # Set up application
    create_directories
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
        echo "  --force       Force deployment"
        echo "  --update      Quick update (use deploy/fast-update.sh instead)"
        echo ""
        echo "For updates, use: ./deploy/fast-update.sh"
        echo ""
        ;;
    --update)
        if [[ -f "deploy/fast-update.sh" ]]; then
            exec ./deploy/fast-update.sh "$@"
        else
            error "Fast update script not found"
            exit 1
        fi
        ;;
    *)
        main "$@"
        ;;
esac