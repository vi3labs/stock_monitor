#!/bin/bash
#
# Stock Monitor Dashboard - Start Script
# ======================================
# Starts the Flask API server and serves the dashboard frontend.
#
# Usage:
#   ./start-dashboard.sh         # Start both API and frontend
#   ./start-dashboard.sh api     # Start API only
#   ./start-dashboard.sh web     # Start frontend only
#
# Ports:
#   API:      http://localhost:5001
#   Frontend: http://localhost:3004

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ports
API_PORT=5001
WEB_PORT=3004

# PIDs for cleanup
API_PID=""
WEB_PID=""

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"

    if [ -n "$API_PID" ] && kill -0 "$API_PID" 2>/dev/null; then
        kill "$API_PID" 2>/dev/null || true
        echo -e "${GREEN}API server stopped${NC}"
    fi

    if [ -n "$WEB_PID" ] && kill -0 "$WEB_PID" 2>/dev/null; then
        kill "$WEB_PID" 2>/dev/null || true
        echo -e "${GREEN}Web server stopped${NC}"
    fi

    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM

# Check for required commands
check_dependencies() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: python3 is required but not installed.${NC}"
        exit 1
    fi

    # Check for http-server or npx
    if ! command -v npx &> /dev/null && ! command -v http-server &> /dev/null; then
        echo -e "${YELLOW}Warning: npx (node) not found. Will try python http.server instead.${NC}"
    fi
}

# Start API server
start_api() {
    echo -e "${BLUE}Starting API server on port $API_PORT...${NC}"

    # Check if port is already in use
    if lsof -Pi :$API_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}Port $API_PORT already in use. Attempting to kill existing process...${NC}"
        lsof -Pi :$API_PORT -sTCP:LISTEN -t | xargs kill -9 2>/dev/null || true
        sleep 1
    fi

    python3 api/server.py &
    API_PID=$!

    # Wait for server to be ready
    for i in {1..10}; do
        if curl -s "http://localhost:$API_PORT/api/health" > /dev/null 2>&1; then
            echo -e "${GREEN}API server ready at http://localhost:$API_PORT${NC}"
            return 0
        fi
        sleep 1
    done

    echo -e "${YELLOW}API server starting (may take a moment for first data fetch)${NC}"
}

# Start web server
start_web() {
    echo -e "${BLUE}Starting web server on port $WEB_PORT...${NC}"

    # Check if port is already in use
    if lsof -Pi :$WEB_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}Port $WEB_PORT already in use. Attempting to kill existing process...${NC}"
        lsof -Pi :$WEB_PORT -sTCP:LISTEN -t | xargs kill -9 2>/dev/null || true
        sleep 1
    fi

    # Try npx http-server first, fallback to python
    if command -v npx &> /dev/null; then
        npx http-server dashboard -p $WEB_PORT -c-1 --silent &
        WEB_PID=$!
    elif command -v http-server &> /dev/null; then
        http-server dashboard -p $WEB_PORT -c-1 --silent &
        WEB_PID=$!
    else
        # Fallback to Python's built-in server
        cd dashboard
        python3 -m http.server $WEB_PORT &
        WEB_PID=$!
        cd ..
    fi

    sleep 2
    echo -e "${GREEN}Dashboard available at http://localhost:$WEB_PORT${NC}"
}

# Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "=============================================="
    echo "  Stock Monitor Dashboard"
    echo "=============================================="
    echo -e "${NC}"
}

# Main
main() {
    print_banner
    check_dependencies

    MODE=${1:-all}

    case $MODE in
        api)
            start_api
            echo -e "\n${GREEN}API server running. Press Ctrl+C to stop.${NC}"
            wait $API_PID
            ;;
        web)
            start_web
            echo -e "\n${GREEN}Web server running. Press Ctrl+C to stop.${NC}"
            wait $WEB_PID
            ;;
        all|*)
            start_api
            start_web

            echo ""
            echo -e "${GREEN}=============================================="
            echo "  Dashboard is running!"
            echo "=============================================="
            echo -e "  API:       http://localhost:$API_PORT"
            echo -e "  Dashboard: http://localhost:$WEB_PORT"
            echo -e "==============================================${NC}"
            echo ""
            echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"

            # Wait for either process to exit
            wait
            ;;
    esac
}

main "$@"
