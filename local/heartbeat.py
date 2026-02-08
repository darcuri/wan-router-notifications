"""Heartbeat sender to remote sentinel."""

import logging
from datetime import UTC, datetime

import httpx

from shared.models import AlertEvent, HeartbeatPayload, WANState

logger = logging.getLogger(__name__)


class HeartbeatSender:
    """Send periodic heartbeats to remote sentinel."""

    def __init__(
        self,
        remote_url: str,
        timeout: int = 10,
    ):
        self.remote_url = remote_url
        self.timeout = timeout

    def build_payload(
        self,
        wan_states: dict[str, WANState],
        recent_events: list[AlertEvent],
    ) -> HeartbeatPayload:
        """Build heartbeat payload from current state."""
        return HeartbeatPayload(
            timestamp=datetime.now(UTC),
            wan_states=wan_states,
            recent_events=recent_events[-10:],  # Last 10 events
            monitor_version="0.1.0",
        )

    async def send(
        self,
        wan_states: dict[str, WANState],
        recent_events: list[AlertEvent],
    ) -> bool:
        """Send heartbeat to remote sentinel."""
        payload = self.build_payload(wan_states, recent_events)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.remote_url,
                    json=payload.model_dump(mode="json"),
                )
                if response.status_code == 200:
                    logger.debug("Heartbeat sent successfully")
                    return True
                else:
                    logger.warning(f"Heartbeat failed with status {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False
