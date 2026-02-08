# tests/test_snmp_poller.py
import pytest

from local.snmp_poller import MockSNMPPoller, SNMPPoller
from shared.models import InterfaceStatus

WAN_GATEWAYS = {"WAN1": "192.168.1.254", "WAN2": "192.168.1.1"}
WAN_INTERFACES = {"WAN1": 4, "WAN2": 5}


class TestMockSNMPPoller:
    @pytest.mark.asyncio
    async def test_default_active_wan_is_wan1(self):
        poller = MockSNMPPoller(wan_gateways=WAN_GATEWAYS)
        states = await poller.poll()
        assert states["WAN1"].status == InterfaceStatus.UP
        assert states["WAN2"].status == InterfaceStatus.DOWN

    @pytest.mark.asyncio
    async def test_failover_to_wan2(self):
        poller = MockSNMPPoller(wan_gateways=WAN_GATEWAYS)
        poller.set_active_wan("WAN2")
        states = await poller.poll()
        assert states["WAN1"].status == InterfaceStatus.DOWN
        assert states["WAN2"].status == InterfaceStatus.UP

    @pytest.mark.asyncio
    async def test_since_preserved_on_same_status(self):
        poller = MockSNMPPoller(wan_gateways=WAN_GATEWAYS)
        states1 = await poller.poll()
        states2 = await poller.poll()
        # WAN1 stayed UP, so 'since' should be preserved
        assert states2["WAN1"].since == states1["WAN1"].since

    @pytest.mark.asyncio
    async def test_since_updated_on_status_change(self):
        poller = MockSNMPPoller(wan_gateways=WAN_GATEWAYS)
        states1 = await poller.poll()
        wan1_since_up = states1["WAN1"].since

        poller.set_active_wan("WAN2")
        states2 = await poller.poll()
        # WAN1 went from UP to DOWN, so 'since' should be updated
        assert states2["WAN1"].since > wan1_since_up

    @pytest.mark.asyncio
    async def test_set_active_wan_rejects_unknown(self):
        poller = MockSNMPPoller(wan_gateways=WAN_GATEWAYS)
        with pytest.raises(ValueError, match="Unknown WAN"):
            poller.set_active_wan("WAN3")

    @pytest.mark.asyncio
    async def test_default_gateways_used_when_none(self):
        poller = MockSNMPPoller()
        states = await poller.poll()
        assert "WAN1" in states
        assert "WAN2" in states

    @pytest.mark.asyncio
    async def test_link_up_defaults_none_without_interfaces(self):
        poller = MockSNMPPoller(wan_gateways=WAN_GATEWAYS)
        states = await poller.poll()
        assert states["WAN1"].link_up is None

    @pytest.mark.asyncio
    async def test_link_up_true_when_interface_configured(self):
        poller = MockSNMPPoller(wan_gateways=WAN_GATEWAYS, wan_interfaces=WAN_INTERFACES)
        states = await poller.poll()
        assert states["WAN1"].link_up is True
        assert states["WAN2"].link_up is True

    @pytest.mark.asyncio
    async def test_link_down_on_failed_interface(self):
        poller = MockSNMPPoller(wan_gateways=WAN_GATEWAYS, wan_interfaces=WAN_INTERFACES)
        poller.set_link_down("WAN1")
        states = await poller.poll()
        assert states["WAN1"].link_up is False
        assert states["WAN2"].link_up is True


class TestSNMPPoller:
    @pytest.mark.asyncio
    async def test_poller_creation(self):
        poller = SNMPPoller(
            host="192.168.0.1",
            username="testuser",
            auth_key="testpass",
            wan_gateways=WAN_GATEWAYS,
            auth_protocol="MD5",
            port=161,
        )
        assert poller.host == "192.168.0.1"
        assert poller.username == "testuser"
        assert poller.auth_key == "testpass"
        assert poller.wan_gateways == WAN_GATEWAYS

    @pytest.mark.asyncio
    async def test_gateway_reverse_map(self):
        poller = SNMPPoller(
            host="192.168.0.1",
            username="testuser",
            auth_key="testpass",
            wan_gateways=WAN_GATEWAYS,
        )
        assert poller._gateway_to_wan == {
            "192.168.1.254": "WAN1",
            "192.168.1.1": "WAN2",
        }

    @pytest.mark.asyncio
    async def test_poller_with_wan_interfaces(self):
        poller = SNMPPoller(
            host="192.168.0.1",
            username="testuser",
            auth_key="testpass",
            wan_gateways=WAN_GATEWAYS,
            wan_interfaces=WAN_INTERFACES,
        )
        assert poller.wan_interfaces == WAN_INTERFACES
