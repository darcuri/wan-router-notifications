# tests/test_dns_monitor.py
from unittest.mock import patch

from remote.dns_monitor import DnsMonitor
from shared.models import AlertSeverity


class TestDnsMonitor:
    def test_first_check_records_ip_no_alert(self):
        monitor = DnsMonitor(hostname="example.duckdns.org", expected_ip="1.2.3.4")
        with patch("remote.dns_monitor.resolve_hostname", return_value="1.2.3.4"):
            alerts = monitor.check()
        assert len(alerts) == 0
        assert monitor.last_seen_ip == "1.2.3.4"

    def test_ip_changed_from_last_known(self):
        monitor = DnsMonitor(hostname="example.duckdns.org", expected_ip="1.2.3.4")
        monitor.last_seen_ip = "1.2.3.4"
        with patch("remote.dns_monitor.resolve_hostname", return_value="5.6.7.8"):
            alerts = monitor.check()
        assert len(alerts) >= 1
        titles = [a.title for a in alerts]
        assert any("changed" in t.lower() for t in titles)

    def test_ip_matches_expected_no_alert(self):
        monitor = DnsMonitor(hostname="example.duckdns.org", expected_ip="1.2.3.4")
        monitor.last_seen_ip = "1.2.3.4"
        with patch("remote.dns_monitor.resolve_hostname", return_value="1.2.3.4"):
            alerts = monitor.check()
        assert len(alerts) == 0

    def test_ip_differs_from_expected(self):
        monitor = DnsMonitor(hostname="example.duckdns.org", expected_ip="1.2.3.4")
        with patch("remote.dns_monitor.resolve_hostname", return_value="5.6.7.8"):
            alerts = monitor.check()
        assert any(a.severity == AlertSeverity.CRITICAL for a in alerts)

    def test_dns_resolution_failure_single_no_alert(self):
        monitor = DnsMonitor(hostname="example.duckdns.org", expected_ip="1.2.3.4")
        with patch("remote.dns_monitor.resolve_hostname", return_value=None):
            alerts = monitor.check()
        assert len(alerts) == 0
        assert monitor.consecutive_failures == 1

    def test_dns_resolution_failure_multiple_alerts(self):
        monitor = DnsMonitor(hostname="example.duckdns.org", expected_ip="1.2.3.4")
        with patch("remote.dns_monitor.resolve_hostname", return_value=None):
            monitor.check()  # failure 1 — no alert
            alerts = monitor.check()  # failure 2 — alert
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING
