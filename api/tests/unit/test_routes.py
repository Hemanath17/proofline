from fastapi.testclient import TestClient
from proofline.db.models import Event
from sqlalchemy import select
from sqlalchemy.orm import Session

PRIYA = "st-01"  # preparer
DANIEL = "st-02"  # reviewer
HELEN = "st-03"  # partner
MARCUS = "st-04"  # preparer, no clearance
CLIENT = "cu-01"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_missing_actor_header_returns_401(client: TestClient) -> None:
    response = client.get("/api/household")
    assert response.status_code == 401


def test_unknown_actor_returns_401(client: TestClient) -> None:
    response = client.get("/api/household", headers=_headers("no-such-actor"))
    assert response.status_code == 401


def test_household_masks_ssn_for_marcus_but_not_for_daniel(client: TestClient) -> None:
    masked = client.get("/api/household", headers=_headers(MARCUS)).json()
    unmasked = client.get("/api/household", headers=_headers(DANIEL)).json()

    assert masked["people"][0]["ssn"] != unmasked["people"][0]["ssn"]
    assert masked["people"][0]["ssn"].endswith(unmasked["people"][0]["ssn"][-4:])
    assert "*" in masked["people"][0]["ssn"]
    assert "*" not in unmasked["people"][0]["ssn"]


def test_add_review_note_as_preparer_returns_403_naming_the_rule(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D30", "body": "check this"},
        headers=_headers(PRIYA),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "only a reviewer, partner or quality reviewer may raise a review note"
    )


def test_add_review_note_as_reviewer_succeeds(client: TestClient) -> None:
    response = client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D30", "body": "check this"},
        headers=_headers(DANIEL),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "open"
    assert body["opened_by"] == DANIEL
    assert body["revision"] == 1


def test_respond_as_uncleared_preparer_still_allowed(client: TestClient) -> None:
    note = client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D30", "body": "check this"},
        headers=_headers(DANIEL),
    ).json()

    response = client.post(
        f"/api/review-notes/{note['id']}/respond",
        json={"expected_revision": 1, "body": "looking into it"},
        headers=_headers(MARCUS),
    )
    assert response.status_code == 200
    assert response.json()["revision"] == 2


def test_resolve_by_a_different_staff_member_returns_403(client: TestClient) -> None:
    note = client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D30", "body": "check this"},
        headers=_headers(DANIEL),
    ).json()

    response = client.post(
        f"/api/review-notes/{note['id']}/resolve",
        json={"expected_revision": 1, "resolution": "fixed"},
        headers=_headers(PRIYA),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "only the reviewer who raised a note, or the partner, may clear it"
    )


def test_resolve_by_partner_succeeds_even_though_not_author(
    client: TestClient,
) -> None:
    note = client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D30", "body": "check this"},
        headers=_headers(DANIEL),
    ).json()

    response = client.post(
        f"/api/review-notes/{note['id']}/resolve",
        json={"expected_revision": 1, "resolution": "fixed"},
        headers=_headers(HELEN),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


def test_stale_revision_returns_409_with_current_state(client: TestClient) -> None:
    note = client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D30", "body": "check this"},
        headers=_headers(DANIEL),
    ).json()
    client.post(
        f"/api/review-notes/{note['id']}/respond",
        json={"expected_revision": 1, "body": "first response"},
        headers=_headers(PRIYA),
    )

    response = client.post(
        f"/api/review-notes/{note['id']}/respond",
        json={"expected_revision": 1, "body": "too late"},
        headers=_headers(MARCUS),
    )

    assert response.status_code == 409
    body = response.json()
    assert body["current_state"]["revision"] == 2


def test_responding_to_a_resolved_note_returns_409_with_current_state(
    client: TestClient,
) -> None:
    note = client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D30", "body": "check this"},
        headers=_headers(DANIEL),
    ).json()
    client.post(
        f"/api/review-notes/{note['id']}/resolve",
        json={"expected_revision": 1, "resolution": "fixed"},
        headers=_headers(DANIEL),
    )

    response = client.post(
        f"/api/review-notes/{note['id']}/respond",
        json={"expected_revision": 2, "body": "too late"},
        headers=_headers(PRIYA),
    )

    assert response.status_code == 409
    body = response.json()
    assert body["detail"] == "cannot respond to a resolved note"
    assert body["current_state"]["status"] == "resolved"


def test_reveal_requires_clearance(client: TestClient) -> None:
    response = client.post(
        "/api/reveal",
        json={
            "entity_id": "household:theo",
            "field": "ssn",
            "reason": "client asked to confirm it",
        },
        headers=_headers(CLIENT),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "no clearance"


def test_reveal_with_clearance_succeeds_and_writes_an_event(
    client: TestClient, db_session: Session
) -> None:
    response = client.post(
        "/api/reveal",
        json={
            "entity_id": "household:theo",
            "field": "ssn",
            "reason": "client asked to confirm it",
        },
        headers=_headers(DANIEL),
    )
    assert response.status_code == 200

    events = db_session.scalars(select(Event)).all()
    reveal_events = [e for e in events if e.event_type == "sensitive_value_revealed"]
    assert len(reveal_events) == 1
    assert reveal_events[0].payload["reason"] == "client asked to confirm it"


def test_reveal_without_a_reason_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/reveal",
        json={"entity_id": "household:theo", "field": "ssn"},
        headers=_headers(DANIEL),
    )
    assert response.status_code == 422


