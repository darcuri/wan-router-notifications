#!/bin/bash
# scripts/setup-remote.sh
# Setup script for remote sentinel

set -e

echo "=== WAN Router Remote Sentinel Setup ==="

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
pip install -e .

# Create config from example
if [ ! -f remote/config.yaml ]; then
    echo "Creating config file..."
    cp remote/config.example.yaml remote/config.yaml
    echo "IMPORTANT: Edit remote/config.yaml with your settings"
fi

# Create .env from example
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "IMPORTANT: Edit .env with your Telegram bot token"
fi

# Create service user (if running as root)
if [ "$EUID" -eq 0 ]; then
    echo "Creating service user..."
    useradd -r -s /bin/false sentinel 2>/dev/null || true
fi

# Check if Headscale is installed
if ! command -v headscale &> /dev/null; then
    echo ""
    echo "WARNING: Headscale not installed. Install with:"
    echo "  curl -Lo /tmp/headscale.deb 'https://github.com/juanfont/headscale/releases/download/v0.22.3/headscale_0.22.3_linux_arm64.deb'"
    echo "  sudo dpkg -i /tmp/headscale.deb"
fi

# Check if Tailscale client is installed
if ! command -v tailscale &> /dev/null; then
    echo ""
    echo "WARNING: Tailscale client not installed. Install with:"
    echo "  curl -fsSL https://tailscale.com/install.sh | sh"
fi

# OCI iptables fix (if running on Oracle Cloud)
if sudo iptables -L INPUT -n --line-numbers 2>/dev/null | grep -q "REJECT.*icmp-host-prohibited"; then
    echo ""
    echo "Detected OCI iptables rules. Adding Headscale and STUN ports..."
    sudo iptables -I INPUT 5 -p tcp --dport 443 -j ACCEPT
    sudo iptables -I INPUT 6 -p udp --dport 3478 -j ACCEPT
    sudo netfilter-persistent save 2>/dev/null || true
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Configure Headscale: sudo cp deploy/remote/headscale/config.yaml /etc/headscale/config.yaml"
echo "   - Update acme_email and tls_letsencrypt_hostname for your domain"
echo "2. Edit .env with your Telegram bot token"
echo "3. Edit remote/config.yaml with your home WAN hostname for external probe"
echo "4. Start Headscale: sudo systemctl enable --now headscale"
echo "5. Create user: headscale users create home"
echo "6. Create authkey: headscale preauthkeys create --user home --expiration 24h"
echo "7. Join VPS to mesh FIRST: sudo tailscale up --login-server https://<your-domain>:443 --authkey <key>"
echo "   (VPS must join first to get 100.64.0.1)"
echo "8. Install service: sudo cp deploy/remote/systemd/wan-sentinel.service /etc/systemd/system/"
echo "9. Enable service: sudo systemctl enable --now wan-sentinel"
