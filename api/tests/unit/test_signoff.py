"""C2 sign-off support, proven against the real packet's D30/D31
scenario (docs/ACCEPTANCE.md A2).
"""

from proofline.analysis.signoff import (
    changes_since_sign_off,
    compare_document_dependents,
    compute_fingerprints,
    document_replacements,
)
from proofline.packet import load_packet


def test_document_replacements_finds_d31_as_d30s_replacement() -> None:
    packet = load_packet()
    v2 = packet.return_version("v2")
    assert document_replacements(packet, v2) == {"D30": "D31"}


def test_compare_document_dependents_finds_24_lines_3_changed_21_unchanged() -> None:
    packet = load_packet()
    v1 = packet.return_version("v1")
    v2 = packet.return_version("v2")

    comparison = compare_document_dependents(packet, v1, v2, "D30")

    assert len(comparison.unchanged) + len(comparison.changed) == 24
    assert len(comparison.changed) == 3
    assert len(comparison.unchanged) == 21
    changed_keys = {c.comparison_key for c in comparison.changed}
    assert changed_keys == {
        "1099b_lot:Meridian Brokerage:M6",
        "1099b_lot:Meridian Brokerage:M9",
        "1099b_lot:Meridian Brokerage:M14",
    }


def test_m14_keeps_its_identity_across_the_box_move() -> None:
    """CONTRACTS.md claim identity: M14 moved from box A to box D but is
    still the same claim."""
    packet = load_packet()
    v1 = packet.return_version("v1")
    v2 = packet.return_version("v2")

    comparison = compare_document_dependents(packet, v1, v2, "D30")
    m14 = next(
        c
        for c in comparison.changed
        if c.comparison_key == "1099b_lot:Meridian Brokerage:M14"
    )
    assert m14.old_line_key == "F8949.A.M14"
    assert m14.new_line_key == "F8949.D.M14"
    assert m14.old_value == m14.new_value == 855.0


def test_investments_scope_changed_because_m14_moved_box() -> None:
    """`scope_fingerprint` hashes line *keys*, not claim identity, so
    M14's box move (F8949.A.M14 -> F8949.D.M14) flips it even though M14
    is still the same claim -- CONTRACTS.md C2's "the scope: new claims
    need review" is read generously here as "scope membership moved",
    not strictly "a brand new claim exists". It's informational
    (`routes/areas.py` surfaces it as a blocking reason, never a hard
    block), so a false-ish positive here costs a reviewer's glance, not a
    wrong sign-off."""
    packet = load_packet()
    v1 = packet.return_version("v1")
    v2 = packet.return_version("v2")
    report = changes_since_sign_off(packet, v1, v2, "investments")
    assert report.scope_changed is True


def test_business_scope_is_unaffected_by_the_d30_d31_swap() -> None:
    packet = load_packet()
    v1 = packet.return_version("v1")
    v2 = packet.return_version("v2")
    report = changes_since_sign_off(packet, v1, v2, "business")
    assert report.value_changed is False
    assert report.evidence_only_changed is False
    assert report.scope_changed is False
    # D30 is replaced somewhere in the return (`document_replacements` is
    # global), but none of its dependent lines are in scope "business" --
    # business must not be asked to confirm a carry-over for a document
    # it never relied on (CONTRACTS.md A2: "Business stays signed").
    assert report.pending_documents == ()


def test_investments_scope_shows_change_pending() -> None:
    packet = load_packet()
    v1 = packet.return_version("v1")
    v2 = packet.return_version("v2")
    report = changes_since_sign_off(packet, v1, v2, "investments")
    assert report.value_changed is True
    assert report.pending_documents == (("D30", "D31"),)


def test_tax_computation_scope_shows_a_pending_change() -> None:
    packet = load_packet()
    v1 = packet.return_version("v1")
    v2 = packet.return_version("v2")
    report = changes_since_sign_off(packet, v1, v2, "tax_computation")
    assert report.value_changed is True


def test_compute_fingerprints_is_stable_for_the_same_version() -> None:
    packet = load_packet()
    v1 = packet.return_version("v1")
    assert compute_fingerprints(v1, "investments") == compute_fingerprints(
        v1, "investments"
    )
