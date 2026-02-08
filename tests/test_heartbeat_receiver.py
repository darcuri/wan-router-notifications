# tests/test_heartbeat_receiver.py
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from remote.heartbeat_receiver import HeartbeatStore, create_app
from shared.models import HeartbeatPayload


class TestHeartbeatStore:
    def test_store_initial_heartbeat(self):
        store = HeartbeatStore()
        payload = HeartbeatPayload(
            timestamp=datetime.now(UTC),
            wan_states={},
            recent_events=[],
        )
        store.record(payload)
        assert store.last_heartbeat is not None
        assert store.last_payload == payload

    def test_is_missing_when_no_heartbeat(self):
        store = HeartbeatStore(expected_interval=60, missed_threshold=3)
        assert store.is_missing() is True

    def test_is_not_missing_when_recent(self):
        store = HeartbeatStore(expected_interval=60, missed_threshold=3)
        payload = HeartbeatPayload(
            timestamp=datetime.now(UTC),
            wan_states={},
            recent_events=[],
        )
        store.record(payload)
        assert store.is_missing() is False

    def test_is_missing_when_stale(self):
        store = HeartbeatStore(expected_interval=60, missed_threshold=3)
        payload = HeartbeatPayload(
            timestamp=datetime.now(UTC) - timedelta(minutes=5),
            wan_states={},
            recent_events=[],
        )
        store.record(payload)
        # Simulate time passing
        store.last_heartbeat = datetime.now(UTC) - timedelta(minutes=5)
        assert store.is_missing() is True


class TestHeartbeatAPI:
    def test_receive_heartbeat(self):
        app = create_app()
        client = TestClient(app)

        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "wan_states": {},
            "recent_events": [],
            "monitor_version": "0.1.0",
        }

        response = client.post("/heartbeat", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_endpoint(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
