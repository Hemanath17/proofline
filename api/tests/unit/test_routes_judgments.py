"""`GET`/`POST /api/judgments`, `GET /api/due-diligence`."""

from fastapi.testclient import TestClient

DANIEL = "st-02"  # reviewer
CLIENT = "cu-01"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_record_judgment_then_list(client: TestClient) -> None:
    response = client.post(
        "/api/judgments",
        json={
            "authority": "IRC 179",
            "approved_by": "st-02",
            "reasoning": "elected section 179",
            "is_election": True,
            "what_if_id": "equipment_section179",
        },
        headers=_headers(DANIEL),
    )
    assert response.status_code == 200

    listed = client.get("/api/judgments", headers=_headers(DANIEL)).json()
    assert len(listed["judgments"]) == 1
    assert listed["judgments"][0]["what_if_id"] == "equipment_section179"


def test_judgments_blocked_for_client(client: TestClient) -> None:
    response = client.get("/api/judgments", headers=_headers(CLIENT))
    assert response.status_code == 403


def test_due_diligence_checklist_has_items_and_a_done_status(
    client: TestClient,
) -> None:
    response = client.get("/api/due-diligence", headers=_headers(DANIEL))
    assert response.status_code == 200
    body = response.json()
    assert body["checklist"]
    assert body["done"] is False

    confirm = client.post(
        "/api/readiness/due_diligence_done/confirm",
        json={"note": "Form 8867 reviewed"},
        headers=_headers(DANIEL),
    )
    assert confirm.status_code == 200
    after = client.get("/api/due-diligence", headers=_headers(DANIEL)).json()
    assert after["done"] is True
