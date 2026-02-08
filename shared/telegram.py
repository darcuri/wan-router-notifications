# shared/telegram.py
"""Telegram notification client."""

import logging
from datetime import UTC, datetime

from telegram import Bot
from telegram.error import TelegramError

from shared.models import AlertEvent, AlertSeverity, WANState

logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    seconds = int(seconds)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def format_wan_down_message(
    state: WANState,
    router_ip: str,
    previous_uptime: str,
    router_name: str = "router",
) -> str:
    """Format WAN down alert message."""
    timestamp = state.since.strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""🔴 {state.interface} DOWN
Router: {router_name} ({router_ip})
Time: {timestamp}
Previous state: UP for {previous_uptime}
Action: Monitoring at 15s intervals"""


def format_wan_up_message(
    state: WANState,
    router_ip: str,
    downtime: str,
    router_name: str = "router",
) -> str:
    """Format WAN recovery alert message."""
    timestamp = state.since.strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""🟢 {state.interface} RECOVERED
Router: {router_name} ({router_ip})
Time: {timestamp}
Downtime: {downtime}"""


def format_monitor_lost_message(
    last_heartbeat: datetime,
    wan_states: dict[str, WANState],
    probe_result: bool | None,
) -> str:
    """Format message when local monitor stops responding."""
    now = datetime.now(UTC)
    ago = format_duration((now - last_heartbeat).total_seconds())

    wan_summary = " | ".join(
        f"{name}: {state.status.value.upper()}" for name, state in wan_states.items()
    )

    probe_status = "FAILED" if probe_result is False else "SUCCESS" if probe_result else "N/A"
    diagnosis = (
        "Internet connection likely down"
        if probe_result is False
        else "Local monitor may have crashed"
        if probe_result is True
        else "Unknown"
    )

    return f"""🟠 CONNECTION LOST TO LOCAL MONITOR
Last heartbeat: {ago} ago
Last known state:
  {wan_summary}
External probe: {probe_status}
Diagnosis: {diagnosis}"""


class TelegramNotifier:
    """Send notifications via Telegram bot."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        mock_mode: bool = False,
    ):
        self.chat_id = chat_id
        self.mock_mode = mock_mode
        self._bot: Bot | None = None

        if not mock_mode and bot_token:
            self._bot = Bot(token=bot_token)

    async def send_message(self, text: str) -> bool:
        """Send a message to the configured chat."""
        if self.mock_mode:
            logger.info(f"[MOCK] Telegram message:\n{text}")
            return True

        if not self._bot:
            logger.warning("Telegram bot not configured, skipping notification")
            return False

        try:
            await self._bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=None,
            )
            return True
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_alert(self, event: AlertEvent) -> bool:
        """Send an alert event as a Telegram message."""
        severity_emoji = {
            AlertSeverity.CRITICAL: "🔴",
            AlertSeverity.WARNING: "🟠",
            AlertSeverity.INFO: "🔵",
        }
        emoji = severity_emoji.get(event.severity, "⚪")
        text = f"{emoji} {event.title}\n\n{event.message}"
        return await self.send_message(text)
