#!/bin/bash

# Audio Enhancer Deployment Check Script
# This script checks the deployment status of the bahmann-audio-enhancer

echo "======================================"
echo "Audio Enhancer Deployment Check Script"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

# Function to print info
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Check if Docker is installed and running
echo -e "${BLUE}1. Docker Status${NC}"
echo "----------------"
if command -v docker &> /dev/null; then
    print_status 0 "Docker is installed"
    docker_version=$(docker --version)
    print_info "Version: $docker_version"
    
    if docker info &> /dev/null; then
        print_status 0 "Docker daemon is running"
    else
        print_status 1 "Docker daemon is not running"
        print_warning "Please start Docker with: sudo systemctl start docker"
    fi
else
    print_status 1 "Docker is not installed"
    print_warning "Please install Docker first"
fi
echo ""

# 2. Check container status
echo -e "${BLUE}2. Container Status${NC}"
echo "-------------------"
container_name="bahmann-audio-enhancer"
container_status=$(docker ps --filter "name=$container_name" --format "{{.Status}}" 2>/dev/null)

if [ -n "$container_status" ]; then
    print_status 0 "Container '$container_name' is running"
    print_info "Status: $container_status"
    
    # Get container ID
    container_id=$(docker ps -q --filter "name=$container_name")
    
    # Show container details
    echo ""
    echo "Container details:"
    docker ps --filter "name=$container_name" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | tail -n +1
else
    print_status 1 "Container '$container_name' is not running"
    
    # Check if container exists but is stopped
    if docker ps -a --filter "name=$container_name" | grep -q "$container_name"; then
        print_warning "Container exists but is stopped"
        print_info "Try starting it with: docker start $container_name"
    else
        print_warning "Container does not exist"
        print_info "Deploy the application first"
    fi
fi
echo ""

# 3. Check port mappings
echo -e "${BLUE}3. Port Mappings${NC}"
echo "----------------"
if [ -n "$container_id" ]; then
    port_mappings=$(docker port $container_name 2>/dev/null)
    if [ -n "$port_mappings" ]; then
        print_status 0 "Port mappings configured"
        echo "$port_mappings" | while read line; do
            print_info "$line"
        done
        
        # Check if ports are actually listening
        echo ""
        echo "Checking port availability:"
        for port in 8002 8443; do
            if netstat -tuln 2>/dev/null | grep -q ":$port "; then
                print_status 0 "Port $port is listening"
            else
                print_warning "Port $port is not listening (might be normal if container uses different port)"
            fi
        done
    else
        print_status 1 "No port mappings found"
    fi
else
    print_warning "Cannot check ports - container not running"
fi
echo ""

# 4. Check SSL certificates
echo -e "${BLUE}4. SSL Certificate Status${NC}"
echo "-------------------------"
ssl_path="/opt/audio-enhancer/ssl"
cert_file="$ssl_path/cert.pem"
key_file="$ssl_path/key.pem"

