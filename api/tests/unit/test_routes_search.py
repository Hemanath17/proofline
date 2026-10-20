"""`GET /api/search` (B38). A document snippet is always redacted, even
for a cleared actor -- a search result is a quick preview, not "opening
the document" (docs/DECISIONS.md)."""

from fastapi.testclient import TestClient
from proofline.packet import load_packet
from proofline.security.redact import collect_sensitive_values, generate_variants

DANIEL = "st-02"  # reviewer, cleared
CLIENT = "cu-01"


def _headers(actor_id: str) -> dict[str, str]:
    return {"X-Proofline-Actor": actor_id}


def test_search_finds_a_line_by_key(client: TestClient) -> None:
    response = client.get("/api/search?q=F1040.1a", headers=_headers(DANIEL))
    assert response.status_code == 200
    results = response.json()["results"]
    assert any(r["type"] == "line" and r["id"] == "F1040.1a" for r in results)


def test_search_finds_a_document_by_title(client: TestClient) -> None:
    packet = load_packet()
    title_word = packet.documents[0].title.split()[0]
    response = client.get(f"/api/search?q={title_word}", headers=_headers(DANIEL))
    assert response.status_code == 200
    results = response.json()["results"]
    assert any(r["type"] == "document" for r in results)


def test_search_empty_query_returns_no_results(client: TestClient) -> None:
    response = client.get("/api/search?q=", headers=_headers(DANIEL))
    assert response.json()["results"] == []


def test_search_never_leaks_a_sensitive_value_even_to_a_cleared_actor(
    client: TestClient,
) -> None:
    packet = load_packet()
    ssn = packet.household.people[0].ssn
    response = client.get(f"/api/search?q={ssn}", headers=_headers(DANIEL))
    assert response.status_code == 200
    variants = set()
    for value in collect_sensitive_values(packet):
        variants |= generate_variants(value.value)
    for variant in variants:
        assert variant not in response.text


def test_search_blocked_for_client(client: TestClient) -> None:
    response = client.get("/api/search?q=x", headers=_headers(CLIENT))
    assert response.status_code == 403
