"""`GET /api/time`, `POST /api/time`."""

from fastapi.testclient import TestClient

PRIYA = "st-01"
CLIENT = "cu-01"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_log_time_then_report(client: TestClient) -> None:
    response = client.post(
        "/api/time",
        json={
            "area": "wages",
            "hours": "1.0",
            "date": "2026-10-19",
            "note": "W-2 review",
        },
        headers=_headers(PRIYA),
    )
    assert response.status_code == 200

    report = client.get("/api/time", headers=_headers(PRIYA)).json()
    wages_row = next(row for row in report["budget"] if row["area"] == "wages")
    assert wages_row["logged_hours"] == "1.0"
    assert len(report["entries"]) == 1
    assert report["entries"][0]["area"] == "wages"


def test_log_time_as_client_returns_403(client: TestClient) -> None:
    response = client.post(
        "/api/time",
        json={"area": "wages", "hours": "1.0", "date": "2026-10-19"},
        headers=_headers(CLIENT),
    )
    assert response.status_code == 403


def test_time_report_blocked_for_client(client: TestClient) -> None:
    response = client.get("/api/time", headers=_headers(CLIENT))
    assert response.status_code == 403
