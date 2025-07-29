#!/bin/bash

# IELTS Telegram Bot Deployment Verification Script
# This script verifies that the deployment was successful and all components are working

set -e

# Configuration
APP_NAME="ielts-telegram-bot"
APP_DIR="/opt/$APP_NAME"
LOG_FILE="/var/log/${APP_NAME}_verify.log"
HEALTH_URL="http://localhost:8000/health"
API_URL="http://localhost:8000"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Logging function
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

# Test execution wrapper
run_test() {
    local test_name="$1"
    local test_function="$2"
    
    info "Running test: $test_name"
    
    if $test_function; then
        log "✓ PASS: $test_name"
        ((TESTS_PASSED++))
        return 0
    else
        error "✗ FAIL: $test_name"
        FAILED_TESTS+=("$test_name")
        ((TESTS_FAILED++))
        return 1
    fi
}

# Test 1: Check if Docker is running
test_docker_running() {
    docker --version > /dev/null 2>&1 && \
    docker info > /dev/null 2>&1
}

# Test 2: Check if application directory exists
test_app_directory() {
    [[ -d "$APP_DIR" ]] && \
    [[ -f "$APP_DIR/docker-compose.yml" ]] && \
    [[ -f "$APP_DIR/Dockerfile" ]] && \
    [[ -f "$APP_DIR/.env" ]]
}

# Test 3: Check if Docker containers are running
test_containers_running() {
    cd "$APP_DIR" 2>/dev/null || return 1
    
    local running_containers=$(docker-compose ps --services --filter "status=running" | wc -l)
    [[ $running_containers -gt 0 ]]
}

# Test 4: Check container health
test_container_health() {
    cd "$APP_DIR" 2>/dev/null || return 1
    
    # Check if container is healthy
    local health_status=$(docker-compose ps --format "table {{.Service}}\t{{.Status}}" | grep -v "SERVICE" | grep -c "healthy\|Up")
    [[ $health_status -gt 0 ]]
}

# Test 5: Check API health endpoint
test_health_endpoint() {
    local response=$(curl -s -w "%{http_code}" -o /tmp/health_response.json "$HEALTH_URL" 2>/dev/null || echo "000")
    
    if [[ "$response" == "200" ]]; then
        # Check if response contains expected fields
        if command -v jq >/dev/null 2>&1; then
            local status=$(jq -r '.status' /tmp/health_response.json 2>/dev/null || echo "unknown")
            [[ "$status" == "healthy" ]] || [[ "$status" == "unhealthy" ]]
        else
            # Basic check without jq
            grep -q '"status"' /tmp/health_response.json
        fi
    else
        return 1
    fi
}

# Test 6: Check API root endpoint
test_api_root() {
    local response=$(curl -s -w "%{http_code}" -o /tmp/root_response.json "$API_URL" 2>/dev/null || echo "000")
    [[ "$response" == "200" ]]
}

# Test 7: Check log files creation
test_log_files() {
    local log_paths=(
        "$APP_DIR/logs"
        "/app/logs"
        "./logs"
    )
    
    for log_path in "${log_paths[@]}"; do
        if [[ -d "$log_path" ]]; then
            return 0
        fi
    done
    
    return 1
}

# Test 8: Check database file
test_database_file() {
    local db_paths=(
        "$APP_DIR/data/ielts_bot.db"
        "/app/data/ielts_bot.db"
        "./data/ielts_bot.db"
    )
    
    for db_path in "${db_paths[@]}"; do
        if [[ -f "$db_path" ]]; then
            return 0
        fi
    done
    
    return 1
}

# Test 9: Check environment variables
test_environment_variables() {
    cd "$APP_DIR" 2>/dev/null || return 1
    
    # Check if .env file has required variables
    local required_vars=(
        "TELEGRAM_BOT_TOKEN"
        "OPENAI_API_KEY"
        "DATABASE_URL"
    )
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" .env 2>/dev/null; then
            return 1
        fi
        
        # Check if variable is not empty (not just =)
        if grep -q "^$var=$" .env 2>/dev/null; then
            return 1
        fi
    done
    
    return 0
}

# Test 10: Check Nginx configuration (if applicable)
test_nginx_config() {
    if command -v nginx >/dev/null 2>&1; then
        # Check if nginx is running
        if systemctl is-active --quiet nginx 2>/dev/null; then
            # Check if our site is enabled
            [[ -f "/etc/nginx/sites-enabled/$APP_NAME" ]] || [[ -f "/etc/nginx/sites-enabled/default" ]]
        else
            # Nginx not running, but that's okay for some deployments
            return 0
        fi
    else
        # Nginx not installed, skip test
        return 0
    fi
}

# Test 11: Check systemd service (if applicable)
test_systemd_service() {
    if command -v systemctl >/dev/null 2>&1; then
        if [[ -f "/etc/systemd/system/${APP_NAME}.service" ]]; then
            systemctl is-enabled "${APP_NAME}.service" >/dev/null 2>&1
        else
            # Service file doesn't exist, that's okay
            return 0
        fi
    else
        # systemctl not available, skip test
        return 0
    fi
}

