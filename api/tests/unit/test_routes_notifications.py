"""`GET /api/notifications` (B14, B26)."""

import time

from fastapi.testclient import TestClient

DANIEL = "st-02"  # reviewer
CLIENT = "cu-01"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_notifications_has_the_three_sections(client: TestClient) -> None:
    response = client.get("/api/notifications", headers=_headers(DANIEL))
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"needs_me", "changed", "deadlines"}
    assert body["deadlines"], "the packet's own firm.deadlines should show up"


def test_notifications_changed_reflects_a_revisit(client: TestClient) -> None:
    synced = client.post("/api/cases/sync", headers=_headers(DANIEL))
    cases = synced.json()["cases"]
    assert cases, "the real packet should produce at least one case"
    case_id = cases[0]["case_id"]

    # First view establishes last_seen.
    first = client.get(f"/api/cases/{case_id}", headers=_headers(DANIEL))
    assert first.status_code == 200
    before = client.get("/api/notifications", headers=_headers(DANIEL)).json()
    assert not any(c["entity_id"] == case_id for c in before["changed"])

    # SQLite's `onupdate=func.now()` only has second resolution; sleeping
    # past a full second keeps this comparable to real Postgres timing
    # without it (see docs/DECISIONS.md's other SQLite-timestamp notes).
    time.sleep(1.1)

    # A pick-up changes the case after last_seen.
    revision = first.json()["revision"]
    picked_up = client.post(
        f"/api/cases/{case_id}/pick-up",
        json={"expected_revision": revision},
        headers={"X-Proofline-Actor": "st-01"},
    )
    assert picked_up.status_code == 200

    after = client.get("/api/notifications", headers=_headers(DANIEL)).json()
    assert any(c["entity_id"] == case_id for c in after["changed"])


def test_notifications_blocked_for_client(client: TestClient) -> None:
    response = client.get("/api/notifications", headers=_headers(CLIENT))
    assert response.status_code == 403
