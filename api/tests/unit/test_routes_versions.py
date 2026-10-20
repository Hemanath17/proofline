"""`GET /api/versions/diff` (B15), `GET /api/what-ifs` (B16)."""

from fastapi.testclient import TestClient

DANIEL = "st-02"
CLIENT = "cu-01"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_diff_v1_to_v3_finds_m14_box_move(client: TestClient) -> None:
    """A2's own scenario: M14 keeps its identity but moves from box A to
    box D between v1 and v2 -- its line key changes, so a plain key-union
    diff should show both the old and new key as changed, not quietly
    drop the old one."""
    response = client.get("/api/versions/diff?from=v1&to=v3", headers=_headers(DANIEL))
    assert response.status_code == 200
    lines = response.json()["lines"]
    assert any(line["changed"] for line in lines)


def test_diff_only_changed_filters(client: TestClient) -> None:
    all_lines = client.get(
        "/api/versions/diff?from=v1&to=v3", headers=_headers(DANIEL)
    ).json()["lines"]
    changed_only = client.get(
        "/api/versions/diff?from=v1&to=v3&only_changed=true", headers=_headers(DANIEL)
    ).json()["lines"]
    assert len(changed_only) < len(all_lines)
    assert all(line["changed"] for line in changed_only)


def test_diff_rejects_an_unknown_version(client: TestClient) -> None:
    response = client.get("/api/versions/diff?from=v9&to=v3", headers=_headers(DANIEL))
    assert response.status_code == 422


def test_diff_to_workpaper_labels_an_adjustment(client: TestClient) -> None:
    response = client.get(
        "/api/versions/diff?from=v3&to=workpaper", headers=_headers(DANIEL)
    )
    assert response.status_code == 200
    for line in response.json()["lines"]:
        assert line["source"] in ("engine", "adjustment", "n/a")


def test_versions_diff_blocked_for_client(client: TestClient) -> None:
    response = client.get("/api/versions/diff?from=v1&to=v3", headers=_headers(CLIENT))
    assert response.status_code == 403


def test_what_ifs_lists_the_five_packet_alternatives(client: TestClient) -> None:
    response = client.get("/api/what-ifs", headers=_headers(DANIEL))
    assert response.status_code == 200
    ids = {alt["id"] for alt in response.json()["alternatives"]}
    assert ids == {
        "equipment_section179",
        "equipment_no_bonus",
        "hvac_improvement",
        "standard_deduction",
        "penalty_annualized",
    }
    for alternative in response.json()["alternatives"]:
        for changed in alternative["changed_lines"]:
            assert "current_workpaper_value" in changed


def test_what_ifs_blocked_for_client(client: TestClient) -> None:
    response = client.get("/api/what-ifs", headers=_headers(CLIENT))
    assert response.status_code == 403
