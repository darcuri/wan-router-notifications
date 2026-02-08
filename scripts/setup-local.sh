#!/bin/bash
# scripts/setup-local.sh
# Setup script for local monitor

set -e

echo "=== WAN Router Local Monitor Setup ==="

# Check Python version
python3 --version | grep -q "3.1[1-9]" || {
    echo "Error: Python 3.11+ required"
    exit 1
}

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install package
echo "Installing dependencies..."
pip install -e ".[dev]"

# Create config from example
if [ ! -f local/config.yaml ]; then
    echo "Creating config file..."
    cp local/config.example.yaml local/config.yaml
    echo "IMPORTANT: Edit local/config.yaml with your router settings"
fi

# Create .env from example
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "IMPORTANT: Edit .env with your Telegram bot token and SNMP auth key"
fi

# Note: wan-monitor.service runs as root (syslog needs privileged port 514)

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit local/config.yaml with your router IP and settings"
echo "2. Edit .env with your Telegram bot token and SNMP auth key"
echo "3. Test with: python -m local.main --mock-snmp --mock-telegram -v"
echo "4. Install service: sudo cp deploy/local/systemd/wan-monitor.service /etc/systemd/system/"
echo "5. Enable service: sudo systemctl enable --now wan-monitor"