if [ -d "$ssl_path" ]; then
    print_status 0 "SSL directory exists"
    
    if [ -f "$cert_file" ]; then
        print_status 0 "Certificate file exists"
        # Check certificate expiry
        if command -v openssl &> /dev/null; then
            expiry_date=$(openssl x509 -enddate -noout -in "$cert_file" 2>/dev/null | cut -d= -f2)
            if [ -n "$expiry_date" ]; then
                print_info "Certificate expires: $expiry_date"
                
                # Check if expired
                expiry_seconds=$(date -d "$expiry_date" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$expiry_date" +%s 2>/dev/null)
                current_seconds=$(date +%s)
                if [ -n "$expiry_seconds" ] && [ $expiry_seconds -lt $current_seconds ]; then
                    print_warning "Certificate has expired!"
                fi
            fi
        fi
    else
        print_status 1 "Certificate file not found"
        print_info "Expected at: $cert_file"
    fi
    
    if [ -f "$key_file" ]; then
        print_status 0 "Key file exists"
        # Check key file permissions
        key_perms=$(stat -c %a "$key_file" 2>/dev/null || stat -f %A "$key_file" 2>/dev/null)
        if [ "$key_perms" = "600" ]; then
            print_status 0 "Key file has correct permissions (600)"
        else
            print_warning "Key file permissions: $key_perms (should be 600)"
        fi
    else
        print_status 1 "Key file not found"
        print_info "Expected at: $key_file"
    fi
else
    print_status 1 "SSL directory not found"
    print_info "Expected at: $ssl_path"
fi

# Check Let's Encrypt certificates
echo ""
echo "Let's Encrypt certificates:"
le_path="/etc/letsencrypt/live/ai-coustics.janbahmann.de"
if [ -d "$le_path" ]; then
    print_status 0 "Let's Encrypt directory exists"
    ls -la "$le_path" 2>/dev/null | grep -E "(fullchain|privkey)" | while read line; do
        print_info "$line"
    done
else
    print_warning "Let's Encrypt directory not found"
    print_info "Expected at: $le_path"
fi
echo ""

# 5. Container logs
echo -e "${BLUE}5. Recent Container Logs${NC}"
echo "------------------------"
if [ -n "$container_id" ]; then
    echo "Last 20 lines of container logs:"
    echo ""
    docker logs --tail 20 $container_name 2>&1 | sed 's/^/  /'
    
    # Check specifically for SSL detection in logs
    echo ""
    echo "SSL-related log entries:"
    docker logs $container_name 2>&1 | grep -i "ssl\|https\|certificate\|8443\|8000" | tail -10 | sed 's/^/  /'
else
    print_warning "Cannot show logs - container not running"
fi
echo ""

# 6. Environment check
echo -e "${BLUE}6. Environment Configuration${NC}"
echo "----------------------------"
env_file="/opt/audio-enhancer/.env"
if [ -f "$env_file" ]; then
    print_status 0 ".env file exists"
    
    # Check for required environment variables (without showing sensitive values)
    required_vars=("AI_COUSTICS_API_KEY" "SLACK_WEBHOOK_URL" "SLACK_CHANNEL")
    for var in "${required_vars[@]}"; do
        if grep -q "^$var=" "$env_file"; then
            print_status 0 "$var is configured"
        else
            print_status 1 "$var is not configured"
        fi
    done
else
    print_status 1 ".env file not found"
    print_info "Expected at: $env_file"
fi
echo ""

# 7. Network connectivity test
echo -e "${BLUE}7. Network Connectivity${NC}"
echo "-----------------------"
if [ -n "$container_id" ]; then
    # Test HTTP endpoint
    http_url="http://localhost:8002"
    https_url="https://localhost:8443"
    
    echo "Testing HTTP endpoint ($http_url):"
    if curl -s -o /dev/null -w "%{http_code}" "$http_url" 2>/dev/null | grep -q "200\|301\|302"; then
        print_status 0 "HTTP endpoint is responding"
        response_code=$(curl -s -o /dev/null -w "%{http_code}" "$http_url" 2>/dev/null)
        print_info "Response code: $response_code"
    else
        print_warning "HTTP endpoint not responding as expected"
    fi
    
    echo ""
    echo "Testing HTTPS endpoint ($https_url):"
    if curl -k -s -o /dev/null -w "%{http_code}" "$https_url" 2>/dev/null | grep -q "200\|301\|302"; then
        print_status 0 "HTTPS endpoint is responding"
        response_code=$(curl -k -s -o /dev/null -w "%{http_code}" "$https_url" 2>/dev/null)
        print_info "Response code: $response_code"
    else
        print_warning "HTTPS endpoint not responding"
        print_info "This might be normal if SSL is not configured"
    fi
    
    # Test API endpoint
    echo ""
    echo "Testing API stats endpoint:"
    api_response=$(curl -s "$http_url/api/stats" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$api_response" ]; then
        print_status 0 "API is responding"
        print_info "Stats response: $api_response"
    else
        print_warning "API not responding"
    fi
else
    print_warning "Cannot test connectivity - container not running"
fi
echo ""

# 8. Summary and recommendations
echo -e "${BLUE}8. Summary & Recommendations${NC}"
echo "----------------------------"

# Collect issues
issues=()
if [ -z "$container_id" ]; then
    issues+=("Container is not running")
fi
if [ ! -f "$cert_file" ] || [ ! -f "$key_file" ]; then
    issues+=("SSL certificates are missing")
fi
if [ ! -f "$env_file" ]; then
    issues+=("Environment configuration is missing")
fi

if [ ${#issues[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "The audio enhancer appears to be properly deployed."
    echo ""
    echo "Access the application at:"
    if [ -f "$cert_file" ] && [ -f "$key_file" ]; then
        echo "  - HTTPS: https://ai-coustics.janbahmann.de"
        echo "  - HTTPS (local): https://localhost:8443"
    fi
    echo "  - HTTP (local): http://localhost:8002"
else
    echo -e "${RED}Issues found:${NC}"
    for issue in "${issues[@]}"; do
        echo "  - $issue"
    done
    echo ""
    echo "Recommended actions:"
    if [ -z "$container_id" ]; then
        echo "  1. Check if deployment completed: cd /opt/audio-enhancer && docker compose ps"
        echo "  2. Try restarting: cd /opt/audio-enhancer && docker compose up -d"
        echo "  3. Check deployment logs: cd /opt/audio-enhancer && docker compose logs"
    fi
    if [ ! -f "$cert_file" ] || [ ! -f "$key_file" ]; then
        echo "  - Run certbot to generate SSL certificates"
        echo "  - Copy certificates to $ssl_path"
    fi
    if [ ! -f "$env_file" ]; then
        echo "  - Create .env file with required configuration"
    fi
fi

echo ""
echo "======================================"
echo "Check completed at: $(date)"
echo "======================================"