"""The area page (S3) over HTTP -- GET /api/areas/{scope} and the C2/C4/
bulk-verify POSTs, docs/CONTRACTS.md C2/C4, docs/UX.md S3.
"""

from fastapi.testclient import TestClient

PRIYA = "st-01"  # preparer
DANIEL = "st-02"  # reviewer
HELEN = "st-03"  # partner


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_get_unknown_area_returns_404(client: TestClient) -> None:
    response = client.get("/api/areas/not_a_real_scope", headers=_headers(DANIEL))
    assert response.status_code == 404


def test_get_area_returns_blocks_tie_outs_and_detail(client: TestClient) -> None:
    response = client.get("/api/areas/business", headers=_headers(DANIEL))
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "business"
    assert body["sign_off"] is None
    assert body["changes_since_sign_off"] is None
    assert isinstance(body["blocking_reasons"], list)
    assert isinstance(body["tie_outs"], list)
    assert isinstance(body["detail"], list)


def test_sign_off_as_preparer_returns_403(client: TestClient) -> None:
    response = client.post(
        "/api/areas/business/sign-off", json={}, headers=_headers(PRIYA)
    )
    assert response.status_code == 403


def test_sign_off_tax_computation_as_reviewer_returns_403(client: TestClient) -> None:
    response = client.post(
        "/api/areas/tax_computation/sign-off", json={}, headers=_headers(DANIEL)
    )
    assert response.status_code == 403


def test_sign_off_business_then_area_shows_it(client: TestClient) -> None:
    sign_off_response = client.post(
        "/api/areas/business/sign-off", json={"version": "v1"}, headers=_headers(DANIEL)
    )
    assert sign_off_response.status_code == 200
    assert sign_off_response.json()["version"] == 1

    area = client.get("/api/areas/business", headers=_headers(DANIEL)).json()
    assert area["sign_off"]["version"] == 1
    assert area["sign_off"]["signed_by"] == DANIEL


def test_investments_sign_off_v1_then_v2_needs_carryover_first(
    client: TestClient,
) -> None:
    client.post(
        "/api/areas/investments/sign-off",
        json={"version": "v1"},
        headers=_headers(DANIEL),
    )
    blocked = client.post(
        "/api/areas/investments/sign-off",
        json={"version": "v2"},
        headers=_headers(DANIEL),
    )
    assert blocked.status_code == 409
    assert "carry-over" in blocked.json()["detail"]

    confirmed = client.post(
        "/api/areas/investments/confirm-carryover",
        json={"old_document_id": "D30", "new_document_id": "D31"},
        headers=_headers(DANIEL),
    )
    assert confirmed.status_code == 200

    signed_v2 = client.post(
        "/api/areas/investments/sign-off",
        json={"version": "v2"},
        headers=_headers(DANIEL),
    )
    assert signed_v2.status_code == 200
    assert signed_v2.json()["version"] == 2


def test_confirm_disposition_as_reviewer_returns_403(client: TestClient) -> None:
    response = client.post(
        "/api/documents/D10/confirm-disposition",
        json={"expected_revision": 1, "disposition": "duplicate_of", "reason": "x"},
        headers=_headers(DANIEL),
    )
    assert response.status_code == 403


def test_confirm_disposition_as_preparer_then_document_detail_shows_it(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/documents/D10/confirm-disposition",
        json={
            "expected_revision": 1,
            "disposition": "duplicate_of",
            "reason": "same as D09",
        },
        headers=_headers(PRIYA),
    )
    assert response.status_code == 200
    assert response.json()["disposition"] == "duplicate_of"

    detail = client.get("/api/documents/D10", headers=_headers(DANIEL)).json()
    assert detail["disposition"] == "duplicate_of"
    assert detail["disposition_reason"] == "same as D09"


def test_bulk_verify_then_undo_over_http(client: TestClient) -> None:
    claim_keys = ["1099b_lot:Northlake Securities:N1"]
    verified = client.post(
        "/api/areas/investments/bulk-verify",
        json={"claim_keys": claim_keys},
        headers=_headers(PRIYA),
    )
    assert verified.status_code == 200
    event_id = verified.json()["event_id"]

    area = client.get("/api/areas/investments", headers=_headers(PRIYA)).json()
    row = next(r for r in area["detail"] if r["claim_key"] == claim_keys[0])
    assert row["verified"] is True

    undone = client.post(
        "/api/areas/investments/undo-bulk-verify",
        json={"event_id": event_id},
        headers=_headers(PRIYA),
    )
    assert undone.status_code == 200

    area_after = client.get("/api/areas/investments", headers=_headers(PRIYA)).json()
    row_after = next(r for r in area_after["detail"] if r["claim_key"] == claim_keys[0])
    assert row_after["verified"] is False


def test_bulk_verify_with_a_bad_claim_applies_nothing(client: TestClient) -> None:
    response = client.post(
        "/api/areas/investments/bulk-verify",
        json={"claim_keys": ["1099b_lot:Northlake Securities:N1", "not-a-real-claim"]},
        headers=_headers(PRIYA),
    )
    assert response.status_code == 422
    assert "not-a-real-claim" in response.json()["detail"]
