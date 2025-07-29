#!/bin/bash

# IELTS Telegram Bot Update Script
# This script handles updates for existing deployments

set -e

# Configuration
APP_NAME="ielts-telegram-bot"
APP_DIR="/opt/$APP_NAME"
BACKUP_DIR="/opt/backups/$APP_NAME"
LOG_FILE="/var/log/${APP_NAME}_update.log"

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

# Check if application is deployed
check_deployment() {
    if [[ ! -d "$APP_DIR" ]]; then
        error "Application not found at $APP_DIR"
        error "Please run the deployment script first: ./deploy/deploy.sh"
        exit 1
    fi
    
    if [[ ! -f "$APP_DIR/docker-compose.yml" ]]; then
        error "Docker Compose file not found. Invalid deployment."
        exit 1
    fi
    
    log "Existing deployment found at $APP_DIR"
}

# Create backup before update
create_backup() {
    log "Creating backup before update..."
    
    local backup_name="pre_update_$(date +%Y%m%d_%H%M%S)"
    local backup_path="$BACKUP_DIR/$backup_name.tar.gz"
    
    mkdir -p "$BACKUP_DIR"
    
    cd "$APP_DIR"
    tar -czf "$backup_path" \
        data/ \
        logs/ \
        .env \
        docker-compose.yml \
        src/ 2>/dev/null || true
    
    if [[ -f "$backup_path" ]]; then
        log "Backup created: $backup_path"
        echo "$backup_path" > /tmp/last_backup_path
    else
        error "Failed to create backup"
        exit 1
    fi
}

# Check for updates
check_for_updates() {
    log "Checking for updates..."
    
    local source_dir=$(pwd)
    
    if [[ ! -d "$source_dir/.git" ]]; then
        warn "Not a git repository. Cannot check for updates automatically."
        return 0
    fi
    
    # Fetch latest changes
    cd "$source_dir"
    git fetch origin
    
    # Check if updates are available
    local local_commit=$(git rev-parse HEAD)
    local remote_commit=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master 2>/dev/null)
    
    if [[ "$local_commit" == "$remote_commit" ]]; then
        log "No updates available. Current version is up to date."
        return 1
    else
        log "Updates available:"
        git log --oneline "$local_commit..$remote_commit" | head -5
        return 0
    fi
}

# Update application code
update_code() {
    log "Updating application code..."
    
    local source_dir=$(pwd)
    
    # Update source code
    if [[ -d "$source_dir/.git" ]]; then
        cd "$source_dir"
        git pull origin main 2>/dev/null || git pull origin master 2>/dev/null
        log "Code updated from repository"
    else
        warn "Not a git repository. Copying files from current directory."
    fi
    
    # Copy updated files
    log "Copying updated files to $APP_DIR..."
    
    # Preserve environment file
    if [[ -f "$APP_DIR/.env" ]]; then
        cp "$APP_DIR/.env" /tmp/env_backup
    fi
    
    # Copy application files
    cp -r "$source_dir/src" "$APP_DIR/"
    cp -r "$source_dir/tests" "$APP_DIR/"
    cp "$source_dir/requirements.txt" "$APP_DIR/"
    cp "$source_dir/Dockerfile" "$APP_DIR/"
    cp "$source_dir/docker-compose.yml" "$APP_DIR/"
    cp "$source_dir/pytest.ini" "$APP_DIR/"
    
    # Copy deployment files
    cp -r "$source_dir/deploy" "$APP_DIR/"
    
    # Restore environment file
    if [[ -f /tmp/env_backup ]]; then
        cp /tmp/env_backup "$APP_DIR/.env"
        rm /tmp/env_backup
    fi
    
    # Set permissions
    chown -R ieltsbot:ieltsbot "$APP_DIR"
    
    log "Application code updated successfully"
}

# Stop application
stop_application() {
    log "Stopping application..."
    
    cd "$APP_DIR"
    
    if docker-compose ps -q 2>/dev/null | grep -q .; then
        docker-compose down
        log "Application stopped"
    else
        log "Application was not running"
    fi
}

# Build and start updated application
build_and_start() {
    log "Building and starting updated application..."
    
    cd "$APP_DIR"
    
    # Build new images
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
        return 1
    fi
    
    log "Application started successfully"
    return 0
}

