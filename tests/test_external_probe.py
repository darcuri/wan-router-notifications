# tests/test_external_probe.py
from unittest.mock import AsyncMock, patch

import pytest

from remote.external_probe import ExternalProbe, ProbeResult


class TestExternalProbe:
    @pytest.mark.asyncio
    async def test_probe_success(self):
        probe = ExternalProbe(target_ip="93.184.216.34", timeout=5)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = await probe.check()
            assert result == ProbeResult.REACHABLE

    @pytest.mark.asyncio
    async def test_probe_failure(self):
        probe = ExternalProbe(target_ip="192.0.2.1", timeout=1)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("Connection timeout")

            result = await probe.check()
            assert result == ProbeResult.UNREACHABLE

    def test_probe_disabled(self):
        probe = ExternalProbe(target_ip="", enabled=False)
        assert probe.enabled is False
