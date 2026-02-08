"""Configuration loading and validation."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RouterConfig(BaseModel):
    """Router connection settings."""

    host: str
    name: str = "router"
    snmp_username: str
    snmp_auth_key: str
    snmp_auth_protocol: str = "MD5"
    snmp_port: int = 161
    snmp_timeout: int = 5
    wan_gateways: dict[str, str] = {}  # e.g. {"WAN1": "192.168.1.254", "WAN2": "192.168.1.1"}
    wan_interfaces: dict[str, int] = {}  # WAN name -> ifIndex for ifOperStatus polling

    @field_validator("snmp_auth_protocol")
    @classmethod
    def validate_snmp_auth_protocol(cls, v: str) -> str:
        v = v.upper()
        if v not in ("MD5", "SHA"):
            raise ValueError("snmp_auth_protocol must be 'MD5' or 'SHA'")
        return v


class PollingConfig(BaseModel):
    """SNMP polling intervals."""

    normal_interval: int = 60
    alert_interval: int = 15
    recovery_threshold: int = 5

    @field_validator("normal_interval", "alert_interval")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        if v < 10:
            raise ValueError("Interval must be at least 10 seconds")
        return v


class SyslogConfig(BaseModel):
    """Syslog receiver settings."""

    enabled: bool = True
    port: int = 514
    bind_address: str = "0.0.0.0"


class LocalHeartbeatConfig(BaseModel):
    """Heartbeat sender settings for local monitor."""

    remote_url: str = "http://100.64.0.1:8080/heartbeat"
    interval: int = 60
    timeout: int = 10


class LocalConfig(BaseModel):
    """Configuration for local monitor."""

    router: RouterConfig
    polling: PollingConfig = Field(default_factory=PollingConfig)
    syslog: SyslogConfig = Field(default_factory=SyslogConfig)
    heartbeat: LocalHeartbeatConfig = Field(default_factory=LocalHeartbeatConfig)


class RemoteHeartbeatConfig(BaseModel):
    """Heartbeat receiver settings for remote sentinel."""

    expected_interval: int = 60
    missed_threshold: int = 3
    listen_host: str = "100.64.0.1"
    listen_port: int = 8080


class ExternalProbeConfig(BaseModel):
    """External probe settings."""

    enabled: bool = False
    target_ip: str = ""
    interval: int = 300
    timeout: int = 10


class DnsMonitorConfig(BaseModel):
    """DNS monitoring settings for DuckDNS IP change detection."""

    enabled: bool = False
    hostname: str = ""
    expected_ip: str = ""
    interval: int = 300


class RemoteConfig(BaseModel):
    """Configuration for remote sentinel."""

    heartbeat: RemoteHeartbeatConfig = Field(default_factory=RemoteHeartbeatConfig)
    external_probe: ExternalProbeConfig = Field(default_factory=ExternalProbeConfig)
    dns_monitor: DnsMonitorConfig = Field(default_factory=DnsMonitorConfig)


class EnvConfig(BaseSettings):
    """Environment-based configuration (secrets)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    snmp_auth_key: str | None = None


def load_local_config(path: Path) -> LocalConfig:
    """Load local monitor configuration from YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return LocalConfig(**data)


def load_remote_config(path: Path) -> RemoteConfig:
    """Load remote sentinel configuration from YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return RemoteConfig(**data)