# Run health check
run_health_check() {
    log "Running health check..."
    
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

# Rollback to previous version
rollback() {
    log "Rolling back to previous version..."
    
    if [[ ! -f /tmp/last_backup_path ]]; then
        error "No backup path found. Cannot rollback."
        exit 1
    fi
    
    local backup_path=$(cat /tmp/last_backup_path)
    
    if [[ ! -f "$backup_path" ]]; then
        error "Backup file not found: $backup_path"
        exit 1
    fi
    
    # Stop current application
    cd "$APP_DIR"
    docker-compose down 2>/dev/null || true
    
    # Restore from backup
    log "Restoring from backup: $backup_path"
    cd "$APP_DIR"
    tar -xzf "$backup_path"
    
    # Start application
    docker-compose up -d
    
    # Wait and check health
    sleep 30
    if run_health_check; then
        log "Rollback completed successfully"
    else
        error "Rollback completed but health check failed"
        exit 1
    fi
}

# Clean up old Docker images
cleanup_docker() {
    log "Cleaning up old Docker images..."
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused containers
    docker container prune -f
    
    log "Docker cleanup completed"
}

# Display update summary
display_summary() {
    log "Update completed successfully!"
    
    echo ""
    echo "=========================================="
    echo "🎉 IELTS Telegram Bot Update Summary"
    echo "=========================================="
    echo ""
    echo "📍 Application Directory: $APP_DIR"
    echo "🔗 Health Check URL: http://localhost:8000/health"
    echo "🔗 API URL: http://localhost:8000"
    echo "📋 Update Log: $LOG_FILE"
    echo ""
    echo "🔧 Management Commands:"
    echo "  Status:  systemctl status $APP_NAME"
    echo "  Logs:    docker-compose -f $APP_DIR/docker-compose.yml logs -f"
    echo "  Health:  curl http://localhost:8000/health"
    echo ""
    echo "🔍 Verification:"
    echo "  Quick:   python $APP_DIR/deploy/quick-verify.py --quick"
    echo "  Full:    $APP_DIR/deploy/verify-deployment.sh"
    echo ""
    echo "🚀 Your IELTS bot has been updated successfully!"
    echo "=========================================="
    echo ""
}

# Main update function
main() {
    local check_only=false
    local force_update=false
    local skip_backup=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --check-only)
                check_only=true
                shift
                ;;
            --force)
                force_update=true
                shift
                ;;
            --skip-backup)
                skip_backup=true
                shift
                ;;
            --rollback)
                check_root
                check_deployment
                rollback
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    log "Starting IELTS Telegram Bot update..."
    log "Timestamp: $(date)"
    log "Host: $(hostname)"
    log "User: $(whoami)"
    
    # Pre-update checks
    check_root
    check_deployment
    
    # Check for updates
    if ! check_for_updates && [[ "$force_update" != true ]]; then
        if [[ "$check_only" == true ]]; then
            log "Check completed: No updates available"
            exit 0
        else
            log "No updates available. Use --force to update anyway."
            exit 0
        fi
    fi
    
    if [[ "$check_only" == true ]]; then
        log "Check completed: Updates are available"
        exit 0
    fi
    
    # Perform update
    if [[ "$skip_backup" != true ]]; then
        create_backup
    fi
    
    update_code
    stop_application
    
    if build_and_start; then
        if run_health_check; then
            cleanup_docker
            display_summary
            
            # Run verification script if available
            if [[ -f "$APP_DIR/deploy/verify-deployment.sh" ]]; then
                log "Running deployment verification..."
                bash "$APP_DIR/deploy/verify-deployment.sh" --quick
            fi
            
            log "Update completed successfully"
        else
            error "Update completed but health check failed"
            warn "Consider rolling back with: $0 --rollback"
            exit 1
        fi
    else
        error "Failed to start updated application"
        warn "Consider rolling back with: $0 --rollback"
        exit 1
    fi
}

# Handle command line arguments
case "${1:-}" in
    --help)
        echo "IELTS Telegram Bot Update Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help         Show this help message"
        echo "  --check-only   Check for updates without applying them"
        echo "  --force        Force update even if no updates detected"
        echo "  --skip-backup  Skip backup creation (not recommended)"
        echo "  --rollback     Rollback to previous version"
        echo ""
        echo "Examples:"
        echo "  $0                    # Update if updates are available"
        echo "  $0 --check-only      # Check for updates only"
        echo "  $0 --force           # Force update"
        echo "  $0 --rollback        # Rollback to previous version"
        echo ""
        ;;
    *)
        main "$@"
        ;;
esac