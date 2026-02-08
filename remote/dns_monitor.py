"""DNS monitor for DuckDNS IP change detection."""

import logging
import socket
from datetime import UTC, datetime

from shared.models import AlertEvent, AlertSeverity

logger = logging.getLogger(__name__)


def resolve_hostname(hostname: str) -> str | None:
    """Resolve hostname to IPv4 address. Returns None on failure."""
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if results:
            return results[0][4][0]
    except socket.gaierror as e:
        logger.warning(f"DNS resolution failed for {hostname}: {e}")
    return None


class DnsMonitor:
    """Monitor DNS record for IP changes."""

    def __init__(self, hostname: str, expected_ip: str = ""):
        self.hostname = hostname
        self.expected_ip = expected_ip
        self.last_seen_ip: str | None = None
        self.consecutive_failures: int = 0

    def check(self) -> list[AlertEvent]:
        """Check DNS and return alerts for any changes."""
        now = datetime.now(UTC)
        current_ip = resolve_hostname(self.hostname)

        if current_ip is None:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 2:
                return [AlertEvent(
                    severity=AlertSeverity.WARNING,
                    category="dns",
                    title=f"DNS resolution failed for {self.hostname}",
                    message=(
                        f"Failed to resolve {self.hostname}\n"
                        f"Consecutive failures: {self.consecutive_failures}\n"
                        f"Last known IP: {self.last_seen_ip or 'none'}"
                    ),
                    timestamp=now,
                )]
            return []

        self.consecutive_failures = 0
        alerts: list[AlertEvent] = []

        # Check for change from last known IP
        if self.last_seen_ip is not None and current_ip != self.last_seen_ip:
            alerts.append(AlertEvent(
                severity=AlertSeverity.WARNING,
                category="dns",
                title=f"DNS record changed for {self.hostname}",
                message=(
                    f"IP changed: {self.last_seen_ip} → {current_ip}\n"
                    f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                ),
                timestamp=now,
            ))

        # Check against expected IP
        if self.expected_ip and current_ip != self.expected_ip:
            alerts.append(AlertEvent(
                severity=AlertSeverity.CRITICAL,
                category="dns",
                title=f"DNS mismatch for {self.hostname}",
                message=(
                    f"Current IP: {current_ip}\n"
                    f"Expected IP: {self.expected_ip}\n"
                    f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                ),
                timestamp=now,
            ))

        self.last_seen_ip = current_ip
        return alerts
