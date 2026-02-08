"""Alert engine for remote sentinel."""

import logging
from datetime import UTC, datetime

from remote.external_probe import ProbeResult
from shared.models import AlertEvent, AlertSeverity, WANState
from shared.telegram import format_duration

logger = logging.getLogger(__name__)


class RemoteAlertEngine:
    """Generate alerts for remote sentinel events."""

    def create_monitor_lost_alert(
        self,
        last_heartbeat: datetime,
        wan_states: dict[str, WANState],
        probe_result: ProbeResult,
    ) -> AlertEvent:
        """Create alert when local monitor stops responding."""
        now = datetime.now(UTC)
        ago = format_duration((now - last_heartbeat).total_seconds())

        wan_summary = " | ".join(
            f"{name}: {state.status.value.upper()}"
            for name, state in wan_states.items()
        ) or "No data"

        probe_status = {
            ProbeResult.UNREACHABLE: "FAILED",
            ProbeResult.REACHABLE: "SUCCESS",
            ProbeResult.DISABLED: "N/A",
        }.get(probe_result, "N/A")

        if probe_result == ProbeResult.UNREACHABLE:
            diagnosis = "Internet connection likely down"
        elif probe_result == ProbeResult.REACHABLE:
            diagnosis = "Local monitor may have crashed"
        else:
            diagnosis = "Unable to determine"

        message = (
            f"Last heartbeat: {ago} ago\n"
            f"Last known state:\n  {wan_summary}\n"
            f"External probe: {probe_status}\n"
            f"Diagnosis: {diagnosis}"
        )

        return AlertEvent(
            severity=AlertSeverity.CRITICAL,
            category="monitor",
            title="CONNECTION LOST TO LOCAL MONITOR",
            message=message,
            timestamp=now,
        )

    def create_monitor_recovered_alert(self) -> AlertEvent:
        """Create alert when local monitor reconnects."""
        return AlertEvent(
            severity=AlertSeverity.INFO,
            category="monitor",
            title="LOCAL MONITOR RECOVERED",
            message="Heartbeat received. Local monitor is back online.",
            timestamp=datetime.now(UTC),
        )
