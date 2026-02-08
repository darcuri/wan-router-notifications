# remote/heartbeat_receiver.py
"""Heartbeat receiver API for remote sentinel."""

import logging
from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

from shared.models import HeartbeatPayload, WANState

logger = logging.getLogger(__name__)


class HeartbeatResponse(BaseModel):
    status: str
    received_at: datetime


class HealthResponse(BaseModel):
    status: str
    last_heartbeat: datetime | None
    heartbeat_missing: bool


class HeartbeatStore:
    """Store and track heartbeat state."""

    def __init__(
        self,
        expected_interval: int = 60,
        missed_threshold: int = 3,
    ):
        self.expected_interval = expected_interval
        self.missed_threshold = missed_threshold
        self.last_heartbeat: datetime | None = None
        self.last_payload: HeartbeatPayload | None = None
        self._alerted_missing = False

    def record(self, payload: HeartbeatPayload) -> None:
        """Record a received heartbeat."""
        self.last_heartbeat = datetime.now(UTC)
        self.last_payload = payload
        self._alerted_missing = False
        logger.debug(f"Heartbeat received from monitor v{payload.monitor_version}")

    def is_missing(self) -> bool:
        """Check if heartbeats are missing."""
        if self.last_heartbeat is None:
            return True

        now = datetime.now(UTC)
        elapsed = (now - self.last_heartbeat).total_seconds()
        threshold = self.expected_interval * self.missed_threshold

        return elapsed > threshold

    def should_alert_missing(self) -> bool:
        """Check if we should alert about missing heartbeat (once)."""
        if self.is_missing() and not self._alerted_missing:
            self._alerted_missing = True
            return True
        return False

    def get_last_wan_states(self) -> dict[str, "WANState"]:
        """Get last known WAN states."""
        if self.last_payload:
            return self.last_payload.wan_states
        return {}


# Global store instance (will be replaced in app factory)
_store: HeartbeatStore | None = None


def create_app(store: HeartbeatStore | None = None) -> FastAPI:
    """Create FastAPI application."""
    global _store
    _store = store or HeartbeatStore()

    app = FastAPI(title="WAN Router Sentinel")

    @app.post("/heartbeat", response_model=HeartbeatResponse)
    async def receive_heartbeat(payload: HeartbeatPayload) -> HeartbeatResponse:
        """Receive heartbeat from local monitor."""
        _store.record(payload)
        return HeartbeatResponse(
            status="ok",
            received_at=datetime.now(UTC),
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Health check endpoint."""
        return HealthResponse(
            status="ok",
            last_heartbeat=_store.last_heartbeat,
            heartbeat_missing=_store.is_missing(),
        )

    return app
