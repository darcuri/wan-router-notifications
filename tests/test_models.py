# tests/test_models.py
from datetime import UTC, datetime

from shared.models import (
    AlertEvent,
    AlertSeverity,
    HeartbeatPayload,
    InterfaceStatus,
    WANState,
)


class TestInterfaceStatus:
    def test_interface_status_enum_values(self):
        assert InterfaceStatus.UP.value == "up"
        assert InterfaceStatus.DOWN.value == "down"
        assert InterfaceStatus.UNKNOWN.value == "unknown"


class TestWANState:
    def test_wan_state_creation(self):
        state = WANState(
            interface="WAN1",
            status=InterfaceStatus.UP,
            since=datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC),
        )
        assert state.interface == "WAN1"
        assert state.status == InterfaceStatus.UP

    def test_wan_state_duration(self):
        now = datetime(2026, 2, 3, 15, 0, 0, tzinfo=UTC)
        state = WANState(
            interface="WAN1",
            status=InterfaceStatus.UP,
            since=datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC),
        )
        duration = state.duration_since(now)
        assert duration.total_seconds() == 3 * 60 * 60  # 3 hours

    def test_wan_state_with_link_up(self):
        state = WANState(
            interface="WAN1",
            status=InterfaceStatus.UP,
            since=datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC),
            link_up=True,
        )
        assert state.link_up is True

    def test_wan_state_link_up_defaults_none(self):
        state = WANState(
            interface="WAN1",
            status=InterfaceStatus.UP,
            since=datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC),
        )
        assert state.link_up is None


class TestHeartbeatPayload:
    def test_heartbeat_payload_creation(self):
        payload = HeartbeatPayload(
            timestamp=datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC),
            wan_states={
                "WAN1": WANState(
                    interface="WAN1",
                    status=InterfaceStatus.UP,
                    since=datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC),

                ),
            },
            recent_events=[],
        )
        assert payload.timestamp.year == 2026
        assert "WAN1" in payload.wan_states

    def test_heartbeat_payload_serialization(self):
        payload = HeartbeatPayload(
            timestamp=datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC),
            wan_states={},
            recent_events=[],
        )
        json_data = payload.model_dump_json()
        assert "2026-02-03" in json_data


class TestAlertSeverity:
    def test_severity_ordering(self):
        assert AlertSeverity.CRITICAL.value > AlertSeverity.WARNING.value
        assert AlertSeverity.WARNING.value > AlertSeverity.INFO.value


class TestAlertEvent:
    def test_alert_event_creation(self):
        event = AlertEvent(
            severity=AlertSeverity.CRITICAL,
            category="wan",
            title="WAN1 DOWN",
            message="WAN1 interface went down",
            timestamp=datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC),
        )
        assert event.severity == AlertSeverity.CRITICAL
        assert event.category == "wan"
