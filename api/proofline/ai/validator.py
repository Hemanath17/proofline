"""Deterministic validation of an `InvestigatorSuggestion` -- no model
calls here, and nothing here is specific to any one case or packet value
(CLAUDE.md: "A check is a general rule that should work on any client's
packet" applies just as much to this).

Four checks, all against the one case the suggestion claims to be about:
1. Every cited claim id is one of the case's own `claims`.
2. Every cited document id is reachable from the case's own
   `evidence_refs` -- this is the "no distractor evidence" boundary: a
   document that exists in the packet but isn't actually tied to this
   case's evidence fails here even if it's real and even if it's about
   the same packet.
3. Every number in `numbers_cited` actually appears (within a cent) in
   that same evidence -- an extracted value's own parsed amount, or a
   number parsed out of a cited document's own page text, never a
   substring match against formatted currency.
4. `proposed_resolution_type`/`proposed_fields` are a transition the
   case's current state could actually accept as a proposal (reusing
   `validate_resolution_fields` and `submit_proposal`'s own evidence-
   presence rule from `proofline.actions.cases` -- not duplicated here).
   This does NOT re-check the `ai_assistant` role against
   `check_permission`: the AI never calls `submit_proposal` itself (there
   is no code path for that), so there is nothing to re-derive there --
   only a human, through the ordinary action service, ever does (see
   docs/DECISIONS.md).

A suggestion that fails any of these is never silently upgraded: this
module always returns every reason it found, and the caller
(`proofline.ai.investigator`) forces `confidence="uncertain"` whenever
there's at least one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from proofline.actions.cases import validate_resolution_fields
from proofline.actions.errors import ActionValidationError
from proofline.ai.schema import InvestigatorSuggestion
from proofline.checks.money import parse_money
from proofline.db.models import Case
from proofline.packet import Packet
from proofline.provenance.resolver import Resolved, UnresolvedReferenceError, resolve

_DOCUMENT_ID_RE = re.compile(r"^D\d{2}$")
_MONEY_RE = re.compile(r"-?\(?\$?\d[\d,]*\.\d{2}\)?")
# Free text (a client message, call note or questionnaire answer) prints
# money more loosely than a document -- "about 3,050", no cents
# (CLAUDE.md: "Printed amounts may omit cents; parse numbers before
# comparing text to values"). Requires either comma-grouping or exact
# cents, so a bare year or id number doesn't get picked up as "evidence".
_TEXT_MONEY_RE = re.compile(
    r"(?<!\d)\$?\d{1,3}(?:,\d{3})+(?:\.\d{2})?(?!\d)|(?<!\d)\$?\d+\.\d{2}(?!\d)"
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reasons: tuple[str, ...]


def _documents_behind(packet: Packet, resolved: Resolved, version: str) -> set[str]:
    if resolved.kind == "extracted_value":
        return {resolved.value.document_id}
    if resolved.kind == "document":
        return {resolved.ref}
    if resolved.kind == "asset":
        documents: set[str] = set()
        for nested_ref in resolved.value.sources:
            try:
                nested = resolve(nested_ref, packet, version)
            except UnresolvedReferenceError:
                continue
            documents |= _documents_behind(packet, nested, version)
        return documents
    return set()


def _allowed_documents(packet: Packet, case: Case, version: str = "v3") -> set[str]:
    """Every document id reachable from this case's own `evidence_refs`."""
    allowed: set[str] = set()
    for ref in case.evidence_refs:
        if _DOCUMENT_ID_RE.match(ref):
            allowed.add(ref)
            continue
        try:
            resolved = resolve(ref, packet, version)
        except UnresolvedReferenceError:
            continue
        allowed |= _documents_behind(packet, resolved, version)
    return allowed


def _evidence_numbers(
    packet: Packet, case: Case, allowed_documents: set[str]
) -> set[Decimal]:
    numbers: set[Decimal] = set()
    if case.tax_effect_federal is not None:
        numbers.add(Decimal(case.tax_effect_federal))
    if case.tax_effect_california is not None:
        numbers.add(Decimal(case.tax_effect_california))
    for value in packet.extracted_values:
        if value.document_id not in allowed_documents:
            continue
        try:
            parsed = parse_money(value.value)
        except ValueError:
            continue
        if parsed is not None:
            numbers.add(parsed)
    for document_id in allowed_documents:
        document = packet.document(document_id)
        for page in document.pages:
            for match in _MONEY_RE.findall(page.printed_content):
                try:
                    parsed = parse_money(match)
                except ValueError:
                    continue
                if parsed is not None:
                    numbers.add(parsed)
    for text in _case_evidence_text(packet, case):
        for match in _TEXT_MONEY_RE.findall(text):
            try:
                parsed = parse_money(match)
            except ValueError:
                continue
            if parsed is not None:
                numbers.add(parsed)
    return numbers


def _case_evidence_text(packet: Packet, case: Case) -> list[str]:
    """Free text from the case's own client-origin evidence (a qa-,
    msg- or call- reference) -- a client's own words are legitimate
    evidence for a `record_judgment`/`resolve_evidence_conflict`
    citation (CLAUDE.md: "What the client tells us is not verification.
    Accepting it is a judgment someone records" -- it can still be cited,
    just never as if it settled the question on its own)."""
    blocks: list[str] = []
    for ref in case.evidence_refs:
        try:
            resolved = resolve(ref, packet)
        except UnresolvedReferenceError:
            continue
        if resolved.kind == "message":
            blocks.append(resolved.value.text)
        elif resolved.kind == "questionnaire_item":
            blocks.append(resolved.value.question)
            blocks.append(str(resolved.value.answer))
        elif resolved.kind == "call_note":
            blocks.extend(resolved.value.notes)
    return blocks


def validate_suggestion(
    packet: Packet, case: Case, suggestion: InvestigatorSuggestion
) -> ValidationResult:
    reasons: list[str] = []

    allowed_claims = set(case.claims)
    for claim_id in suggestion.cited_claim_ids:
        if claim_id not in allowed_claims:
            reasons.append(
                f"cited claim {claim_id!r} doesn't belong to case {case.case_id}"
            )

    allowed_documents = _allowed_documents(packet, case)
    for document_id in suggestion.cited_document_ids:
        if document_id not in allowed_documents:
            reasons.append(
                f"cited document {document_id!r} doesn't belong to case {case.case_id}"
            )

    if not any("doesn't belong to case" in reason for reason in reasons):
        evidence_numbers = _evidence_numbers(packet, case, allowed_documents)
        for number in suggestion.numbers_cited:
            if not any(
                abs(number - evidence) <= Decimal("0.01")
                for evidence in evidence_numbers
            ):
                reasons.append(
                    f"cited number {number} doesn't appear in case {case.case_id}'s "
                    "own evidence"
                )

    if case.status != "investigating":
        reasons.append(
            f"case is {case.status!r}, not investigating -- a proposal can't be "
            "submitted from here"
        )

    try:
        validate_resolution_fields(
            suggestion.proposed_resolution_type, suggestion.proposed_fields
        )
    except ActionValidationError as exc:
        reasons.append(exc.detail)

    has_evidence = bool(suggestion.cited_claim_ids or suggestion.cited_document_ids)
    if suggestion.proposed_resolution_type != "record_judgment" and not has_evidence:
        reasons.append(
            f"{suggestion.proposed_resolution_type} needs at least one piece of "
            "supporting evidence, same as submit_proposal requires"
        )

    return ValidationResult(ok=not reasons, reasons=tuple(reasons))
