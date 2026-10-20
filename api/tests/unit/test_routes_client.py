"""The client workspace (S5) -- `GET /api/client/*`."""

from fastapi.testclient import TestClient

NGOZI = "cu-01"
PRIYA = "st-01"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_client_summary_is_labelled_with_a_version(client: TestClient) -> None:
    response = client.get("/api/client/summary", headers=_headers(NGOZI))
    assert response.status_code == 200
    body = response.json()
    assert body["federal"]["label"].startswith("Engine")
    assert body["california"]["label"].startswith("Engine")
    assert "balance_due" in body["federal"]


def test_client_questions_shows_an_answered_thread(client: TestClient) -> None:
    synced = client.post("/api/cases/sync", headers=_headers(PRIYA))
    cases = synced.json()["cases"]
    case_id = next(
        c["case_id"] for c in cases if c["status"] in ("open", "investigating")
    )

    picked_up = client.post(
        f"/api/cases/{case_id}/pick-up",
        json={"expected_revision": 1},
        headers=_headers(PRIYA),
    )
    assert picked_up.status_code == 200
    asked = client.post(
        f"/api/cases/{case_id}/ask-client",
        json={
            "expected_revision": picked_up.json()["revision"],
            "question": "Can you confirm this amount?",
        },
        headers=_headers(PRIYA),
    )
    assert asked.status_code == 200
    answered = client.post(
        f"/api/cases/{case_id}/client-answered",
        json={"expected_revision": asked.json()["revision"], "evidence_ref": "msg-01"},
        headers=_headers(NGOZI),
    )
    assert answered.status_code == 200

    threads = client.get("/api/client/questions", headers=_headers(NGOZI)).json()[
        "threads"
    ]
    thread = next(t for t in threads if t["case_id"] == case_id)
    assert thread["question"] == "Can you confirm this amount?"
    assert thread["answer"] is not None


def test_client_documents_only_shows_client_uploaded_ones(client: TestClient) -> None:
    from proofline.packet import load_packet

    packet = load_packet()
    response = client.get("/api/client/documents", headers=_headers(NGOZI))
    assert response.status_code == 200
    documents = response.json()["documents"]
    uploaded_ids = {d["id"] for d in documents if d["kind"] == "uploaded"}
    expected_ids = {d.id for d in packet.documents if d.uploaded_by == "client"}
    assert uploaded_ids == expected_ids


def test_client_package_shows_fingerprints_before_signing(client: TestClient) -> None:
    response = client.get("/api/client/package", headers=_headers(NGOZI))
    assert response.status_code == 200
    body = response.json()
    assert body["reference"]
    assert body["amounts_fingerprint"]
    assert body["identity_fingerprint"]


def test_client_can_sign_via_the_existing_authorize_filing_action(
    client: TestClient,
) -> None:
    """W4: "the signature is tied to that exact package" -- the client
    workspace's sign step IS `authorize_filing`, not a second mechanism."""
    package = client.get("/api/client/package", headers=_headers(NGOZI)).json()
    response = client.post(
        "/api/filing/authorize",
        json={"pins": {"taxpayer": "41207", "spouse": "88310"}},
        headers=_headers(NGOZI),
    )
    assert response.status_code == 200
    assert response.json()["package_reference"] == package["reference"]
