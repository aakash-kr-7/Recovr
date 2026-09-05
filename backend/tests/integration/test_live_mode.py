"""Integration coverage for deterministic demo playback controls."""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.api.demo as demo


def _wait_for(client: TestClient, minimum_events: int, timeout_seconds: float = 1.0) -> dict:
    """Poll the public status contract without depending on scheduler timing."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = client.get("/demo/live-mode/status").json()
        if status["transactions_fired"] >= minimum_events:
            return status
        time.sleep(0.005)
    pytest.fail(f"Live mode did not fire {minimum_events} events in time")


@pytest.fixture(autouse=True)
def stopped_live_mode():
    """No background playback may leak between tests."""
    with TestClient(app) as client:
        client.post("/demo/live-mode/stop")
        yield
        client.post("/demo/live-mode/stop")


def test_live_mode_is_ordered_stoppable_and_restarts_from_step_zero(monkeypatch):
    """The playback script is fixed, cancellable, and never resumes mid-script."""
    fired: list[tuple[str, float, str]] = []

    def record_pipeline(payload, source, db):
        # This is the shared /demo/simulate helper's call boundary. Replacing
        # persistence keeps this control-flow test free of LLM/network work.
        fired.append((payload.decline_reason, payload.amount_inr, source))
        return {"status": "processed"}

    monkeypatch.setattr(demo, "_simulate_transaction", record_pipeline)
    expected = [
        (preset["payload"]["decline_reason"], preset["payload"]["amount_inr"], "live_mode")
        for preset in demo._live_mode_presets()
    ]

    with TestClient(app) as client:
        started = client.post("/demo/live-mode/start", json={"interval_seconds": 0.01})
        assert started.status_code == 200
        assert started.json()["sequence_length"] == len(expected)

        _wait_for(client, minimum_events=3)
        stopped = client.post("/demo/live-mode/stop")
        assert stopped.status_code == 200
        assert client.get("/demo/live-mode/status").json()["is_running"] is False

        first_run = list(fired)
        assert first_run == expected[:len(first_run)]

        # Cancellation is awaited by the stop endpoint, so no extra event can
        # appear once it returns.
        time.sleep(0.04)
        assert fired == first_run

        restarted = client.post("/demo/live-mode/start", json={"interval_seconds": 0.01})
        assert restarted.status_code == 200
        restarted_status = _wait_for(client, minimum_events=2)
        assert restarted_status["current_step"] == restarted_status["transactions_fired"]
        client.post("/demo/live-mode/stop")

    second_run = fired[len(first_run):]
    assert second_run == expected[:len(second_run)]
    assert len(second_run) >= 2
