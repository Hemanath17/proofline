"""`GET /api/readiness` and `POST /api/readiness/{item}/confirm`."""

from fastapi.testclient import TestClient

PRIYA = "st-01"  # preparer
CLIENT = "cu-01"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_get_readiness_lists_every_item(client: TestClient) -> None:
    response = client.get("/api/readiness", headers=_headers(PRIYA))
    assert response.status_code == 200
    body = response.json()
    assert body["ready_to_file"] is False
    item_names = {item["item"] for item in body["items"]}
    assert "engagement_and_consents_signed" in item_names
    assert "identity_verified" in item_names
    for item in body["items"]:
        if not item["met"]:
            assert item["reasons"], f"{item['item']} is unmet with no reason"


def test_confirm_readiness_item_as_staff(client: TestClient) -> None:
    response = client.post(
        "/api/readiness/due_diligence_done/confirm",
        json={"note": "Form 8867 reviewed"},
        headers=_headers(PRIYA),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["item"] == "due_diligence_done"
    assert body["confirmed_by"] == PRIYA

    report = client.get("/api/readiness", headers=_headers(PRIYA)).json()
    item = next(i for i in report["items"] if i["item"] == "due_diligence_done")
    assert item["met"] is True


def test_confirm_readiness_item_as_client_returns_403(client: TestClient) -> None:
    response = client.post(
        "/api/readiness/due_diligence_done/confirm",
        json={"note": "x"},
        headers=_headers(CLIENT),
    )
    assert response.status_code == 403


def test_confirm_readiness_item_unknown_item_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/readiness/not_a_real_item/confirm",
        json={"note": "x"},
        headers=_headers(PRIYA),
    )
    assert response.status_code == 422
