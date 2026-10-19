"""C5's package, its fingerprints, and the Letter 566 pack."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from proofline.analysis.calculation import adjustments_by_claim
from proofline.analysis.filing import (
    build_package,
    document_content_hash,
    identity_fingerprint,
    letter_566_pack,
    resolved_line_value,
)
from proofline.db.models import Adjustment, Base
from proofline.db.repository import insert_adjustment
from proofline.packet import load_packet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_document_content_hash_is_stable_regardless_of_page_order() -> None:
    packet = load_packet()
    document = packet.document("D71")
    first = document_content_hash(document)
    reversed_document = document.model_copy(
        update={"pages": list(reversed(document.pages))}
    )
    second = document_content_hash(reversed_document)
    assert first == second


def test_document_content_hash_changes_with_content() -> None:
    packet = load_packet()
    document = packet.document("D71")
    original = document_content_hash(document)
    changed_pages = [
        page.model_copy(update={"printed_content": page.printed_content + " "})
        for page in document.pages
    ]
    changed = document_content_hash(
        document.model_copy(update={"pages": changed_pages})
    )
    assert original != changed


def test_identity_fingerprint_changes_when_an_ssn_is_adjusted() -> None:
    packet = load_packet()
    before = identity_fingerprint(packet, {})
    theo = next(p for p in packet.household.people if p.id == "theo")
    adjustments = {
        f"household:{theo.id}:ssn": Adjustment(
            id="adj-1",
            claim_key=f"household:{theo.id}:ssn",
            old_value=theo.ssn,
            new_value="666-74-3390",
            evidence_refs=["D71"],
        )
    }
    after = identity_fingerprint(packet, adjustments)
    assert before != after


def test_identity_fingerprint_is_stable_for_the_same_facts() -> None:
    packet = load_packet()
    assert identity_fingerprint(packet, {}) == identity_fingerprint(packet, {})


def test_build_package_is_deterministic_for_the_same_state(session: Session) -> None:
    packet = load_packet()
    rv = packet.return_versions[-1]
    first = build_package(session, packet, rv)
    second = build_package(session, packet, rv)
    assert first.reference == second.reference
    assert first.amounts_fingerprint == second.amounts_fingerprint
    assert first.identity_fingerprint == second.identity_fingerprint
    assert len(first.lines) == len(rv.lines)
    assert len(first.documents) == len(rv.documents_used)


def test_build_package_reflects_a_return_total_adjustment_in_its_own_line(
    session: Session,
) -> None:
    """Regression test (reviewer-agent finding): `build_package`'s own
    `PackageLine` for SchC.1 used to call plain `workpaper_value`, which
    can't see a `return_total`-keyed adjustment (the E3 correction) --
    so the filed package and `letter_566_pack` would disagree about
    SchC.1's value once E3 is resolved. Both must agree."""
    packet = load_packet()
    rv = packet.return_versions[-1]
    engine_value = rv.line("SchC.1").value

    insert_adjustment(
        session,
        Adjustment(
            id="adj-1",
            claim_key="SchC.1",
            old_value=str(engine_value),
            new_value="151300.0",
            evidence_refs=["D14", "ev-0103"],
        ),
    )

    package = build_package(session, packet, rv)
    schc1_line = next(line for line in package.lines if line.line_key == "SchC.1")
    assert schc1_line.provenance_label == "adjusted"
    assert Decimal(str(schc1_line.value)) == Decimal("151300.0")


def test_resolved_line_value_honors_a_direct_adjustment_on_a_return_total(
    session: Session,
) -> None:
    """SchC.1 has no F8949-style claim identity -- `resolved_line_value`
    is what lets its own `return_total` adjustment (the E3 correction)
    show through where plain `workpaper_value` can't."""
    packet = load_packet()
    rv = packet.return_versions[-1]
    engine_value = rv.line("SchC.1").value

    unadjusted = resolved_line_value(packet, rv, "SchC.1", {})
    assert unadjusted == Decimal(str(engine_value))

    adjustments = {
        "SchC.1": Adjustment(
            id="adj-1",
            claim_key="SchC.1",
            old_value=str(engine_value),
            new_value="151300.0",
            evidence_refs=["D14", "ev-0103"],
        )
    }
    adjusted = resolved_line_value(packet, rv, "SchC.1", adjustments)
    assert adjusted == Decimal("151300.0")


