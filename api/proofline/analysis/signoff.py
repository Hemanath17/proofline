"""C2 sign-off support: which scope a line belongs to, and what changed
in a scope between the version it was last signed at and the current one
(docs/CONTRACTS.md C2, acceptance test A2).

Scope assignment (`_FORM_SCOPE`) is tax-form domain knowledge (which form
covers which C2 scope), not a packet-specific mapping -- it never reads a
packet value to decide. Form 1040 is special-cased by line number because
one form spans two scopes: lines 1-8 are income sources, lines 9 onward
are the return-wide computation cascade (total income through amount
owed) that C2 calls "Tax computation." A handful of forms (Sch1) genuinely
span several real-world categories and are given the single best-fit
scope noted inline; a fuller per-line taxonomy is Step 9 polish, not
needed for A1/A2.
"""

from __future__ import annotations

from dataclasses import dataclass

from proofline.analysis.calculation import line_claim_identity
from proofline.checks.models import Area
from proofline.db.canonical import canonical_hash
from proofline.packet import Line, Packet, ReturnVersion

_FORM_SCOPE: dict[str, Area] = {
    "F8949": "investments",
    "SchD": "investments",
    "SchB": "investments",
    "F8960": "investments",
    "F6251": "investments",
    "SchC": "business",
    "SchSE": "business",
    "F4562-C": "business",
    "Sch1": "business",
    "SchE": "rentals",
    "F8582": "rentals",
    "F4797": "rentals",
    "F4562-E": "rentals",
    "F7203": "pass_throughs",
    "ScheduleS": "pass_throughs",
    "SchA": "deductions_credits",
    "F2441": "deductions_credits",
    "F8812": "deductions_credits",
    "F8863": "deductions_credits",
    "F8283": "deductions_credits",
    "F8606": "deductions_credits",
    "F8889": "deductions_credits",
    "F8867": "deductions_credits",
    "Sch3": "deductions_credits",
    "F540NR": "california",
    "SchCA540NR": "california",
    "FTB3885A": "california",
    "FTB5805": "california",
    "F8938": "identity",
    "F8959": "wages",
    "Sch2": "tax_computation",
}

_F1040_TOTALS_FROM_LINE_NUMBER = 9


def line_scope(line: Line) -> Area:
    if line.form == "F1040":
        digits = "".join(ch for ch in line.line if ch.isdigit())
        if digits and int(digits) >= _F1040_TOTALS_FROM_LINE_NUMBER:
            return "tax_computation"
        return "wages"
    return _FORM_SCOPE.get(line.form, "deductions_credits")


def scope_lines(rv: ReturnVersion, scope: Area) -> list[Line]:
    return [line for line in rv.lines if line_scope(line) == scope]


def _comparison_key(packet: Packet, line: Line) -> str:
    """The same claim can sit at a different line key across versions
    (CONTRACTS.md claim identity: lot M14 moving from box A to box D is
    still the same claim) -- compare by claim identity when one is known,
    falling back to the line key itself (a return-total claim's identity
    *is* its line key)."""
    claim = line_claim_identity(packet, line)
    return str(claim) if claim is not None else line.key


@dataclass(frozen=True)
class ChangedClaim:
    comparison_key: str
    old_line_key: str | None
    new_line_key: str | None
    old_value: object
    new_value: object


@dataclass(frozen=True)
class ScopeComparison:
    unchanged: tuple[str, ...]
    changed: tuple[ChangedClaim, ...]
    replaced_documents: tuple[tuple[str, str], ...]


def document_replacements(packet: Packet, new_rv: ReturnVersion) -> dict[str, str]:
    """Maps a superseded document to whichever new document replaced it,
    found generically (same issuer and document type), the same method
    already used to detect excluded duplicates in
    `proofline.provenance.tracing`."""
    replacements: dict[str, str] = {}
    for old_id in new_rv.documents_superseded:
        old_document = packet.document(old_id)
        replacement = next(
            (
                doc
                for doc in packet.documents
                if doc.id in new_rv.documents_used
                and doc.issuer == old_document.issuer
                and doc.document_type == old_document.document_type
            ),
            None,
        )
        if replacement is not None:
            replacements[old_id] = replacement.id
    return replacements


def _relied_on_fields(packet: Packet, line: Line) -> tuple:
    """Every field this line actually relied on: the engine's own value,
    plus every extracted value behind its `ev-` sources -- e.g. for a
    Form 8949 lot, that already includes descriptive fields like the
    acquisition date and term alongside proceeds and basis (the packet's
    own `sources` lists all of them, not just what the engine's formula
    used), which is exactly what lets a lot whose box/term changed but
    whose dollar value didn't (CONTRACTS.md A2's M14) still compare as
    changed: "identical in every field they relied on" is this tuple,
    not just the line's `value`."""
    fields = [("__value__", line.value)]
    for ref in line.sources:
        if ref.startswith("ev-"):
            extracted = packet.extracted_value(ref)
            fields.append((extracted.field, extracted.value))
    return tuple(sorted(fields))


