#!/bin/bash

# Fast Update Script for IELTS Telegram Bot
# Quick updates without full rebuild

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ERROR: $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')] INFO: $1${NC}"
}

# Check if Docker Compose is running
check_running() {
    if ! docker-compose ps -q 2>/dev/null | grep -q .; then
        error "Application is not running. Use ./deploy/deploy.sh to start it first."
        exit 1
    fi
}

# Pull latest code
pull_code() {
    log "Pulling latest code..."
    
    if [[ -d ".git" ]]; then
        git fetch origin
        local local_commit=$(git rev-parse HEAD)
        local remote_commit=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master 2>/dev/null)
        
        if [[ "$local_commit" == "$remote_commit" ]]; then
            log "Already up to date"
            return 1
        fi
        
        git pull origin main 2>/dev/null || git pull origin master 2>/dev/null
        log "Code updated"
        return 0
    else
        warn "Not a git repository - skipping code pull"
        return 0
    fi
}

# Fast restart without rebuild
fast_restart() {
    log "Performing fast restart..."
    
    # Just restart containers without rebuilding
    docker-compose restart
    
    # Wait a moment for startup
    sleep 10
    
    log "Fast restart completed"
}

# Full update with rebuild
full_update() {
    log "Performing full update with rebuild..."
    
    # Stop containers
    docker-compose down
    
    # Rebuild and start
    docker-compose build --no-cache
    docker-compose up -d
    
    # Wait for startup
    sleep 30
    
    log "Full update completed"
}

# Quick health check
health_check() {
    log "Running quick health check..."
    
    local health_url="http://localhost:8080/health"
    local max_attempts=6
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s "$health_url" > /dev/null 2>&1; then
            log "✅ Health check passed"
            return 0
        fi
        
        info "Health check attempt $attempt/$max_attempts..."
        sleep 5
        ((attempt++))
    done
    
    warn "⚠️  Health check failed - check logs with: docker-compose logs"
    return 1
}

# Show status
show_status() {
    echo ""
    echo "🔍 Current Status:"
    docker-compose ps
    echo ""
    echo "📊 Resource Usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
    echo ""
}

# Show logs
show_logs() {
    local lines=${1:-50}
    echo ""
    echo "📋 Recent Logs (last $lines lines):"
    docker-compose logs --tail="$lines"
}

# Main function
main() {
    local mode="auto"
    local show_logs_flag=false
    local log_lines=50
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --fast)
                mode="fast"
                shift
                ;;
            --full)
                mode="full"
                shift
                ;;
            --status)
                mode="status"
                shift
                ;;
            --logs)
                show_logs_flag=true
                shift
                ;;
            --logs=*)
                show_logs_flag=true
                log_lines="${1#*=}"
                shift
                ;;
            --help)
                echo "Fast Update Script for IELTS Telegram Bot"
                echo ""
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --fast      Fast restart without rebuild (default if no code changes)"
                echo "  --full      Full update with rebuild (default if code changes detected)"
                echo "  --status    Show current status and exit"
                echo "  --logs      Show recent logs"
                echo "  --logs=N    Show last N lines of logs"
                echo "  --help      Show this help"
                echo ""
                echo "Examples:"
                echo "  $0                # Auto-detect update type needed"
                echo "  $0 --fast         # Quick restart only"
                echo "  $0 --full         # Full rebuild and restart"
                echo "  $0 --status       # Show status"
                echo "  $0 --logs=100     # Show last 100 log lines"
                echo ""
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    log "🚀 Fast Update Tool"
    
    # Show status if requested
    if [[ "$mode" == "status" ]]; then
        check_running
        show_status
        if [[ "$show_logs_flag" == true ]]; then
            show_logs "$log_lines"
        fi
        exit 0
    fi
    
    # Show logs if requested
    if [[ "$show_logs_flag" == true && "$mode" == "auto" ]]; then
        check_running
        show_logs "$log_lines"
        exit 0
    fi
    
    # Check if application is running
    check_running
    
    # Determine update type
    local code_updated=false
    if [[ "$mode" == "auto" ]]; then
        if pull_code; then
            code_updated=true
            mode="full"
        else
            mode="fast"
        fi
    elif [[ "$mode" == "full" ]]; then
        pull_code || true
        code_updated=true
    fi
    
    # Perform update
    case "$mode" in
        "fast")
            log "🔄 Performing fast restart..."
            fast_restart
            ;;
        "full")
            log "🔨 Performing full update..."
            full_update
            ;;
    esac
    
    # Health check
    health_check
    
    # Show final status
    show_status
    
    if [[ "$show_logs_flag" == true ]]; then
        show_logs "$log_lines"
    fi
    
    log "✅ Update completed successfully!"
    
    if [[ "$code_updated" == true ]]; then
        info "💡 Code was updated - consider running tests if available"
    fi
}

# Run main function
main "$@"