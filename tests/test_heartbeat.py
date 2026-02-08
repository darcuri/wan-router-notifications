# tests/test_heartbeat.py
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from local.heartbeat import HeartbeatSender
from shared.models import HeartbeatPayload, InterfaceStatus, WANState


class TestHeartbeatSender:
    @pytest.mark.asyncio
    async def test_send_heartbeat_success(self):
        sender = HeartbeatSender(remote_url="http://100.64.0.1:8080/heartbeat")

        wan_states = {
            "WAN1": WANState(
                interface="WAN1",
                status=InterfaceStatus.UP,
                since=datetime.now(UTC),

            )
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(status_code=200)
            result = await sender.send(wan_states, [])
            assert result is True

    @pytest.mark.asyncio
    async def test_send_heartbeat_failure(self):
        sender = HeartbeatSender(remote_url="http://100.64.0.1:8080/heartbeat")

        wan_states = {}

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = Exception("Connection refused")
            result = await sender.send(wan_states, [])
            assert result is False

    def test_build_payload(self):
        sender = HeartbeatSender(remote_url="http://100.64.0.1:8080/heartbeat")

        wan_states = {
            "WAN1": WANState(
                interface="WAN1",
                status=InterfaceStatus.UP,
                since=datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC),

            )
        }

        payload = sender.build_payload(wan_states, [])
        assert isinstance(payload, HeartbeatPayload)
        assert "WAN1" in payload.wan_states
        assert payload.monitor_version == "0.1.0"
