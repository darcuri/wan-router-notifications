# WAN Router Notifications

Hybrid monitoring system for dual-WAN routers that detects failover events via SNMP and syslog, sends Telegram alerts with severity levels, and includes a remote sentinel for detecting total connectivity outages.

Designed for the TP-Link ER605, but the SNMP and syslog approach may work with other routers that support SNMPv3 and standard syslog output.

## Features

- **SNMP Gateway Polling** -- Detects active WAN by monitoring the default route next-hop gateway
- **SNMP ifOperStatus** -- Monitors physical link state as a secondary signal
- **Syslog Failover Detection** -- Parses Link Backup and SWITCH events from the router
- **Telegram Alerts** -- Instant notifications with severity levels (Critical, Warning)
- **Remote Sentinel** -- Detects total connection loss via heartbeat monitoring from a VPS
- **DuckDNS IP Change Detection** -- Alerts when your public IP changes or mismatches expected value
- **Self-hosted VPN** -- Secure local-to-remote communication via Headscale (self-hosted Tailscale)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         YOUR NETWORK                                │
│  ┌─────────────┐      SNMP/Syslog      ┌─────────────────────────┐  │
│  │  Dual-WAN  │◄─────────────────────►│   Local Monitor         │  │
│  │   Router   │                       │   (wan-monitor)         │  │
│  └─────────────┘                       └───────────┬─────────────┘  │
└────────────────────────────────────────────────────┼────────────────┘
                                                     │ Tailscale
                                                     │ (Headscale)
┌────────────────────────────────────────────────────┼────────────────┐
│                      ORACLE CLOUD VPS              ▼                │
│                       ┌─────────────────────────────────────────┐   │
│                       │   Remote Sentinel (wan-sentinel)        │   │
│                       │   + Headscale server                    │   │
│                       └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

1. TP-Link ER605 router with SNMPv3 enabled
2. Oracle Cloud Free Tier account (or any VPS)
3. Domain name pointing to VPS (e.g. DuckDNS)
4. Telegram account
5. SSH key pair

### 1. Create Telegram Bot

See [scripts/create-telegram-bot.md](scripts/create-telegram-bot.md) for detailed instructions.

### 2. Deploy Remote Sentinel (VPS)

```bash
# Generate SSH key if needed
ssh-keygen -t ed25519 -C "oracle-vps"

# In OCI Cloud Shell:
git clone <repo-url>
cd wan-router-notifications/deploy/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your OCIDs

terraform init
terraform apply -var="ssh_public_key=$(cat ~/id_ed25519.pub)"
```

SSH to the new instance and run setup:

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@<public-ip>
cd /opt/wan-router-notifications
./scripts/setup-remote.sh

# Configure Headscale (TLS via Let's Encrypt ACME)
sudo cp deploy/remote/headscale/config.yaml /etc/headscale/config.yaml
# Edit /etc/headscale/config.yaml:
#   - server_url: https://<your-domain>:443
#   - acme_email: your-email@example.com
#   - tls_letsencrypt_hostname: <your-domain>
sudo mkdir -p /var/lib/headscale/cache

# Start Headscale
sudo systemctl enable --now headscale
headscale users create home
headscale preauthkeys create --user home --expiration 24h
# Save the auth key!

# Install Tailscale client and join mesh FIRST
# (VPS must join before local monitor to get 100.64.0.1)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --login-server https://<your-domain>:443 --authkey <key>

# Verify VPS got 100.64.0.1
tailscale status

# Configure and start sentinel
cp .env.example .env
# Edit .env with Telegram token
cp remote/config.example.yaml remote/config.yaml
# Edit remote/config.yaml with your settings

sudo cp deploy/remote/systemd/wan-sentinel.service /etc/systemd/system/
sudo systemctl enable --now wan-sentinel
```

> **OCI Note**: Oracle Cloud Ubuntu images have iptables rules that block all
> non-SSH traffic, bypassing firewalld. The setup script detects this and adds
> rules for port 443 (Headscale HTTPS) and 3478/UDP (STUN). If deploying
> manually, run:
> ```bash
> sudo iptables -I INPUT 5 -p tcp --dport 443 -j ACCEPT
> sudo iptables -I INPUT 6 -p udp --dport 3478 -j ACCEPT
> sudo netfilter-persistent save
> ```

### 3. Deploy Local Monitor

```bash
# Generate a new auth key on the VPS
headscale preauthkeys create --user home --expiration 24h

