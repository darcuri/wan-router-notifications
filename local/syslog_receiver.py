"""Syslog receiver for router events."""

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime

from shared.models import SyslogEvent

logger = logging.getLogger(__name__)

# Syslog priority regex: <PRI>TIMESTAMP HOSTNAME TAG: MESSAGE
SYSLOG_PATTERN = re.compile(
    r"<(\d+)>(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(.+?):\s*(.*)"
)

# WAN event patterns (checked before generic keywords)
WAN_PATTERNS = [
    (re.compile(r"Backup \[(.+?)\] took effect"), "failover_activated"),
    (re.compile(r"Backup \[(.+?)\] was down"), "failover_deactivated"),
    (re.compile(r"physical connection status of \[(.+?)\] was down"), "link_down"),
    (
        re.compile(r"online detection result of \[(.+?)\] was (?:online|offline)"),
        "online_detection",
    ),
]

# Keywords for categorization
AUTH_KEYWORDS = ["login", "logout", "password", "authentication", "user", "admin"]
FIREWALL_KEYWORDS = ["blocked", "dropped", "denied", "firewall", "reject"]
VPN_KEYWORDS = ["ipsec", "vpn", "tunnel", "openvpn", "l2tp", "pptp"]
SYSTEM_KEYWORDS = ["reboot", "startup", "shutdown", "config", "firmware", "update"]


def parse_syslog_message(raw: str) -> SyslogEvent | None:
    """Parse a raw syslog message into a SyslogEvent."""
    match = SYSLOG_PATTERN.match(raw.strip())
    if not match:
        logger.debug(f"Failed to parse syslog message: {raw[:100]}")
        return None

    priority, timestamp_str, hostname, facility, message = match.groups()

    # Parse timestamp (assume current year)
    try:
        now = datetime.now(UTC)
        timestamp = datetime.strptime(f"{now.year} {timestamp_str}", "%Y %b %d %H:%M:%S")
        timestamp = timestamp.replace(tzinfo=UTC)
    except ValueError:
        timestamp = datetime.now(UTC)

    # Calculate severity from priority (priority = facility * 8 + severity)
    pri = int(priority)
    severity_num = pri % 8
    severity_names = ["emerg", "alert", "crit", "err", "warning", "notice", "info", "debug"]
    severity = severity_names[severity_num] if severity_num < len(severity_names) else "unknown"

    category, metadata = categorize_message(message)

    return SyslogEvent(
        timestamp=timestamp,
        facility=facility,
        severity=severity,
        hostname=hostname,
        message=message,
        category=category,
        raw=raw,
        metadata=metadata,
    )


def categorize_message(message: str) -> tuple[str, dict[str, str]]:
    """Categorize a syslog message. Returns (category, metadata)."""
    # Check WAN patterns first
    for pattern, event_type in WAN_PATTERNS:
        match = pattern.search(message)
        if match:
            return "wan", {
                "wan_event_type": event_type,
                "wan_interface": match.group(1),
            }

    # Generic keyword matching
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in AUTH_KEYWORDS):
        return "auth", {}
    if any(kw in msg_lower for kw in FIREWALL_KEYWORDS):
        return "firewall", {}
    if any(kw in msg_lower for kw in VPN_KEYWORDS):
        return "vpn", {}
    if any(kw in msg_lower for kw in SYSTEM_KEYWORDS):
        return "system", {}

    return "system", {}  # default


class SyslogProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for syslog messages."""

    def __init__(self, callback: Callable[[SyslogEvent], None]):
        self.callback = callback

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            raw = data.decode("utf-8", errors="replace")
            event = parse_syslog_message(raw)
            if event:
                self.callback(event)
        except Exception as e:
            logger.error(f"Error processing syslog from {addr}: {e}")


class SyslogReceiver:
    """Async UDP syslog receiver."""

    def __init__(
        self,
        port: int = 514,
        bind_address: str = "0.0.0.0",
    ):
        self.port = port
        self.bind_address = bind_address
        self._transport: asyncio.DatagramTransport | None = None
        self._callbacks: list[Callable[[SyslogEvent], None]] = []

    def add_callback(self, callback: Callable[[SyslogEvent], None]) -> None:
        """Register a callback for received syslog events."""
        self._callbacks.append(callback)

    def _on_event(self, event: SyslogEvent) -> None:
        """Internal handler that dispatches to all callbacks."""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def start(self) -> None:
        """Start the syslog receiver."""
        loop = asyncio.get_event_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: SyslogProtocol(self._on_event),
            local_addr=(self.bind_address, self.port),
        )
        logger.info(f"Syslog receiver listening on {self.bind_address}:{self.port}")

    async def stop(self) -> None:
        """Stop the syslog receiver."""
        if self._transport:
            self._transport.close()
            self._transport = None
