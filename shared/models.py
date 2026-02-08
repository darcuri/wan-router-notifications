"""Data models for WAN router notifications."""

from datetime import UTC, datetime, timedelta
from enum import IntEnum, StrEnum

from pydantic import BaseModel, Field


class InterfaceStatus(StrEnum):
    """Status of a network interface."""

    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class AlertSeverity(IntEnum):
    """Alert severity levels, higher value = more severe."""

    INFO = 1
    WARNING = 2
    CRITICAL = 3


class WANState(BaseModel):
    """Current state of a WAN interface."""

    interface: str
    status: InterfaceStatus
    since: datetime
    link_up: bool | None = None

    def duration_since(self, now: datetime | None = None) -> timedelta:
        """Calculate how long the interface has been in current state."""
        if now is None:
            now = datetime.now(UTC)
        return now - self.since


class AlertEvent(BaseModel):
    """An alert event to be sent or logged."""

    severity: AlertSeverity
    category: str  # wan, firewall, auth, vpn, system
    title: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, str] = Field(default_factory=dict)


class HeartbeatPayload(BaseModel):
    """Payload sent from local monitor to remote sentinel."""

    timestamp: datetime
    wan_states: dict[str, WANState]
    recent_events: list[AlertEvent]
    monitor_version: str = "0.1.0"


class SyslogEvent(BaseModel):
    """Parsed syslog event from router."""

    timestamp: datetime
    facility: str
    severity: str
    hostname: str
    message: str
    category: str = "system"
    raw: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)
