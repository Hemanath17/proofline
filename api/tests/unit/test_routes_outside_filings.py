"""`GET /api/outside-filings`, `POST /api/outside-filings/{item}/confirm`."""

from fastapi.testclient import TestClient

PRIYA = "st-01"
CLIENT = "cu-01"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_get_outside_filings_lists_the_known_items(client: TestClient) -> None:
    response = client.get("/api/outside-filings", headers=_headers(PRIYA))
    assert response.status_code == 200
    items = {row["item"] for row in response.json()["items"]}
    assert items == {
        "fbar",
        "contractor_1099_nec",
        "form_3520_2023",
        "oregon_composite",
    }


def test_confirm_outside_filing_then_report_reflects_it(client: TestClient) -> None:
    response = client.post(
        "/api/outside-filings/fbar/confirm",
        json={"decision": "not_required", "note": "client filed separately"},
        headers=_headers(PRIYA),
    )
    assert response.status_code == 200

    report = client.get("/api/outside-filings", headers=_headers(PRIYA)).json()
    fbar = next(row for row in report["items"] if row["item"] == "fbar")
    assert fbar["decided"] is True
    assert fbar["decision"] == "not_required"


def test_outside_filings_blocked_for_client(client: TestClient) -> None:
    response = client.get("/api/outside-filings", headers=_headers(CLIENT))
    assert response.status_code == 403


def test_confirm_outside_filing_as_client_returns_403(client: TestClient) -> None:
    response = client.post(
        "/api/outside-filings/fbar/confirm",
        json={"decision": "filed", "note": "x"},
        headers=_headers(CLIENT),
    )
    assert response.status_code == 403