# Test 12: Check firewall configuration (if applicable)
test_firewall_config() {
    if command -v ufw >/dev/null 2>&1; then
        # Check if UFW is active and allows required ports
        if ufw status | grep -q "Status: active"; then
            ufw status | grep -q "80/tcp" && ufw status | grep -q "443/tcp"
        else
            # UFW not active, that's okay
            return 0
        fi
    else
        # UFW not installed, skip test
        return 0
    fi
}

# Test 13: Check application logs for errors
test_application_logs() {
    cd "$APP_DIR" 2>/dev/null || return 1
    
    # Check recent logs for critical errors
    local recent_logs=$(docker-compose logs --tail=50 2>/dev/null || echo "")
    
    if [[ -n "$recent_logs" ]]; then
        # Check for critical errors (but allow some warnings)
        local critical_errors=$(echo "$recent_logs" | grep -i "critical\|fatal\|exception" | wc -l)
        [[ $critical_errors -eq 0 ]]
    else
        # No logs available, might be too early
        return 0
    fi
}

# Test 14: Check disk space
test_disk_space() {
    # Check if we have at least 1GB free space
    local free_space=$(df / | awk 'NR==2 {print $4}')
    [[ $free_space -gt 1048576 ]] # 1GB in KB
}

# Test 15: Check memory usage
test_memory_usage() {
    # Check if system has reasonable memory available
    local available_memory=$(free -m | awk 'NR==2{printf "%.0f", $7}')
    [[ $available_memory -gt 100 ]] # At least 100MB available
}

# Performance test: Response time
test_response_time() {
    local start_time=$(date +%s%N)
    curl -s "$HEALTH_URL" > /dev/null 2>&1
    local end_time=$(date +%s%N)
    
    local response_time=$(( (end_time - start_time) / 1000000 )) # Convert to milliseconds
    
    info "Health endpoint response time: ${response_time}ms"
    
    # Response should be under 5 seconds (5000ms)
    [[ $response_time -lt 5000 ]]
}

# Main verification function
main() {
    log "Starting IELTS Telegram Bot deployment verification..."
    log "Timestamp: $(date)"
    log "Host: $(hostname)"
    
    # Infrastructure tests
    run_test "Docker Installation" test_docker_running
    run_test "Application Directory" test_app_directory
    run_test "Environment Variables" test_environment_variables
    
    # Application tests
    run_test "Docker Containers Running" test_containers_running
    run_test "Container Health" test_container_health
    run_test "Database File" test_database_file
    run_test "Log Files" test_log_files
    
    # API tests
    run_test "Health Endpoint" test_health_endpoint
    run_test "API Root Endpoint" test_api_root
    run_test "Response Time" test_response_time
    
    # System tests
    run_test "Application Logs" test_application_logs
    run_test "Disk Space" test_disk_space
    run_test "Memory Usage" test_memory_usage
    
    # Optional system configuration tests
    run_test "Nginx Configuration" test_nginx_config
    run_test "Systemd Service" test_systemd_service
    run_test "Firewall Configuration" test_firewall_config
    
    # Summary
    local total_tests=$((TESTS_PASSED + TESTS_FAILED))
    
    log "Verification completed!"
    log "Results: $TESTS_PASSED/$total_tests tests passed"
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        log "🎉 All tests passed! Deployment is successful."
        
        # Display application info
        info "Application Information:"
        info "- Health Check: $HEALTH_URL"
        info "- API Endpoint: $API_URL"
        info "- Application Directory: $APP_DIR"
        
        # Show current status
        if cd "$APP_DIR" 2>/dev/null; then
            info "- Container Status:"
            docker-compose ps 2>/dev/null | head -10
        fi
        
        return 0
    else
        error "❌ $TESTS_FAILED tests failed!"
        error "Failed tests:"
        for test in "${FAILED_TESTS[@]}"; do
            error "  - $test"
        done
        
        warn "Please check the logs and fix the issues before proceeding."
        return 1
    fi
}

# Cleanup function
cleanup() {
    rm -f /tmp/health_response.json /tmp/root_response.json
}

# Set up cleanup trap
trap cleanup EXIT

# Handle command line arguments
case "${1:-}" in
    --quick)
        log "Running quick verification (essential tests only)..."
        run_test "Docker Containers Running" test_containers_running
        run_test "Health Endpoint" test_health_endpoint
        run_test "Environment Variables" test_environment_variables
        
        if [[ $TESTS_FAILED -eq 0 ]]; then
            log "✓ Quick verification passed!"
        else
            error "✗ Quick verification failed!"
            exit 1
        fi
        ;;
    --health-only)
        log "Checking health endpoint only..."
        if test_health_endpoint; then
            log "✓ Health endpoint is responding"
            curl -s "$HEALTH_URL" | head -5
        else
            error "✗ Health endpoint is not responding"
            exit 1
        fi
        ;;
    --help)
        echo "IELTS Telegram Bot Deployment Verification Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --quick       Run only essential tests"
        echo "  --health-only Check only the health endpoint"
        echo "  --help        Show this help message"
        echo ""
        echo "Default: Run all verification tests"
        ;;
    *)
        main "$@"
        ;;
esac