def compare_document_dependents(
    packet: Packet, old_rv: ReturnVersion, new_rv: ReturnVersion, old_document_id: str
) -> ScopeComparison:
    """CONTRACTS.md A2: "the provenance resolver finds the ... lines that
    depended on" a now-superseded document. Every line that directly used
    `old_document_id` in `old_rv` (via `proofline.provenance.tracing`'s
    own document-dependency logic, reused here through `trace_document`)
    is compared, by claim identity, against its counterpart in `new_rv`
    -- so a lot that only moved box (M14) still resolves to the same
    claim and can compare as changed on fields other than its value."""
    from proofline.provenance.tracing import trace_document

    old_dependent_keys = trace_document(
        packet, old_document_id, version=old_rv.version
    ).lines_using
    new_lines_by_comparison_key = {
        _comparison_key(packet, line): line for line in new_rv.lines
    }

    unchanged: list[str] = []
    changed: list[ChangedClaim] = []
    for old_line_key in old_dependent_keys:
        old_line = old_rv.line(old_line_key)
        comparison_key = _comparison_key(packet, old_line)
        new_line = new_lines_by_comparison_key.get(comparison_key)
        if new_line is not None and _relied_on_fields(
            packet, old_line
        ) == _relied_on_fields(packet, new_line):
            unchanged.append(comparison_key)
        else:
            changed.append(
                ChangedClaim(
                    comparison_key=comparison_key,
                    old_line_key=old_line.key,
                    new_line_key=new_line.key if new_line is not None else None,
                    old_value=old_line.value,
                    new_value=new_line.value if new_line is not None else None,
                )
            )

    return ScopeComparison(
        unchanged=tuple(unchanged), changed=tuple(changed), replaced_documents=()
    )


@dataclass(frozen=True)
class Fingerprints:
    evidence: str
    values: str
    decisions: str
    scope: str


def compute_fingerprints(
    rv: ReturnVersion,
    scope: Area,
    resolved_decision_ids: list[str] | None = None,
) -> Fingerprints:
    lines = scope_lines(rv, scope)
    evidence = canonical_hash({line.key: sorted(line.sources) for line in lines})
    values = canonical_hash({line.key: str(line.value) for line in lines})
    decisions = canonical_hash({"decisions": sorted(resolved_decision_ids or [])})
    scope_fp = canonical_hash({"lines": sorted(line.key for line in lines)})
    return Fingerprints(
        evidence=evidence, values=values, decisions=decisions, scope=scope_fp
    )


@dataclass(frozen=True)
class SignOffChangeReport:
    """What a scope's sign-off needs to deal with, comparing the version
    it was last signed at against the current one. `value_changed` means
    a real change a reviewer must look at again; `evidence_only_changed`
    means every affected line's fields are otherwise identical and the
    only thing that moved is which document it came from -- CONTRACTS.md
    C2's carry-over case, resolvable with one `confirm_carryover` per
    entry in `pending_documents` instead of a full re-review."""

    value_changed: bool
    evidence_only_changed: bool
    scope_changed: bool
    pending_documents: tuple[tuple[str, str], ...]
    document_comparisons: dict[tuple[str, str], ScopeComparison]


def changes_since_sign_off(
    packet: Packet, old_rv: ReturnVersion, new_rv: ReturnVersion, scope: Area
) -> SignOffChangeReport:
    from proofline.provenance.tracing import trace_document

    old_fp = compute_fingerprints(old_rv, scope)
    new_fp = compute_fingerprints(new_rv, scope)
    value_changed = old_fp.values != new_fp.values
    evidence_changed = old_fp.evidence != new_fp.evidence
    # CONTRACTS.md C2: "The scope: New claims need review before the next
    # version." `scope_fp` is already a pure function of (rv, scope), so
    # comparing it the same way as values/evidence is enough -- no
    # database access needed here, unlike the decisions fingerprint
    # (actions/sign_offs.py's own job, since "resolved" is live DB state,
    # not something either return version alone can answer).
    scope_changed = old_fp.scope != new_fp.scope

    # `document_replacements` is global (every document replaced anywhere
    # in the return), not scoped -- a replacement only belongs on *this*
    # scope's report when the old document actually fed at least one line
    # in this scope (CONTRACTS.md A2: "Business stays signed" even though
    # D30 was replaced, since none of D30's dependent lines are in scope
    # "business"; only investments/wages/california/deductions_credits
    # lines cite it).
    scope_line_keys = {line.key for line in scope_lines(old_rv, scope)}
    replacements = {
        old_id: new_id
        for old_id, new_id in document_replacements(packet, new_rv).items()
        if scope_line_keys
        & set(trace_document(packet, old_id, version=old_rv.version).lines_using)
    }
    comparisons = {
        (old_id, new_id): compare_document_dependents(packet, old_rv, new_rv, old_id)
        for old_id, new_id in replacements.items()
    }
    return SignOffChangeReport(
        value_changed=value_changed,
        evidence_only_changed=evidence_changed and not value_changed,
        scope_changed=scope_changed,
        pending_documents=tuple(replacements.items()),
        document_comparisons=comparisons,
    )
