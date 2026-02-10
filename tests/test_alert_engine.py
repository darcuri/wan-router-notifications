# tests/test_alert_engine.py
from datetime import UTC, datetime, timedelta

from local.alert_engine import AlertEngine, AlertState
from shared.models import AlertSeverity, InterfaceStatus, SyslogEvent, WANState


class TestAlertState:
    def test_initial_state(self):
        state = AlertState()
        assert state.current_status == InterfaceStatus.UNKNOWN
        assert state.last_alert_time is None

    def test_should_alert_on_first_down(self):
        state = AlertState()
        state.current_status = InterfaceStatus.UP
        assert state.should_alert(InterfaceStatus.DOWN) is True

    def test_should_not_alert_same_status(self):
        state = AlertState()
        state.current_status = InterfaceStatus.DOWN
        state.last_alert_time = datetime.now(UTC)
        assert state.should_alert(InterfaceStatus.DOWN) is False

    def test_should_alert_on_recovery(self):
        state = AlertState()
        state.current_status = InterfaceStatus.DOWN
        assert state.should_alert(InterfaceStatus.UP) is True


class TestAlertEngine:
    def test_process_wan_state_detects_down(self):
        engine = AlertEngine()
        # First poll - establish baseline
        state_up = WANState(
            interface="WAN1",
            status=InterfaceStatus.UP,
            since=datetime.now(UTC),
        )
        events = engine.process_wan_state(state_up)
        assert len(events) == 0  # No alert for initial UP

        # Second poll - goes down
        state_down = WANState(
            interface="WAN1",
            status=InterfaceStatus.DOWN,
            since=datetime.now(UTC),
        )
        events = engine.process_wan_state(state_down)
        assert len(events) == 1
        assert events[0].severity == AlertSeverity.CRITICAL
        assert "DOWN" in events[0].title

    def test_process_wan_state_detects_recovery(self):
        engine = AlertEngine()
        # Establish down state
        state_down = WANState(
            interface="WAN1",
            status=InterfaceStatus.DOWN,
            since=datetime.now(UTC) - timedelta(minutes=5),
        )
        engine.process_wan_state(state_down)

        # Recovery
        state_up = WANState(
            interface="WAN1",
            status=InterfaceStatus.UP,
            since=datetime.now(UTC),
        )
        events = engine.process_wan_state(state_up)
        assert len(events) == 1
        assert "RECOVERED" in events[0].title

    def test_non_wan_syslog_ignored(self):
        engine = AlertEngine()
        event = SyslogEvent(
            timestamp=datetime.now(UTC),
            facility="authpriv",
            severity="warning",
            hostname="ER605",
            message="User admin login failed from 192.168.0.100",
            category="auth",
        )
        alerts = engine.process_syslog_event(event)
        assert len(alerts) == 0


class TestAlertEngineWanSyslog:
    def test_failover_activated_generates_critical_alert(self):
        engine = AlertEngine()
        event = SyslogEvent(
            timestamp=datetime.now(UTC),
            facility="Link Backup",
            severity="notice",
            hostname="ER605",
            message="[osg:0C-EF-15-05-2C-DF] Backup [WAN/LAN2] took effect.",
            category="wan",
            metadata={"wan_event_type": "failover_activated", "wan_interface": "WAN/LAN2"},
        )
        alerts = engine.process_syslog_event(event)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL
        assert "WAN/LAN2" in alerts[0].title

    def test_failover_deactivated_generates_critical_alert(self):
        engine = AlertEngine()
        event = SyslogEvent(
            timestamp=datetime.now(UTC),
            facility="Link Backup",
            severity="notice",
            hostname="ER605",
            message="[osg:0C-EF-15-05-2C-DF] Backup [WAN/LAN2] was down.",
            category="wan",
            metadata={"wan_event_type": "failover_deactivated", "wan_interface": "WAN/LAN2"},
        )
        alerts = engine.process_syslog_event(event)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL
        assert "WAN/LAN2" in alerts[0].title

    def test_link_down_generates_warning_alert(self):
        engine = AlertEngine()
        event = SyslogEvent(
            timestamp=datetime.now(UTC),
            facility="SWITCH",
            severity="notice",
            hostname="ER605",
            message="[osg:0C-EF-15-05-2C-DF]: The physical connection status of [WAN1] was down.",
            category="wan",
            metadata={"wan_event_type": "link_down", "wan_interface": "WAN1"},
        )
        alerts = engine.process_syslog_event(event)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING
        assert "WAN1" in alerts[0].title

    def test_online_detection_generates_no_alert(self):
        engine = AlertEngine()
        event = SyslogEvent(
            timestamp=datetime.now(UTC),
            facility="ONLINE_DECTION",
            severity="notice",
            hostname="ER605",
            message="[osg:0C-EF-15-05-2C-DF]: The online detection result of [WAN1] was offline.",
            category="wan",
            metadata={"wan_event_type": "online_detection", "wan_interface": "WAN1"},
        )
        alerts = engine.process_syslog_event(event)
        assert len(alerts) == 0

    def test_wan_events_bypass_cooldown(self):
        engine = AlertEngine()
        event = SyslogEvent(
            timestamp=datetime.now(UTC),
            facility="SWITCH",
            severity="notice",
            hostname="ER605",
            message="[osg:0C-EF-15-05-2C-DF]: The physical connection status of [WAN1] was down.",
            category="wan",
            metadata={"wan_event_type": "link_down", "wan_interface": "WAN1"},
        )
        alerts1 = engine.process_syslog_event(event)
        assert len(alerts1) == 1
        alerts2 = engine.process_syslog_event(event)
        assert len(alerts2) == 1


class TestAlertEngineCombinedSignals:
    def test_gateway_down_link_down_is_critical(self):
        """Gateway DOWN + ifOperStatus DOWN = physical failure."""
        engine = AlertEngine()
        state_up = WANState(
            interface="WAN1",
            status=InterfaceStatus.UP,
            since=datetime.now(UTC),
            link_up=True,
        )
        engine.process_wan_state(state_up)
        state_down = WANState(
            interface="WAN1",
            status=InterfaceStatus.DOWN,
            since=datetime.now(UTC),
            link_up=False,
        )
        alerts = engine.process_wan_state(state_down)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL
        assert "physical link down" in alerts[0].message.lower()

    def test_gateway_down_link_up_mentions_upstream(self):
        """Gateway DOWN + ifOperStatus UP = likely upstream/ISP issue."""
        engine = AlertEngine()
        state_up = WANState(
            interface="WAN1",
            status=InterfaceStatus.UP,
            since=datetime.now(UTC),
            link_up=True,
        )
        engine.process_wan_state(state_up)
        state_down = WANState(
            interface="WAN1",
            status=InterfaceStatus.DOWN,
            since=datetime.now(UTC),
            link_up=True,
        )
        alerts = engine.process_wan_state(state_down)
        assert len(alerts) == 1
        assert "upstream" in alerts[0].message.lower() or "isp" in alerts[0].message.lower()

    def test_gateway_down_link_none_works_without_crash(self):
        """No ifOperStatus configured -- should still work as before."""
        engine = AlertEngine()
        state_up = WANState(
            interface="WAN1",
            status=InterfaceStatus.UP,
            since=datetime.now(UTC),
        )
        engine.process_wan_state(state_up)
        state_down = WANState(
            interface="WAN1",
            status=InterfaceStatus.DOWN,
            since=datetime.now(UTC),
        )
        alerts = engine.process_wan_state(state_down)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL
