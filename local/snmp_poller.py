"""SNMP polling for WAN router — default route gateway monitoring."""

import asyncio
import logging
from datetime import UTC, datetime

from pysnmp.hlapi.v3arch.asyncio import (
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    get_cmd,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
)

from shared.models import InterfaceStatus, WANState

logger = logging.getLogger(__name__)

# ipRouteNextHop for default route 0.0.0.0
IP_ROUTE_NEXT_HOP = "1.3.6.1.2.1.4.21.1.7.0.0.0.0"
# ifOperStatus base OID — append .ifIndex for each interface
IF_OPER_STATUS_BASE = "1.3.6.1.2.1.2.2.1.8"


class SNMPPoller:
    """Poll router via SNMP for active WAN via default route next-hop."""

    def __init__(
        self,
        host: str,
        username: str,
        auth_key: str,
        wan_gateways: dict[str, str],
        wan_interfaces: dict[str, int] | None = None,
        auth_protocol: str = "MD5",
        port: int = 161,
        timeout: int = 5,
    ):
        self.host = host
        self.username = username
        self.auth_key = auth_key
        self.wan_gateways = wan_gateways
        self.wan_interfaces = wan_interfaces or {}
        auth_protocols = {"MD5": usmHMACMD5AuthProtocol, "SHA": usmHMACSHAAuthProtocol}
        self._auth_protocol = auth_protocols[auth_protocol.upper()]
        self.port = port
        self.timeout = timeout
        self._engine = SnmpEngine()
        self._last_states: dict[str, WANState] = {}
        self._last_unknown_gateway: str | None = None
        # Reverse map: gateway IP → WAN name
        self._gateway_to_wan = {gw: name for name, gw in wan_gateways.items()}

    async def _get_next_hop(self) -> str | None:
        """Get the default route next-hop gateway IP."""
        try:
            error_indication, error_status, _error_index, var_binds = await get_cmd(
                self._engine,
                UsmUserData(self.username, self.auth_key, authProtocol=self._auth_protocol),
                await UdpTransportTarget.create((self.host, self.port), timeout=self.timeout),
                ContextData(),
                ObjectType(ObjectIdentity(IP_ROUTE_NEXT_HOP)),
            )

            if error_indication or error_status:
                logger.error(f"SNMP error: {error_indication or error_status}")
                return None

            for var_bind in var_binds:
                return str(var_bind[1].prettyPrint())
            return None
        except Exception as e:
            logger.error(f"SNMP query failed: {e}")
            return None

    async def _get_if_oper_status(self) -> dict[str, bool]:
        """Get ifOperStatus for configured WAN interfaces. Returns {WAN_name: link_is_up}."""
        if not self.wan_interfaces:
            return {}

        results: dict[str, bool] = {}
        for name, if_index in self.wan_interfaces.items():
            oid = f"{IF_OPER_STATUS_BASE}.{if_index}"
            try:
                error_indication, error_status, _error_index, var_binds = await get_cmd(
                    self._engine,
                    UsmUserData(self.username, self.auth_key, authProtocol=self._auth_protocol),
                    await UdpTransportTarget.create((self.host, self.port), timeout=self.timeout),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                )
                if error_indication or error_status:
                    err = error_indication or error_status
                    logger.error(f"SNMP ifOperStatus error for {name}: {err}")
                    continue
                for var_bind in var_binds:
                    # ifOperStatus: 1=up, 2=down, 3=testing, etc.
                    results[name] = int(var_bind[1]) == 1
            except Exception as e:
                logger.error(f"SNMP ifOperStatus query failed for {name}: {e}")

        return results

    async def poll(self) -> dict[str, WANState]:
        """Poll default route and ifOperStatus to determine WAN states."""
        states: dict[str, WANState] = {}
        now = datetime.now(UTC)

        next_hop = await self._get_next_hop()
        active_wan = self._gateway_to_wan.get(next_hop) if next_hop else None

        if next_hop and not active_wan:
            if next_hop != self._last_unknown_gateway:
                logger.warning(f"Unknown next-hop gateway: {next_hop}")
                self._last_unknown_gateway = next_hop
        else:
            self._last_unknown_gateway = None

        link_status = await self._get_if_oper_status()

        for name in self.wan_gateways:
            status = InterfaceStatus.UP if name == active_wan else InterfaceStatus.DOWN

            # Preserve 'since' timestamp when status hasn't changed
            previous = self._last_states.get(name)
            if previous and previous.status == status:
                since = previous.since
            else:
                since = now

            states[name] = WANState(
                interface=name,
                status=status,
                since=since,
                link_up=link_status.get(name),
            )

        self._last_states = states
        return states


class MockSNMPPoller:
    """Mock SNMP poller for testing without real router."""

    def __init__(
        self,
        wan_gateways: dict[str, str] | None = None,
        wan_interfaces: dict[str, int] | None = None,
        failure_rate: float = 0.0,
    ):
        self.wan_gateways = wan_gateways or {"WAN1": "192.168.1.254", "WAN2": "192.168.1.1"}
        self.wan_interfaces = wan_interfaces or {}
        self.failure_rate = failure_rate
        self._active_wan: str = "WAN1"
        self._last_states: dict[str, WANState] = {}
        self._links_down: set[str] = set()

    def set_active_wan(self, wan_name: str) -> None:
        """Set which WAN is the active gateway."""
        if wan_name not in self.wan_gateways:
            raise ValueError(f"Unknown WAN: {wan_name}")
        self._active_wan = wan_name

    def set_link_down(self, wan_name: str) -> None:
        """Simulate physical link failure on a WAN interface."""
        if wan_name not in self.wan_gateways:
            raise ValueError(f"Unknown WAN: {wan_name}")
        self._links_down.add(wan_name)

    def set_link_up(self, wan_name: str) -> None:
        """Restore physical link on a WAN interface."""
        self._links_down.discard(wan_name)

    async def poll(self) -> dict[str, WANState]:
        """Return mock WAN states based on active gateway."""
        await asyncio.sleep(0.1)  # Simulate network delay
        now = datetime.now(UTC)
        states: dict[str, WANState] = {}

        for name in self.wan_gateways:
            status = InterfaceStatus.UP if name == self._active_wan else InterfaceStatus.DOWN

            previous = self._last_states.get(name)
            if previous and previous.status == status:
                since = previous.since
            else:
                since = now

            link_up = None
            if self.wan_interfaces:
                link_up = name not in self._links_down

            states[name] = WANState(
                interface=name,
                status=status,
                since=since,
                link_up=link_up,
            )

        self._last_states = states
        return states
