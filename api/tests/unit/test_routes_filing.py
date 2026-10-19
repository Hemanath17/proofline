"""`/api/filing/*` -- package, authorization, submission and the Letter
566 pack (CONTRACTS.md C5, acceptance test A3)."""

from fastapi.testclient import TestClient

DANIEL = "st-02"  # reviewer
CLIENT_USER = "cu-01"
AI_ASSISTANT = "ai-assistant"

_PINS = {"taxpayer": "41207", "spouse": "88310"}


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_get_package_shape(client: TestClient) -> None:
    response = client.get("/api/filing/package", headers=_headers(DANIEL))
    assert response.status_code == 200
    body = response.json()
    assert body["engine_version"] == "v3"
    assert body["reference"]
    assert body["amounts_fingerprint"]
    assert body["identity_fingerprint"]
    assert isinstance(body["lines"], list) and body["lines"]
    assert isinstance(body["documents"], list) and body["documents"]


def test_authorize_filing_as_client(client: TestClient) -> None:
    response = client.post(
        "/api/filing/authorize",
        json={"pins": _PINS},
        headers=_headers(CLIENT_USER),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["simulated"] is True
    assert body["package_reference"]


def test_authorize_filing_as_ai_assistant_returns_403(client: TestClient) -> None:
    response = client.post(
        "/api/filing/authorize",
        json={"pins": _PINS},
        headers=_headers(AI_ASSISTANT),
    )
    assert response.status_code == 403


def test_submit_filing_unknown_jurisdiction_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/filing/texas/submit",
        json={"package_reference": "x", "status": "accepted"},
        headers=_headers(DANIEL),
    )
    assert response.status_code == 404


def test_submit_filing_without_authorization_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/filing/federal/submit",
        json={"package_reference": "sha-does-not-exist", "status": "accepted"},
        headers=_headers(DANIEL),
    )
    assert response.status_code == 422


def test_full_authorize_then_submit_rejected_then_accepted(client: TestClient) -> None:
    authorized = client.post(
        "/api/filing/authorize",
        json={"pins": _PINS},
        headers=_headers(CLIENT_USER),
    )
    package_reference = authorized.json()["package_reference"]

    rejected = client.post(
        "/api/filing/federal/submit",
        json={
            "package_reference": package_reference,
            "status": "rejected",
            "codes": [{"code": "R0000-504-02", "message": "mismatch"}],
        },
        headers=_headers(DANIEL),
    )
    assert rejected.status_code == 200
    assert rejected.json()["filed_record_id"] is None

    accepted = client.post(
        "/api/filing/federal/submit",
        json={"package_reference": package_reference, "status": "accepted"},
        headers=_headers(DANIEL),
    )
    assert accepted.status_code == 200
    assert accepted.json()["filed_record_id"] is not None

    status = client.get("/api/filing", headers=_headers(DANIEL)).json()
    assert len(status["submissions"]["federal"]) == 2
    assert status["submissions"]["federal"][0]["status"] == "rejected"
    assert status["submissions"]["federal"][1]["status"] == "accepted"
    assert len(status["filed_records"]) == 1


def test_get_letter_566_pack(client: TestClient) -> None:
    response = client.get("/api/filing/letter-566", headers=_headers(DANIEL))
    assert response.status_code == 200
    body = response.json()
    assert body["notice"]["id"] == "N-2025-L566"
    assert body["items"]
