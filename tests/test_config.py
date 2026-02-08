# tests/test_config.py
from pathlib import Path

import pytest

from shared.config import LocalConfig, RemoteConfig, load_local_config, load_remote_config

FIXTURES = Path(__file__).parent / "fixtures" / "config_samples"


class TestLocalConfig:
    def test_load_valid_local_config(self):
        config = load_local_config(FIXTURES / "valid_local.yaml")
        assert config.router.host == "192.168.0.1"
        assert config.router.snmp_username == "testuser"
        assert config.router.snmp_auth_key == "testpass"
        assert config.router.snmp_auth_protocol == "MD5"
        assert config.polling.normal_interval == 60
        assert config.polling.alert_interval == 15
        assert config.polling.recovery_threshold == 5

    def test_local_config_defaults(self):
        router = {
            "host": "192.168.0.1",
            "snmp_username": "testuser",
            "snmp_auth_key": "testpass",
            "snmp_auth_protocol": "MD5",
        }
        config = LocalConfig(router=router)
        assert config.polling.normal_interval == 60
        assert config.polling.alert_interval == 15

    def test_local_config_invalid_interval(self):
        router = {
            "host": "192.168.0.1",
            "snmp_username": "testuser",
            "snmp_auth_key": "testpass",
            "snmp_auth_protocol": "MD5",
        }
        with pytest.raises(ValueError):
            LocalConfig(
                router=router,
                polling={"normal_interval": 5},  # too low
            )

    def test_wan_interfaces_config(self):
        router = {
            "host": "192.168.0.1",
            "snmp_username": "testuser",
            "snmp_auth_key": "testpass",
            "snmp_auth_protocol": "MD5",
            "wan_interfaces": {"WAN1": 4, "WAN2": 5},
        }
        config = LocalConfig(router=router)
        assert config.router.wan_interfaces == {"WAN1": 4, "WAN2": 5}

    def test_wan_interfaces_defaults_empty(self):
        router = {
            "host": "192.168.0.1",
            "snmp_username": "testuser",
            "snmp_auth_key": "testpass",
            "snmp_auth_protocol": "MD5",
        }
        config = LocalConfig(router=router)
        assert config.router.wan_interfaces == {}


class TestRemoteConfig:
    def test_load_valid_remote_config(self):
        config = load_remote_config(FIXTURES / "valid_remote.yaml")
        assert config.heartbeat.expected_interval == 60
        assert config.heartbeat.missed_threshold == 3
        assert config.external_probe.enabled is True
        assert config.external_probe.target_ip == "203.0.113.1"

    def test_remote_config_defaults(self):
        config = RemoteConfig()
        assert config.heartbeat.expected_interval == 60
        assert config.heartbeat.missed_threshold == 3
        assert config.external_probe.enabled is False

    def test_dns_monitor_config(self):
        config = load_remote_config(FIXTURES / "valid_remote.yaml")
        assert config.dns_monitor.enabled is True
        assert config.dns_monitor.hostname == "example.duckdns.org"

    def test_dns_monitor_defaults(self):
        config = RemoteConfig()
        assert config.dns_monitor.enabled is False
        assert config.dns_monitor.hostname == ""
