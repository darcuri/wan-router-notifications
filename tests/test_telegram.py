# tests/test_telegram.py
import time
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


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_first_message_sends_immediately(self):
        notifier = TelegramNotifier(
            bot_token="test-token",
            chat_id="12345",
            min_interval_seconds=3,
        )
        with patch.object(notifier, "_bot") as mock_bot:
            mock_bot.send_message = AsyncMock(return_value=True)
            result = await notifier.send_message("first message")
        assert result is True
        mock_bot.send_message.assert_called_once()
        assert notifier._pending_message is None

    @pytest.mark.asyncio
    async def test_message_within_interval_is_queued(self):
        notifier = TelegramNotifier(
            bot_token="test-token",
            chat_id="12345",
            min_interval_seconds=3,
        )
        notifier._last_sent_time = time.monotonic()  # simulate a message just sent

        with patch.object(notifier, "_bot") as mock_bot:
            mock_bot.send_message = AsyncMock(return_value=True)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await notifier.send_message("queued message")

        assert result is True
        mock_bot.send_message.assert_not_called()
        assert notifier._pending_message == "queued message"
        assert notifier._send_task is not None

    @pytest.mark.asyncio
    async def test_only_latest_queued_message_sent(self):
        notifier = TelegramNotifier(
            bot_token="test-token",
            chat_id="12345",
            min_interval_seconds=3,
        )
        notifier._last_sent_time = time.monotonic()  # simulate a message just sent

        with patch.object(notifier, "_bot") as mock_bot:
            mock_bot.send_message = AsyncMock(return_value=True)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await notifier.send_message("intermediate message")
                await notifier.send_message("latest message")

                assert notifier._pending_message == "latest message"
                assert notifier._send_task is not None
                await notifier._send_task

        assert mock_bot.send_message.call_count == 1
        assert mock_bot.send_message.call_args.kwargs["text"] == "latest message"

    @pytest.mark.asyncio
    async def test_second_task_not_created_when_one_pending(self):
        notifier = TelegramNotifier(
            bot_token="test-token",
            chat_id="12345",
            min_interval_seconds=3,
        )
        notifier._last_sent_time = time.monotonic()

        with patch.object(notifier, "_bot") as mock_bot:
            mock_bot.send_message = AsyncMock(return_value=True)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await notifier.send_message("msg1")
                task_after_first = notifier._send_task
                await notifier.send_message("msg2")
                task_after_second = notifier._send_task

        assert task_after_first is task_after_second

    @pytest.mark.asyncio
    async def test_mock_mode_bypasses_rate_limiting(self):
        notifier = TelegramNotifier(
            bot_token="",
            chat_id="",
            mock_mode=True,
            min_interval_seconds=3,
        )
        notifier._last_sent_time = time.monotonic()  # would trigger rate limit normally

        result1 = await notifier.send_message("msg1")
        result2 = await notifier.send_message("msg2")

        assert result1 is True
        assert result2 is True
        assert notifier._pending_message is None  # nothing queued in mock mode