# Install Tailscale and connect (local monitor gets 100.64.0.2)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --login-server https://<your-domain>:443 --authkey <key>

# Setup local monitor
git clone <repo-url>
cd wan-router-notifications
./scripts/setup-local.sh

# Configure
# Edit .env with Telegram token and SNMP auth key
# Edit local/config.yaml with router IP, SNMP credentials, WAN gateways

# Test
python -m local.main --mock-snmp --mock-telegram -v

# Deploy (runs as root for privileged syslog port 514)
sudo cp deploy/local/systemd/wan-monitor.service /etc/systemd/system/
sudo systemctl enable --now wan-monitor
```

## Configuration Reference

### Local Monitor (`local/config.yaml`)

```yaml
router:
  host: "192.168.0.1"            # Router IP address
  name: "router"                 # Display name in alerts
  snmp_username: "snmpuser"      # SNMPv3 username
  snmp_auth_key: "changeme"      # Override with SNMP_AUTH_KEY env var
  snmp_auth_protocol: "MD5"      # MD5 or SHA
  snmp_port: 161                 # SNMP port
  snmp_timeout: 5                # SNMP request timeout (seconds)
  wan_gateways:                  # Map WAN names to gateway IPs
    WAN1: "192.168.1.1"          #   Primary WAN gateway
    WAN2: "192.168.2.1"          #   Backup WAN gateway
  wan_interfaces:                # Optional: ifIndex for physical link monitoring
    WAN1: 4
    WAN2: 5

polling:
  normal_interval: 60            # Seconds between SNMP polls (normal)
  alert_interval: 15             # Seconds between polls (during alert)
  recovery_threshold: 5          # Consecutive OK polls before clearing alert

syslog:
  enabled: true                  # Enable syslog receiver
  port: 514                      # Syslog listen port
  bind_address: "0.0.0.0"       # Syslog bind address

heartbeat:
  remote_url: "http://100.64.0.1:8080/heartbeat"  # Remote sentinel URL
  interval: 60                   # Seconds between heartbeats
  timeout: 10                    # HTTP request timeout (seconds)
```

### Remote Sentinel (`remote/config.yaml`)

```yaml
heartbeat:
  expected_interval: 60          # Expected seconds between heartbeats
  missed_threshold: 3            # Missed heartbeats before alerting
  listen_host: "100.64.0.1"     # Tailscale/VPN IP to listen on
  listen_port: 8080             # HTTP listen port

external_probe:
  enabled: false                 # Enable external reachability probe
  # target_ip: ""               # Home network public IP
  # interval: 300               # Seconds between probes
  # timeout: 10                 # Probe timeout (seconds)

dns_monitor:
  enabled: false                 # Enable DuckDNS IP monitoring
  # hostname: "example.duckdns.org"  # DuckDNS hostname to monitor
  # expected_ip: ""             # Expected public IP (optional)
  # interval: 300               # Seconds between DNS checks
```

### Environment Variables (`.env`)

```bash
TELEGRAM_BOT_TOKEN=your-bot-token   # Telegram bot API token
TELEGRAM_CHAT_ID=your-chat-id       # Telegram chat/group ID
SNMP_AUTH_KEY=your-snmp-auth-key    # SNMP auth password (local monitor only)
```

## Alert Types

| Alert | Severity | Source | Trigger |
|-------|----------|--------|---------|
| WAN DOWN | Critical | SNMP | Default route failover detected |
| WAN RECOVERED | Critical | SNMP | Primary gateway restored |
| Failover Activated | Critical | Syslog | Backup link took effect |
| Failover Ended | Critical | Syslog | Backup link deactivated |
| Physical Link Down | Warning | Syslog | WAN port physical connection lost |
| Auth Failure | Warning | Syslog | Failed login attempts |
| Monitor Lost | Critical | Heartbeat | No heartbeat for 3+ minutes |
| DNS IP Changed | Warning | DNS | DuckDNS record IP changed |
| DNS IP Mismatch | Critical | DNS | IP doesn't match expected |

## Development

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Test
pytest

# Lint
ruff check .

# Type check
mypy .

# Run in mock mode
python -m local.main --mock-snmp --mock-telegram -v
```

## License

[MIT](LICENSE)