def test_document_page_cleared_actor_sees_unmasked_text_and_logs_reveal(
    client: TestClient, db_session: Session
) -> None:
    response = client.get("/api/documents/D03/pages/1", headers=_headers(DANIEL))
    assert response.status_code == 200
    assert "482915" in response.json()["printed_content"]

    events = db_session.scalars(select(Event)).all()
    reveal_events = [e for e in events if e.event_type == "sensitive_value_revealed"]
    assert len(reveal_events) == 1
    assert reveal_events[0].entity_id == "doc:D03#page1"


def test_document_page_uncleared_actor_sees_masked_text_and_logs_nothing(
    client: TestClient, db_session: Session
) -> None:
    response = client.get("/api/documents/D03/pages/1", headers=_headers(MARCUS))
    assert response.status_code == 200
    assert "482915" not in response.json()["printed_content"]

    events = db_session.scalars(select(Event)).all()
    assert not any(event.event_type == "sensitive_value_revealed" for event in events)


def test_record_check_run_as_client_returns_403(client: TestClient) -> None:
    response = client.post("/api/check-runs", headers=_headers(CLIENT))
    assert response.status_code == 403


def test_record_check_run_as_staff_succeeds(client: TestClient) -> None:
    response = client.post("/api/check-runs", headers=_headers(DANIEL))
    assert response.status_code == 200
    body = response.json()
    assert "findings" in body
    assert "id" in body


def test_document_page_unknown_document_returns_404(client: TestClient) -> None:
    response = client.get("/api/documents/D999/pages/1", headers=_headers(DANIEL))
    assert response.status_code == 404
    assert response.json()["detail"] == "document not found"


def test_document_page_unknown_page_number_returns_404(client: TestClient) -> None:
    response = client.get("/api/documents/D03/pages/999", headers=_headers(DANIEL))
    assert response.status_code == 404
    assert response.json()["detail"] == "page not found"


def test_trace_line_with_a_dangling_ref_returns_422(client: TestClient) -> None:
    """Every real packet reference already resolves (Step 2's own "done
    when"), so this path -- trace_line's UnresolvedReferenceError mapped to
    422 -- can only be exercised with a hand-built dangling ref. `routes/
    trace.py` calls the same `@lru_cache`'d `load_packet()` singleton this
    test process already has loaded, so mutating its return version's
    `lines` in place (and removing it again) is enough -- there's no
    FastAPI dependency to override here."""
    from proofline.packet import Line, load_packet

    packet = load_packet()
    rv = packet.return_versions[-1]
    bad_line = Line(
        key="TEST.DANGLING",
        jurisdiction="federal",
        form="TEST",
        line="1",
        label="test",
        value=0,
        rule="R-SUM",
        sources=["ev-99999999"],
    )
    rv.lines.append(bad_line)
    rv._lines_by_key[bad_line.key] = bad_line  # rv.line() reads this, not rv.lines
    try:
        response = client.get("/api/trace/line/TEST.DANGLING", headers=_headers(DANIEL))
        assert response.status_code == 422
    finally:
        rv.lines.remove(bad_line)
        del rv._lines_by_key[bad_line.key]


def test_trace_line_unknown_key_returns_404(client: TestClient) -> None:
    response = client.get("/api/trace/line/NOT.A.REAL.LINE", headers=_headers(DANIEL))
    assert response.status_code == 404
    assert response.json()["detail"] == "line not found"


def test_trace_document_unknown_id_returns_404(client: TestClient) -> None:
    response = client.get("/api/trace/document/D999", headers=_headers(DANIEL))
    assert response.status_code == 404
    assert response.json()["detail"] == "document not found"


def test_respond_to_unknown_note_returns_404_over_http(client: TestClient) -> None:
    """Exercises the app-level EntityNotFound -> 404 exception handler
    through a real route, not just the service layer directly."""
    response = client.post(
        "/api/review-notes/note-does-not-exist/respond",
        json={"expected_revision": 1, "body": "x"},
        headers=_headers(PRIYA),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "not found"


def test_add_review_note_with_empty_body_returns_422_over_http(
    client: TestClient,
) -> None:
    """Exercises the app-level ActionValidationError -> 422 exception
    handler through a real route: the request model's own `str` type
    accepts an empty string, so this only fails inside the action."""
    response = client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D30", "body": ""},
        headers=_headers(DANIEL),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "body is required"


def test_review_notes_list_filters_by_about(client: TestClient) -> None:
    client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D30", "body": "about D30"},
        headers=_headers(DANIEL),
    )
    client.post(
        "/api/review-notes",
        json={"about_type": "document", "about_id": "D31", "body": "about D31"},
        headers=_headers(DANIEL),
    )

    response = client.get(
        "/api/review-notes",
        params={"about_type": "document", "about_id": "D30"},
        headers=_headers(DANIEL),
    )

    notes = response.json()["review_notes"]
    assert len(notes) == 1
    assert notes[0]["about_id"] == "D30"
