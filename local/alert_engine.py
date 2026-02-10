# local/alert_engine.py
"""Alert engine with state tracking and deduplication."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from shared.models import (
    AlertEvent,
    AlertSeverity,
    InterfaceStatus,
    SyslogEvent,
    WANState,
)
from shared.telegram import format_duration

logger = logging.getLogger(__name__)


@dataclass
class AlertState:
    """Tracks state for a single alertable entity."""

    current_status: InterfaceStatus = InterfaceStatus.UNKNOWN
    last_alert_time: datetime | None = None
    last_status_change: datetime | None = None
    consecutive_stable: int = 0

    def should_alert(self, new_status: InterfaceStatus) -> bool:
        """Determine if a status change should trigger an alert."""
        if self.current_status == InterfaceStatus.UNKNOWN:
            # First observation - only alert if down
            return new_status == InterfaceStatus.DOWN
        return new_status != self.current_status


class AlertEngine:
    """Process events and generate alerts with deduplication."""

    def __init__(
        self,
        router_ip: str = "192.168.0.1",
        router_name: str = "router",
    ):
        self.router_ip = router_ip
        self.router_name = router_name
        self._wan_states: dict[str, AlertState] = {}
        self._previous_wan: dict[str, WANState] = {}

    def process_wan_state(
        self, state: WANState, all_states: dict[str, WANState] | None = None,
    ) -> list[AlertEvent]:
        """Process a WAN state update and return any alerts.

        Args:
            state: The WAN state to process.
            all_states: All current WAN states (used to report failover target).
        """
        alerts: list[AlertEvent] = []
        now = datetime.now(UTC)

        if state.interface not in self._wan_states:
            self._wan_states[state.interface] = AlertState()

        alert_state = self._wan_states[state.interface]
        previous = self._previous_wan.get(state.interface)
        state_changed = alert_state.should_alert(state.status)

        if state_changed:
            if state.status == InterfaceStatus.DOWN:
                if previous and previous.status == InterfaceStatus.UP:
                    uptime = format_duration((now - previous.since).total_seconds())
                else:
                    uptime = "unknown"

                failover_target = None
                if all_states:
                    for name, s in all_states.items():
                        if s.status == InterfaceStatus.UP and name != state.interface:
                            failover_target = name
                            break

                failover_line = (
                    f"Failover: active on {failover_target}"
                    if failover_target
                    else "Failover: no active WAN detected"
                )

                # Link state context from ifOperStatus
                if state.link_up is False:
                    link_line = "Cause: physical link down"
                elif state.link_up is True:
                    link_line = "Cause: likely upstream/ISP issue (link up, no route)"
                else:
                    link_line = ""

                message_parts = [
                    f"Router: {self.router_name} ({self.router_ip})",
                    f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    f"Previous state: UP for {uptime}",
                    failover_line,
                ]
                if link_line:
                    message_parts.append(link_line)
                message_parts.append("Action: Monitoring at 15s intervals")

                alerts.append(
                    AlertEvent(
                        severity=AlertSeverity.CRITICAL,
                        category="wan",
                        title=f"{state.interface} DOWN",
                        message="\n".join(message_parts),
                        timestamp=now,
                    )
                )

            elif state.status == InterfaceStatus.UP:
                # Calculate downtime
                if previous and previous.status == InterfaceStatus.DOWN:
                    downtime = format_duration((now - previous.since).total_seconds())
                else:
                    downtime = "unknown"

                alerts.append(
                    AlertEvent(
                        severity=AlertSeverity.CRITICAL,
                        category="wan",
                        title=f"{state.interface} RECOVERED",
                        message=(
                            f"Router: {self.router_name} ({self.router_ip})\n"
                            f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                            f"Downtime: {downtime}\n"
                            f"Restored as primary gateway"
                        ),
                        timestamp=now,
                    )
                )

            alert_state.current_status = state.status
            alert_state.last_alert_time = now
            alert_state.last_status_change = now

        # Track consecutive stable polls for adaptive polling
        if state_changed:
            alert_state.consecutive_stable = 0
        else:
            alert_state.consecutive_stable += 1

        self._previous_wan[state.interface] = state
        return alerts

    def process_syslog_event(self, event: SyslogEvent) -> list[AlertEvent]:
        """Process a syslog event and return any alerts.

        Only WAN events generate alerts. All other syslog categories are ignored.
        """
        if event.category == "wan":
            return self._process_wan_syslog(event)
        return []

    def _process_wan_syslog(self, event: SyslogEvent) -> list[AlertEvent]:
        """Process WAN-specific syslog events. No cooldown applied."""
        wan_event_type = event.metadata.get("wan_event_type", "")
        wan_interface = event.metadata.get("wan_interface", "unknown")
        now = datetime.now(UTC)

        # ONLINE_DECTION events are confirmatory — log only, no alert
        if wan_event_type == "online_detection":
            logger.info(f"WAN online detection: {wan_interface} — {event.message}")
            return []

        if wan_event_type == "failover_activated":
            return [AlertEvent(
                severity=AlertSeverity.CRITICAL,
                category="wan",
                title=f"FAILOVER: {wan_interface} activated",
                message=(
                    f"Router: {self.router_name} ({self.router_ip})\n"
                    f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                    f"Backup link {wan_interface} has taken over"
                ),
                timestamp=now,
            )]

        if wan_event_type == "failover_deactivated":
            return [AlertEvent(
                severity=AlertSeverity.CRITICAL,
                category="wan",
                title=f"FAILOVER ENDED: {wan_interface} deactivated",
                message=(
                    f"Router: {self.router_name} ({self.router_ip})\n"
                    f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                    f"Backup link {wan_interface} deactivated, primary restored"
                ),
                timestamp=now,
            )]

        if wan_event_type == "link_down":
            return [AlertEvent(
                severity=AlertSeverity.WARNING,
                category="wan",
                title=f"{wan_interface} physical link DOWN",
                message=(
                    f"Router: {self.router_name} ({self.router_ip})\n"
                    f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                    f"Physical connection lost on {wan_interface}"
                ),
                timestamp=now,
            )]

        return []

    def should_use_alert_interval(self) -> bool:
        """Check if any interface is in alert state (should poll faster)."""
        for state in self._wan_states.values():
            if state.current_status == InterfaceStatus.DOWN:
                return True
            if state.consecutive_stable < 5:
                return True
        return False

    def get_current_wan_states(self) -> dict[str, WANState]:
        """Get the current WAN states for heartbeat."""
        return self._previous_wan.copy()
