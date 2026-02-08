# tests/test_remote_alert_engine.py
from datetime import UTC, datetime

from remote.alert_engine import RemoteAlertEngine
from remote.external_probe import ProbeResult
from shared.models import AlertSeverity, InterfaceStatus, WANState


class TestRemoteAlertEngine:
    def test_generate_missing_alert_with_probe_failed(self):
        engine = RemoteAlertEngine()

        last_heartbeat = datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC)
        wan_states = {
            "WAN1": WANState(
                interface="WAN1",
                status=InterfaceStatus.UP,
                since=datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC),

            ),
        }

        alert = engine.create_monitor_lost_alert(
            last_heartbeat=last_heartbeat,
            wan_states=wan_states,
            probe_result=ProbeResult.UNREACHABLE,
        )

        assert alert.severity == AlertSeverity.CRITICAL
        assert "CONNECTION LOST" in alert.title
        assert "Internet connection likely down" in alert.message

    def test_generate_missing_alert_with_probe_success(self):
        engine = RemoteAlertEngine()

        last_heartbeat = datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC)
        wan_states: dict[str, WANState] = {}

        alert = engine.create_monitor_lost_alert(
            last_heartbeat=last_heartbeat,
            wan_states=wan_states,
            probe_result=ProbeResult.REACHABLE,
        )

        assert "Local monitor may have crashed" in alert.message

    def test_generate_recovery_alert(self):
        engine = RemoteAlertEngine()
        alert = engine.create_monitor_recovered_alert()

        assert "RECOVERED" in alert.title
        assert alert.severity == AlertSeverity.INFO
