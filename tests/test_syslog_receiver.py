# tests/test_syslog_receiver.py
from pathlib import Path

from local.syslog_receiver import SyslogReceiver, categorize_message, parse_syslog_message

FIXTURES = Path(__file__).parent / "fixtures" / "syslog_samples"


class TestParseSyslogMessage:
    def test_parse_standard_syslog(self):
        raw = "<134>Feb  3 12:34:56 ER605 authpriv: User admin login failed from 192.168.0.100"
        event = parse_syslog_message(raw)
        assert event is not None
        assert event.hostname == "ER605"
        assert "login failed" in event.message

    def test_parse_malformed_returns_none(self):
        raw = "not a valid syslog message"
        event = parse_syslog_message(raw)
        assert event is None

    def test_parse_multi_word_tag(self):
        raw = (
            "<133>Feb  6 19:31:01 ER605 Link Backup:"
            " [osg:0C-EF-15-05-2C-DF] Backup [WAN/LAN2] took effect."
        )
        event = parse_syslog_message(raw)
        assert event is not None
        assert event.hostname == "ER605"
        assert "Backup" in event.message
        assert event.category == "wan"
        assert event.metadata["wan_interface"] == "WAN/LAN2"


class TestCategorizeMessage:
    def test_categorize_auth_message(self):
        msg = "User admin login failed from 192.168.0.100"
        category, metadata = categorize_message(msg)
        assert category == "auth"

    def test_categorize_firewall_message(self):
        msg = "Blocked incoming connection from 10.0.0.1:443"
        category, metadata = categorize_message(msg)
        assert category == "firewall"

    def test_categorize_vpn_message(self):
        msg = "IPsec tunnel established with peer 203.0.113.1"
        category, metadata = categorize_message(msg)
        assert category == "vpn"

    def test_categorize_system_message(self):
        msg = "System rebooted"
        category, metadata = categorize_message(msg)
        assert category == "system"


class TestCategorizeWanEvent:
    def test_failover_activated(self):
        msg = "[osg:0C-EF-15-05-2C-DF] Backup [WAN/LAN2] took effect."
        category, metadata = categorize_message(msg)
        assert category == "wan"
        assert metadata["wan_event_type"] == "failover_activated"
        assert metadata["wan_interface"] == "WAN/LAN2"

    def test_failover_deactivated(self):
        msg = "[osg:0C-EF-15-05-2C-DF] Backup [WAN/LAN2] was down."
        category, metadata = categorize_message(msg)
        assert category == "wan"
        assert metadata["wan_event_type"] == "failover_deactivated"
        assert metadata["wan_interface"] == "WAN/LAN2"

    def test_physical_link_down(self):
        msg = "[osg:0C-EF-15-05-2C-DF]: The physical connection status of [WAN1] was down."
        category, metadata = categorize_message(msg)
        assert category == "wan"
        assert metadata["wan_event_type"] == "link_down"
        assert metadata["wan_interface"] == "WAN1"

    def test_online_detection_offline(self):
        msg = "[osg:0C-EF-15-05-2C-DF]: The online detection result of [WAN1] was offline."
        category, metadata = categorize_message(msg)
        assert category == "wan"
        assert metadata["wan_event_type"] == "online_detection"
        assert metadata["wan_interface"] == "WAN1"

    def test_online_detection_online(self):
        msg = (
            "[osg:0C-EF-15-05-2C-DF][alertLogResolve]:"
            " The online detection result of [WAN/LAN2] was online."
        )
        category, metadata = categorize_message(msg)
        assert category == "wan"
        assert metadata["wan_event_type"] == "online_detection"
        assert metadata["wan_interface"] == "WAN/LAN2"

    def test_non_wan_message_returns_no_metadata(self):
        msg = "User admin login failed from 192.168.0.100"
        category, metadata = categorize_message(msg)
        assert category == "auth"
        assert metadata == {}


class TestSyslogReceiver:
    def test_receiver_creation(self):
        receiver = SyslogReceiver(port=5514, bind_address="127.0.0.1")
        assert receiver.port == 5514
        assert receiver.bind_address == "127.0.0.1"
