"""One test per reference format, plus a sweep across every reference
actually present in the packet's known reference-bearing fields. The sweep
is the Step 2 "Done when": every reference in the packet resolves.
"""

from __future__ import annotations

import pytest

from proofline.packet import load_packet
from proofline.provenance.resolver import UnresolvedReferenceError, resolve


@pytest.fixture(scope="module")
def packet():
    return load_packet()


def test_resolve_extracted_value(packet) -> None:
    resolved = resolve("ev-0016", packet)
    assert resolved.kind == "extracted_value"
    assert resolved.value.document_id == "D08"


def test_resolve_document(packet) -> None:
    resolved = resolve("D08", packet)
    assert resolved.kind == "document"
    assert resolved.value.id == "D08"


def test_resolve_document_page(packet) -> None:
    resolved = resolve("doc:D31#page32", packet)
    assert resolved.kind == "document_page"
    assert resolved.value.page == 32


def test_resolve_questionnaire_message_call(packet) -> None:
    assert resolve("qa-01", packet).kind == "questionnaire_item"
    assert resolve("msg-01", packet).kind == "message"
    assert resolve("call-01", packet).kind == "call_note"


def test_resolve_prior_years_pointer(packet) -> None:
    resolved = resolve("py:/asset_records", packet)
    assert resolved.kind == "prior_years"
    assert isinstance(resolved.value, list)


def test_resolve_agency_pointer(packet) -> None:
    resolved = resolve("agency:/efile", packet)
    assert resolved.kind == "tax_agency_records"


def test_resolve_asset(packet) -> None:
    resolved = resolve("asset:SAC-BLDG", packet)
    assert resolved.kind == "asset"
    assert resolved.value.asset_id == "SAC-BLDG"


def test_resolve_household(packet) -> None:
    resolved = resolve("household:ada", packet)
    assert resolved.kind == "household_person"
    assert resolved.value.id == "ada"


def test_resolve_ref_param(packet) -> None:
    resolved = resolve("ref:param.mileage_rate", packet)
    assert resolved.kind == "engine_parameter"


def test_resolve_ref_fx(packet) -> None:
    resolved = resolve("ref:fx.SEK.2025_average", packet)
    assert resolved.kind == "fx_rate"


def test_resolve_timeline_non_tl_prefixed_id(packet) -> None:
    resolved = resolve("timeline:extension-2026-04-14", packet)
    assert resolved.kind == "timeline_event"


def test_resolve_line_key(packet) -> None:
    resolved = resolve("F1040.1a", packet)
    assert resolved.kind == "line"


def test_unresolved_reference_raises(packet) -> None:
    with pytest.raises(UnresolvedReferenceError):
        resolve("ev-9999", packet)


def _collect_all_references(packet) -> set[tuple[str, str]]:
    """Every literal reference string in the packet's known reference
    fields, paired with the return-version it should resolve against. A
    changes_from_previous key may belong to the current version (added,
    changed) or only to the previous one (removed, e.g. a line that moved
    boxes), so those are returned separately and checked against both."""
    refs: set[tuple[str, str]] = set()
    change_candidates: set[tuple[str, tuple[str, ...]]] = set()

    for index, rv in enumerate(packet.return_versions):
        for doc_id in [*rv.documents_used, *rv.documents_superseded]:
            refs.add((doc_id, rv.version))
        for line in rv.lines:
            for source_ref in line.sources:
                refs.add((source_ref, rv.version))
            for input_key in line.inputs:
                refs.add((input_key, rv.version))
        for asset in rv.assets:
            for source_ref in asset.sources:
                refs.add((source_ref, rv.version))
        for diagnostic in rv.diagnostics:
            for ref in diagnostic.refs:
                refs.add((ref, rv.version))
        for change in rv.changes_from_previous:
            candidate_versions = [rv.version]
            if index > 0:
                candidate_versions.append(packet.return_versions[index - 1].version)
            change_candidates.add((change.key, tuple(candidate_versions)))

    for alternative in packet.what_if.alternatives:
        for changed_line in alternative.changed_lines:
            refs.add((changed_line.key, alternative.base_version))

    return_2024 = packet.prior_years.return_2024
    for line_source_ref in return_2024.get("line_sources", {}).values():
        refs.add((line_source_ref, "v3"))

    for notice in packet.tax_agency_records.notices:
        document_ref = notice.get("document")
        if document_ref:
            refs.add((document_ref, "v3"))

    return refs, change_candidates


def test_every_reference_in_the_packet_resolves(packet) -> None:
    all_refs, change_candidates = _collect_all_references(packet)
    assert len(all_refs) > 0, "the sweep should have found references to check"

    unresolved: list[str] = []
    for ref, version in all_refs:
        try:
            resolve(ref, packet, version=version)
        except UnresolvedReferenceError as exc:
            unresolved.append(str(exc))

    for key, candidate_versions in change_candidates:
        resolved_any = False
        errors = []
        for version in candidate_versions:
            try:
                resolve(key, packet, version=version)
                resolved_any = True
                break
            except UnresolvedReferenceError as exc:
                errors.append(str(exc))
        if not resolved_any:
            unresolved.append(
                f"{key}: unresolved against every candidate version {candidate_versions}: {errors}"
            )

    assert unresolved == []
