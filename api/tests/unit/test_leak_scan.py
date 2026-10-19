"""I4: Marcus never sees an SSN, account number or PIN in any API response
or rendered page. Extended, per the /simulate skill's leak-scan scenario,
to the client and the AI assistant too -- none of the three ever gets
clearance.
"""

from fastapi.testclient import TestClient
from proofline.packet import load_packet
from proofline.security.redact import collect_sensitive_values, generate_variants

UNCLEARED_ACTOR_IDS = [
    "st-04",
    "cu-01",
    "ai-assistant",
]  # Marcus, a client, the AI assistant


def _all_variants() -> set[str]:
    packet = load_packet()
    variants: set[str] = set()
    for value in collect_sensitive_values(packet):
        variants |= generate_variants(value.value)
    return {variant for variant in variants if variant}


def _assert_no_leak(text: str, variants: set[str], where: str) -> None:
    for variant in variants:
        assert variant not in text, f"leaked {variant!r} in {where}"


def test_household_endpoint_never_leaks(client: TestClient) -> None:
    variants = _all_variants()
    for actor_id in UNCLEARED_ACTOR_IDS:
        response = client.get("/api/household", headers={"X-Proofline-Actor": actor_id})
        assert response.status_code == 200
        _assert_no_leak(response.text, variants, f"GET /api/household as {actor_id}")


def test_documents_list_never_leaks(client: TestClient) -> None:
    variants = _all_variants()
    for actor_id in UNCLEARED_ACTOR_IDS:
        response = client.get("/api/documents", headers={"X-Proofline-Actor": actor_id})
        assert response.status_code == 200
        _assert_no_leak(response.text, variants, f"GET /api/documents as {actor_id}")


def test_every_document_page_never_leaks(client: TestClient) -> None:
    packet = load_packet()
    variants = _all_variants()
    for actor_id in UNCLEARED_ACTOR_IDS:
        for document in packet.documents:
            for page in document.pages:
                where = (
                    f"GET /api/documents/{document.id}/pages/{page.page} as {actor_id}"
                )
                response = client.get(
                    f"/api/documents/{document.id}/pages/{page.page}",
                    headers={"X-Proofline-Actor": actor_id},
                )
                assert response.status_code == 200, where
                _assert_no_leak(response.text, variants, where)


def test_checks_endpoint_never_leaks(client: TestClient) -> None:
    variants = _all_variants()
    for actor_id in UNCLEARED_ACTOR_IDS:
        response = client.get("/api/checks", headers={"X-Proofline-Actor": actor_id})
        assert response.status_code == 200
        _assert_no_leak(response.text, variants, f"GET /api/checks as {actor_id}")


def test_review_notes_endpoint_never_leaks(client: TestClient) -> None:
    variants = _all_variants()
    for actor_id in UNCLEARED_ACTOR_IDS:
        response = client.get(
            "/api/review-notes", headers={"X-Proofline-Actor": actor_id}
        )
        assert response.status_code == 200
        _assert_no_leak(response.text, variants, f"GET /api/review-notes as {actor_id}")


def test_document_detail_never_leaks(client: TestClient) -> None:
    packet = load_packet()
    variants = _all_variants()
    for actor_id in UNCLEARED_ACTOR_IDS:
        for document in packet.documents:
            where = f"GET /api/documents/{document.id} as {actor_id}"
            response = client.get(
                f"/api/documents/{document.id}",
                headers={"X-Proofline-Actor": actor_id},
            )
            assert response.status_code == 200, where
            _assert_no_leak(response.text, variants, where)


def test_trace_document_never_leaks(client: TestClient) -> None:
    packet = load_packet()
    variants = _all_variants()
    for actor_id in UNCLEARED_ACTOR_IDS:
        for document in packet.documents:
            where = f"GET /api/trace/document/{document.id} as {actor_id}"
            response = client.get(
                f"/api/trace/document/{document.id}",
                headers={"X-Proofline-Actor": actor_id},
            )
            assert response.status_code == 200, where
            _assert_no_leak(response.text, variants, where)


def test_trace_line_never_leaks(client: TestClient) -> None:
    packet = load_packet()
    variants = _all_variants()
    line_keys = [line.key for line in packet.return_versions[-1].lines]
    for actor_id in UNCLEARED_ACTOR_IDS:
        for line_key in line_keys:
            where = f"GET /api/trace/line/{line_key} as {actor_id}"
            response = client.get(
                f"/api/trace/line/{line_key}", headers={"X-Proofline-Actor": actor_id}
            )
            assert response.status_code in (200, 422), where
            _assert_no_leak(response.text, variants, where)


def test_actors_endpoint_never_leaks(client: TestClient) -> None:
    variants = _all_variants()
    for actor_id in UNCLEARED_ACTOR_IDS:
        response = client.get("/api/actors", headers={"X-Proofline-Actor": actor_id})
        assert response.status_code == 200
        _assert_no_leak(response.text, variants, f"GET /api/actors as {actor_id}")


def test_cases_queue_and_detail_never_leak(client: TestClient) -> None:
    variants = _all_variants()
    synced = client.post("/api/cases/sync", headers={"X-Proofline-Actor": "st-02"})
    assert synced.status_code == 200
    case_ids = [case["case_id"] for case in synced.json()["cases"]]

    for actor_id in UNCLEARED_ACTOR_IDS:
        for tab in ("needs_me", "all_open", "waiting_on_client", "resolved"):
            where = f"GET /api/cases?tab={tab} as {actor_id}"
            response = client.get(
                f"/api/cases?tab={tab}", headers={"X-Proofline-Actor": actor_id}
            )
            assert response.status_code == 200, where
            _assert_no_leak(response.text, variants, where)
        for case_id in case_ids:
            where = f"GET /api/cases/{case_id} as {actor_id}"
            response = client.get(
                f"/api/cases/{case_id}", headers={"X-Proofline-Actor": actor_id}
            )
            assert response.status_code == 200, where
            _assert_no_leak(response.text, variants, where)

            activity_where = f"GET /api/cases/{case_id}/activity as {actor_id}"
            activity_response = client.get(
                f"/api/cases/{case_id}/activity",
                headers={"X-Proofline-Actor": actor_id},
            )
            assert activity_response.status_code == 200, activity_where
            _assert_no_leak(activity_response.text, variants, activity_where)


def test_areas_endpoint_never_leaks(client: TestClient) -> None:
    variants = _all_variants()
    scopes = [
        "identity",
        "wages",
        "investments",
        "business",
        "rentals",
        "pass_throughs",
        "deductions_credits",
        "california",
        "tax_computation",
    ]
    for actor_id in UNCLEARED_ACTOR_IDS:
        for scope in scopes:
            where = f"GET /api/areas/{scope} as {actor_id}"
            response = client.get(
                f"/api/areas/{scope}", headers={"X-Proofline-Actor": actor_id}
            )
            assert response.status_code == 200, where
            _assert_no_leak(response.text, variants, where)


def test_reveal_sensitive_value_refused_for_uncleared_actors(
    client: TestClient,
) -> None:
    for actor_id in UNCLEARED_ACTOR_IDS:
        response = client.post(
            "/api/reveal",
            json={
                "entity_id": "household:theo",
                "field": "ssn",
                "reason": "testing",
            },
            headers={"X-Proofline-Actor": actor_id},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "no clearance"
