#!/bin/bash
# Script to run SlateGallery tests with proper Qt support

echo "Running SlateGallery Test Suite"
echo "==============================="

# Activate virtual environment
source venv/bin/activate

# Check if we're in a headless environment
if [ -z "$DISPLAY" ]; then
    echo "Headless environment detected. Using Xvfb for Qt tests."
    
    # Check if xvfb-run is available
    if command -v xvfb-run &> /dev/null; then
        echo "Running tests with Xvfb virtual display..."
        xvfb-run -a python -m pytest tests/ -v "$@"
    else
        echo "Warning: xvfb-run not found. Running without display (may cause issues with Qt tests)."
        echo "To install Xvfb: sudo apt-get install xvfb"
        QT_QPA_PLATFORM=offscreen python -m pytest tests/ -v "$@"
    fi
else
    echo "Display detected. Running tests normally..."
    python -m pytest tests/ -v "$@"
fi