#!/bin/bash
# Stock Monitor Setup Script
# ==========================
# Run this script to set up the stock monitoring system

set -e

echo "=================================="
echo "  Stock Monitor Setup Script"
echo "=================================="
echo ""

# Check Python version
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    echo "✓ Found Python $PYTHON_VERSION"
else
    echo "✗ Python 3 not found. Please install Python 3.8 or later."
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip > /dev/null
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Create reports directory
echo ""
echo "Creating reports directory..."
mkdir -p reports
echo "✓ Reports directory created"

# Check if config needs to be set up
echo ""
echo "=================================="
echo "  Configuration Required"
echo "=================================="
echo ""
echo "Before running, please update config.yaml with:"
echo ""
echo "1. Your Gmail address:"
echo "   sender_email: \"your.email@gmail.com\""
echo ""
echo "2. Your Gmail App Password:"
echo "   - Go to https://myaccount.google.com/apppasswords"
echo "   - Generate a new app password for 'Mail'"
echo "   - Copy the 16-character password"
echo "   sender_password: \"xxxx xxxx xxxx xxxx\""
echo ""
echo "3. Recipient email (can be same as sender):"
echo "   recipient_email: \"your.email@gmail.com\""
echo ""

# Test imports
echo "=================================="
echo "  Testing Installation"
echo "=================================="
echo ""
python3 -c "import yfinance; print('✓ yfinance')"
python3 -c "import pandas; print('✓ pandas')"
python3 -c "import schedule; print('✓ schedule')"
python3 -c "import yaml; print('✓ pyyaml')"
python3 -c "import jinja2; print('✓ jinja2')"
python3 -c "import requests; print('✓ requests')"
python3 -c "import bs4; print('✓ beautifulsoup4')"

# Try matplotlib (optional)
python3 -c "import matplotlib; print('✓ matplotlib')" 2>/dev/null || echo "⚠ matplotlib not installed (charts won't generate)"

echo ""
echo "=================================="
echo "  Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit config.yaml with your email settings"
echo "2. Test the system: python scheduler.py --test"
echo "3. Run the scheduler: python scheduler.py"
echo ""
echo "To activate the environment in the future:"
echo "  source venv/bin/activate"
echo ""
