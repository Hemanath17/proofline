"""A small, hand-made Packet builder shared by provenance and check tests.

Every check test needs a "nothing is wrong" packet that still satisfies the
required shape. Building that by hand in every test file would mean a lot of
repeated boilerplate, so it lives here once.
"""

from __future__ import annotations

from typing import Any

from proofline.packet import (
    CaliforniaSummary,
    Document,
    Extraction,
    FederalSummary,
    Household,
    Packet,
    PacketMeta,
    Page,
    Person,
    ReturnVersion,
    Summary,
)


def minimal_household(**overrides: Any) -> Household:
    defaults: dict[str, Any] = {
        "filing_status": "married_filing_jointly",
        "tax_year": 2025,
        "people": [
            Person(
                id="taxpayer", role="taxpayer", name="Test Taxpayer", ssn="000-00-0001"
            ),
        ],
    }
    defaults.update(overrides)
    return Household(**defaults)


def minimal_document(document_id: str = "D01", **overrides: Any) -> Document:
    defaults: dict[str, Any] = {
        "id": document_id,
        "title": "Test document",
        "document_type": "W-2",
        "issuer": "Test Employer",
        "page_count": 1,
        "pages": [Page(page=1, printed_content="")],
        "extraction": Extraction(status="extracted", values=0, reason=None),
    }
    defaults.update(overrides)
    return Document(**defaults)


def minimal_return_version(version: str = "v3", **overrides: Any) -> ReturnVersion:
    defaults: dict[str, Any] = {
        "version": version,
        "computed_at": "2026-01-01T00:00:00Z",
        "summary": Summary(federal=FederalSummary(), california=CaliforniaSummary()),
        "lines": [],
    }
    defaults.update(overrides)
    return ReturnVersion(**defaults)


def minimal_packet(**overrides: Any) -> Packet:
    defaults: dict[str, Any] = {
        "packet": PacketMeta(
            name="test-packet",
            version="1.0",
            generated="2026-01-01T00:00:00Z",
            client_id="test",
        ),
        "household": minimal_household(),
        "documents": [],
        "extracted_values": [],
        "return_versions": [minimal_return_version()],
    }
    defaults.update(overrides)
    return Packet(**defaults)
