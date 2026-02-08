# tests/test_telegram.py
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from shared.models import InterfaceStatus, WANState
from shared.telegram import TelegramNotifier, format_wan_down_message, format_wan_up_message


class TestMessageFormatting:
    def test_format_wan_down_message(self):
        state = WANState(
            interface="WAN1",
            status=InterfaceStatus.DOWN,
            since=datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC),

        )
        msg = format_wan_down_message(
            state,
            router_ip="192.168.0.1",
            previous_uptime="3d 4h 12m",
        )
        assert "WAN1 DOWN" in msg
        assert "192.168.0.1" in msg
        assert "3d 4h 12m" in msg

    def test_format_wan_up_message(self):
        state = WANState(
            interface="WAN1",
            status=InterfaceStatus.UP,
            since=datetime(2026, 2, 3, 12, 0, 0, tzinfo=UTC),

        )
        msg = format_wan_up_message(
            state,
            router_ip="192.168.0.1",
            downtime="3m 17s",
        )
        assert "WAN1 RECOVERED" in msg
        assert "192.168.0.1" in msg
        assert "3m 17s" in msg


class TestTelegramNotifier:
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        notifier = TelegramNotifier(
            bot_token="test-token",
            chat_id="12345",
        )
        with patch.object(notifier, "_bot") as mock_bot:
            mock_bot.send_message = AsyncMock(return_value=True)
            result = await notifier.send_message("Test message")
            assert result is True
            mock_bot.send_message.assert_called_once()

    def test_notifier_mock_mode(self):
        notifier = TelegramNotifier(
            bot_token="",
            chat_id="",
            mock_mode=True,
        )
        assert notifier.mock_mode is True
