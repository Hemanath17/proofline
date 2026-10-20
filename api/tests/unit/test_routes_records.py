"""The sixteen CPA record views (R01-R16, docs/PLAN.md Step 9) -- one
smoke test per endpoint against the real packet, plus the permission
guard and a couple of substantive assertions on the more interesting
views (R01's variance rule, R05's recapture, R09's provenance mapping)."""

import pytest
from fastapi.testclient import TestClient

DANIEL = "st-02"
CLIENT = "cu-01"

_ROUTES = [
    "/api/records/return-summary",
    "/api/records/tax-computation",
    "/api/records/area-summaries",
    "/api/records/documents",
    "/api/records/depreciation",
    "/api/records/sales-detail",
    "/api/records/books-to-tax",
    "/api/records/rentals-passive",
    "/api/records/k1-lines",
    "/api/records/retirement-foreign",
    "/api/records/deductions-credits",
    "/api/records/payments",
    "/api/records/state-split",
    "/api/records/carryovers",
    "/api/records/basis",
    "/api/records/prior-preparer",
]


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


@pytest.mark.parametrize("path", _ROUTES)
def test_every_record_view_returns_200(client: TestClient, path: str) -> None:
    response = client.get(path, headers=_headers(DANIEL))
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("path", _ROUTES)
def test_every_record_view_blocked_for_client(client: TestClient, path: str) -> None:
    response = client.get(path, headers=_headers(CLIENT))
    assert response.status_code == 403


def test_r01_return_summary_uses_the_firms_own_variance_thresholds(
    client: TestClient,
) -> None:
    from decimal import Decimal

    from proofline.packet import load_packet

    rows = client.get("/api/records/return-summary", headers=_headers(DANIEL)).json()[
        "rows"
    ]
    assert rows
    variance = load_packet().firm.starter_standards.variance_review
    for row in rows:
        if row["flagged"]:
            assert abs(Decimal(row["difference"])) > variance.and_over_amount


def test_r05_depreciation_surfaces_the_4797_recapture(client: TestClient) -> None:
    rows = client.get("/api/records/depreciation", headers=_headers(DANIEL)).json()[
        "rows"
    ]
    disposed = [row for row in rows if row["disposed"]]
    assert disposed, "the condo sale's assets should show as disposed"
    assert any(row["disposition"] is not None for row in disposed)


def test_r09_k1_lines_map_boxes_to_real_return_lines(client: TestClient) -> None:
    rows = client.get("/api/records/k1-lines", headers=_headers(DANIEL)).json()["rows"]
    assert rows
    assert any(row["feeds_lines"] for row in rows)


def test_r14_carryovers_has_both_directions(client: TestClient) -> None:
    body = client.get("/api/records/carryovers", headers=_headers(DANIEL)).json()
    assert body["in_from_2024"]
    assert body["out_to_2026"]


def test_r15_basis_shows_a_real_gap_as_a_gap(client: TestClient) -> None:
    body = client.get("/api/records/basis", headers=_headers(DANIEL)).json()
    scorp = body["scorp_stock_basis"]
    assert any(entry.get("ending_stock_basis") is None for entry in scorp)
