#!/bin/bash
# SlateGallery JavaScript Test Runner
# Runs the HTML test suite in a browser or headless environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_FILE="$SCRIPT_DIR/gallery_tests.html"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  SlateGallery JavaScript Tests${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if test file exists
check_test_file() {
    if [ ! -f "$TEST_FILE" ]; then
        print_error "Test file not found: $TEST_FILE"
        exit 1
    fi
    print_success "Found test file: gallery_tests.html"
}

# Open in browser
open_browser() {
    print_info "Opening tests in browser..."

    if command -v firefox &> /dev/null; then
        firefox "$TEST_FILE" &
        print_success "Opened in Firefox"
    elif command -v google-chrome &> /dev/null; then
        google-chrome "$TEST_FILE" &
        print_success "Opened in Chrome"
    elif command -v chromium &> /dev/null; then
        chromium "$TEST_FILE" &
        print_success "Opened in Chromium"
    elif command -v open &> /dev/null; then
        # macOS
        open "$TEST_FILE"
        print_success "Opened in default browser (macOS)"
    elif command -v xdg-open &> /dev/null; then
        # Linux
        xdg-open "$TEST_FILE" &
        print_success "Opened in default browser (Linux)"
    else
        print_error "No browser found. Please open manually:"
        echo "  file://$TEST_FILE"
        exit 1
    fi
}

# Start local web server
start_server() {
    local port=${1:-8000}
    print_info "Starting local web server on port $port..."

    cd "$SCRIPT_DIR/../.."

    if command -v python3 &> /dev/null; then
        print_success "Using Python HTTP server"
        echo ""
        print_info "Open in browser: http://localhost:$port/tests/gallery/gallery_tests.html"
        echo ""
        python3 -m http.server $port
    elif command -v python &> /dev/null; then
        print_success "Using Python 2 SimpleHTTPServer"
        echo ""
        print_info "Open in browser: http://localhost:$port/tests/gallery/gallery_tests.html"
        echo ""
        python -m SimpleHTTPServer $port
    else
        print_error "Python not found. Cannot start web server."
        exit 1
    fi
}

# Run headless tests (requires playwright or puppeteer)
run_headless() {
    print_info "Running headless tests..."

    if command -v playwright &> /dev/null; then
        print_success "Using Playwright"
        # Start server in background
        cd "$SCRIPT_DIR/../.."
        python3 -m http.server 8765 > /dev/null 2>&1 &
        SERVER_PID=$!

        sleep 2

        # Run tests
        playwright test "http://localhost:8765/tests/gallery/gallery_tests.html" || {
            kill $SERVER_PID
            print_error "Tests failed"
            exit 1
        }

        kill $SERVER_PID
        print_success "Tests completed"
    elif command -v npx &> /dev/null; then
        print_warning "Playwright not found, trying Puppeteer..."

        # Start server in background
        cd "$SCRIPT_DIR/../.."
        python3 -m http.server 8765 > /dev/null 2>&1 &
        SERVER_PID=$!

        sleep 2

        # Run tests with puppeteer
        npx puppeteer "http://localhost:8765/tests/gallery/gallery_tests.html" || {
            kill $SERVER_PID
            print_error "Tests failed"
            exit 1
        }

        kill $SERVER_PID
        print_success "Tests completed"
    else
        print_error "Neither Playwright nor Puppeteer found"
        print_info "Install with: pip install playwright && playwright install"
        exit 1
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 [option]"
    echo ""
    echo "Options:"
    echo "  browser      Open tests in browser (default)"
    echo "  server       Start local web server"
    echo "  headless     Run tests headlessly (requires playwright/puppeteer)"
    echo "  help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                  # Open in browser"
    echo "  $0 browser          # Open in browser"
    echo "  $0 server           # Start web server on port 8000"
    echo "  $0 server 9000      # Start web server on port 9000"
    echo "  $0 headless         # Run headless tests"
}

# Main script
main() {
    print_header
    check_test_file
    echo ""

    local mode=${1:-browser}

    case "$mode" in
        browser)
            open_browser
            ;;
        server)
            local port=${2:-8000}
            start_server "$port"
            ;;
        headless)
            run_headless
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown option: $mode"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