def test_letter_566_pack_reads_items_from_the_packet_and_resolves_their_lines() -> None:
    packet = load_packet()
    pack = letter_566_pack(packet, {})
    assert pack["notice"]["id"] == "N-2025-L566"
    item_texts = [item["item"] for item in pack["items"]]
    assert any("Schedule A" in text for text in item_texts)
    assert any("gross receipts" in text.lower() for text in item_texts)

    gross_receipts_item = next(
        item for item in pack["items"] if "reconciliation" in item
    )
    assert gross_receipts_item["line_key"] == "SchC.1"
    forms_named = {
        entry["form"]: entry["amount"]
        for entry in gross_receipts_item["reconciliation"]["forms_named"]
    }
    assert forms_named["1099-NEC"] == "142000"
    assert forms_named["1099-K"] == "12400"


def test_letter_566_pack_shows_the_already_adjusted_workpaper_value() -> None:
    """Acceptance test A3: the reconciliation must come from the
    already-adjusted workpaper value (151,300), never a fresh
    142,000 + 12,400 re-derivation -- proven here by checking the
    reconciliation changes once the E3 adjustment exists, without this
    module doing any summing of its own."""
    packet = load_packet()
    rv = packet.return_versions[-1]
    engine_value = rv.line("SchC.1").value

    unadjusted_pack = letter_566_pack(packet, {})
    unadjusted_item = next(
        item for item in unadjusted_pack["items"] if "reconciliation" in item
    )
    assert Decimal(unadjusted_item["reconciliation"]["workpaper_value"]) == Decimal(
        str(engine_value)
    )

    adjustments = adjustments_by_claim(
        [
            Adjustment(
                id="adj-1",
                claim_key="SchC.1",
                old_value=str(engine_value),
                new_value="151300.0",
                evidence_refs=["D14", "ev-0103"],
            )
        ]
    )
    adjusted_pack = letter_566_pack(packet, adjustments)
    adjusted_item = next(
        item for item in adjusted_pack["items"] if "reconciliation" in item
    )
    assert Decimal(adjusted_item["reconciliation"]["workpaper_value"]) == Decimal(
        "151300.0"
    )


def test_letter_566_pack_with_no_matching_notice_returns_an_empty_pack() -> None:
    packet = load_packet()
    no_notice_packet = packet.model_copy(
        update={
            "tax_agency_records": packet.tax_agency_records.model_copy(
                update={"notices": []}
            )
        }
    )
    assert letter_566_pack(no_notice_packet, {}) == {"notice": None, "items": []}


def test_letter_566_pack_leaves_an_unresolvable_item_untraced() -> None:
    """An item naming a schedule+line that doesn't exist on this return
    (a different packet's Letter 566 might) gets no line key and no
    evidence, rather than raising -- genericity, not a hardcoded line
    key, is the whole point of the lookup."""
    packet = load_packet()
    notice = {
        "id": "N-TEST",
        "type": "Letter 566 (correspondence examination)",
        "items_under_examination": [
            "Schedule Z line 99: a schedule that doesn't exist.",
            "Foreign bank account reporting: no schedule named at all.",
        ],
    }
    test_packet = packet.model_copy(
        update={
            "tax_agency_records": packet.tax_agency_records.model_copy(
                update={"notices": [notice]}
            )
        }
    )
    pack = letter_566_pack(test_packet, {})
    assert pack["notice"]["id"] == "N-TEST"
    assert pack["items"] == [
        {
            "item": "Schedule Z line 99: a schedule that doesn't exist.",
            "line_key": None,
            "evidence": None,
        },
        {
            "item": "Foreign bank account reporting: no schedule named at all.",
            "line_key": None,
            "evidence": None,
        },
    ]
