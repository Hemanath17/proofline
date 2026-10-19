"""C5's package, its fingerprints, and the post-filing Letter 566 pack.

The package is everything a filing authorizes: the workpaper's current
values with their labels, every scope's current sign-off version, every
active adjustment, every used document's id and content hash, and two
fingerprints -- amounts and identity. `reference` is the package's own
identity: a hash over all of the above, so two packages are "the same"
exactly when every one of those facts agrees.

`amounts_fingerprint` reuses `compute_fingerprints` (Step 7's sign-off
fingerprints) per scope, combined -- never a second scheme that could
disagree with it. It fingerprints the *engine's* line values, the same
way `compute_fingerprints` always has, not `workpaper_value`'s
adjustment-overlaid ones -- see `_amounts_fingerprint`'s own docstring
for why that's fine for `submit_filing`'s purposes. `identity_fingerprint`
has no existing equivalent to reuse: it hashes each household person's
SSN and name (the fields Publication 1345 ties to a required
re-signature), honoring any approved adjustment on that field the same
way a line's workpaper value honors one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from proofline.analysis.calculation import (
    ValueLabel,
    adjustments_by_claim,
    workpaper_value,
)
from proofline.analysis.signoff import (
    compute_fingerprints,
    resolved_decision_ids_in_scope,
)
from proofline.checks.models import Area
from proofline.checks.money import parse_money
from proofline.db.canonical import canonical_hash
from proofline.db.models import Adjustment
from proofline.db.repository import get_latest_sign_off, list_adjustments
from proofline.packet import Document, Packet, ReturnVersion
from proofline.provenance.claim_identity import household_fact, return_total

AREAS: tuple[Area, ...] = (
    "identity",
    "wages",
    "investments",
    "business",
    "rentals",
    "pass_throughs",
    "deductions_credits",
    "california",
    "tax_computation",
)

_IDENTITY_FIELDS = ("ssn", "name")


def document_content_hash(document: Document) -> str:
    """A deterministic hash of what the document actually says
    (`printed_content`, the packet's own source of truth -- "extracted
    values and engine results can be wrong," docs/PACKET.md), covering
    every page's number and text, sorted by page so page order in the
    packet never changes the hash."""
    pages = sorted(
        (
            {"page": page.page, "printed_content": page.printed_content}
            for page in document.pages
        ),
        key=lambda page: page["page"],
    )
    return canonical_hash({"document_id": document.id, "pages": pages})


def identity_fingerprint(packet: Packet, adjustments: dict[str, Adjustment]) -> str:
    people: dict[str, dict[str, str]] = {}
    for person in packet.household.people:
        record: dict[str, str] = {}
        for field, raw_value in ((f, getattr(person, f)) for f in _IDENTITY_FIELDS):
            claim_key = str(household_fact(person.id, field))
            adjustment = adjustments.get(claim_key)
            record[field] = (
                adjustment.new_value if adjustment is not None else raw_value
            )
        people[person.id] = record
    addresses = sorted(address.address for address in packet.household.addresses)
    return canonical_hash({"people": people, "addresses": addresses})


@dataclass(frozen=True)
class PackageLine:
    line_key: str
    label: str | None
    value: Any
    provenance_label: str


@dataclass(frozen=True)
class PackageDocument:
    document_id: str
    content_hash: str


@dataclass(frozen=True)
class Package:
    engine_version: str
    lines: tuple[PackageLine, ...]
    sign_off_versions: dict[str, int | None]
    active_adjustment_ids: tuple[str, ...]
    documents: tuple[PackageDocument, ...]
    amounts_fingerprint: str
    identity_fingerprint: str
    reference: str


def _amounts_fingerprint(session: Session, rv: ReturnVersion) -> str:
    """Reuses `compute_fingerprints` (Step 7) unmodified, per scope --
    its `.values` component is the *raw engine* `line.value`, not
    `workpaper_value`'s adjustment-overlaid one (confirmed: it ignores
    `resolved_decision_ids` entirely). So this fingerprint only changes
    when the engine itself recomputes a scope's lines (a new document or
    engine version), never because a case was resolved into an
    adjustment -- consistent with Step 7's own C2 design, where a
    resolved decision is tracked as "decisions changed," not "a value
    changed." `submit_filing`'s re-authorization gate doesn't depend on
    this distinction: it compares the *whole package* `reference` (which
    does include every adjustment, via `lines`/`active_adjustment_ids`
    below), not this fingerprint alone."""
    return canonical_hash(
        {
            scope: compute_fingerprints(
                rv, scope, resolved_decision_ids_in_scope(session, scope)
            ).values
            for scope in AREAS
        }
    )


def build_package(session: Session, packet: Packet, rv: ReturnVersion) -> Package:
    adjustments = adjustments_by_claim(list_adjustments(session))
    lines = tuple(
        PackageLine(
            line_key=line.key,
            label=line.label,
            value=(vl := resolved_value_label(packet, rv, line.key, adjustments)).value,
            provenance_label=vl.label,
        )
        for line in rv.lines
    )
    sign_off_versions: dict[str, int | None] = {
        scope: (so.version if (so := get_latest_sign_off(session, scope)) else None)
        for scope in AREAS
    }
    active_adjustment_ids = tuple(sorted(a.id for a in list_adjustments(session)))
    documents = tuple(
        sorted(
            (
                PackageDocument(
                    document_id=document_id,
                    content_hash=document_content_hash(packet.document(document_id)),
                )
                for document_id in rv.documents_used
            ),
            key=lambda d: d.document_id,
        )
    )
    amounts_fp = _amounts_fingerprint(session, rv)
    identity_fp = identity_fingerprint(packet, adjustments)
    reference = canonical_hash(
        {
            "engine_version": rv.version,
            "lines": [
                {
                    "line_key": line.line_key,
                    "label": line.label,
                    "value": line.value,
                    "provenance_label": line.provenance_label,
                }
                for line in lines
            ],
            "sign_off_versions": sign_off_versions,
            "active_adjustment_ids": list(active_adjustment_ids),
            "documents": [
                {"document_id": d.document_id, "content_hash": d.content_hash}
                for d in documents
            ],
            "amounts_fingerprint": amounts_fp,
            "identity_fingerprint": identity_fp,
        }
    )
    return Package(
        engine_version=rv.version,
        lines=lines,
        sign_off_versions=sign_off_versions,
        active_adjustment_ids=active_adjustment_ids,
        documents=documents,
        amounts_fingerprint=amounts_fp,
        identity_fingerprint=identity_fp,
        reference=reference,
    )


def package_to_dict(package: Package) -> dict[str, Any]:
    return {
        "engine_version": package.engine_version,
        "lines": [
            {
                "line_key": line.line_key,
                "label": line.label,
                "value": line.value,
                "provenance_label": line.provenance_label,
            }
            for line in package.lines
        ],
        "sign_off_versions": package.sign_off_versions,
        "active_adjustment_ids": list(package.active_adjustment_ids),
        "documents": [
            {"document_id": d.document_id, "content_hash": d.content_hash}
            for d in package.documents
        ],
        "amounts_fingerprint": package.amounts_fingerprint,
        "identity_fingerprint": package.identity_fingerprint,
        "reference": package.reference,
    }


def resolved_value_label(
    packet: Packet,
    rv: ReturnVersion,
    line_key: str,
    adjustments: dict[str, Adjustment],
) -> ValueLabel:
    """Like `workpaper_value`, but also honors a direct adjustment keyed by
    the line's own return-wide-total claim identity (`return_total`) --
    needed for a line such as SchC.1 that `line_claim_identity` doesn't
    otherwise resolve (its claim support today only covers Form 8949
    lots). Used for *this* line's own value only -- it does not make
    `workpaper_value`'s R-SUM/R-CARRY recursion adjustment-aware for a
    `return_total` claim on some other line further down the chain, so a
    line that sums over an adjusted `return_total` line (e.g. total
    income summing over an adjusted SchC.1) still won't see the
    adjustment propagate upward. Extending that generically is deferred
    (see docs/DECISIONS.md) -- it would mean duplicating or changing
    `workpaper_value`'s own recursion, not a small local addition like
    this one. Kept local to `filing.py` rather than widening
    `line_claim_identity` itself, which would also change what
    `bulk_verify` and the area-detail "verify" column treat as
    verifiable for every other line in the return -- a much bigger
    change than this step asks for."""
    claim_key = str(return_total(line_key))
    adjustment = adjustments.get(claim_key)
    if adjustment is not None:
        return ValueLabel(
            value=parse_money(adjustment.new_value),
            label="adjusted",
            engine_version=rv.version,
            adjustment=adjustment,
        )
    return workpaper_value(packet, rv, line_key, adjustments)


def resolved_line_value(
    packet: Packet,
    rv: ReturnVersion,
    line_key: str,
    adjustments: dict[str, Adjustment],
) -> Decimal | None:
    """`resolved_value_label`'s value, as `Decimal` -- what
    `letter_566_pack`'s reconciliation actually needs."""
    return parse_money(resolved_value_label(packet, rv, line_key, adjustments).value)


_SCHEDULE_LINE_RE = re.compile(r"\bSchedule\s+([A-Za-z])\s+line\s+(\w+)", re.IGNORECASE)
_SCHEDULE_RE = re.compile(r"\bSchedule\s+([A-Za-z])\b", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z]+")
_DOLLAR_NEAR_FORM_RE = re.compile(
    r"Forms?\s+(1099-[A-Z]+)\s*\(([\d,]+)\)", re.IGNORECASE
)


def _line_mentioned_by_schedule_and_line(rv: ReturnVersion, item_text: str):
    match = _SCHEDULE_LINE_RE.search(item_text)
    if match is None:
        return None
    schedule_letter, line_no = match.groups()
    try:
        return rv.line(f"Sch{schedule_letter.upper()}.{line_no}")
    except KeyError:
        return None


def _line_mentioned_by_schedule_and_label(rv: ReturnVersion, item_text: str):
    """Falls back to matching the item's own words against each
    candidate line's label (e.g. "Schedule C gross receipts" against
    SchC.1's label "Gross receipts") when the item names a schedule but
    no specific line number -- generic word-overlap, not a hardcoded line
    key, since a notice's own phrasing isn't itself a contract."""
    schedule_match = _SCHEDULE_RE.search(item_text)
    if schedule_match is None:
        return None
    form = f"Sch{schedule_match.group(1).upper()}"
    candidates = [line for line in rv.lines if line.form == form]
    if not candidates:
        return None
    item_words = set(_WORD_RE.findall(item_text.lower()))
    best, best_overlap = None, 0
    for line in candidates:
        overlap = len(item_words & set(_WORD_RE.findall((line.label or "").lower())))
        if overlap > best_overlap:
            best, best_overlap = line, overlap
    return best


def letter_566_pack(
    packet: Packet, adjustments: dict[str, Adjustment]
) -> dict[str, Any]:
    """CONTRACTS.md C5 "after filing", acceptance test A3: the specific
    items a Letter 566 names (read from the packet's own notice, never
    hardcoded), each traced to its workpaper evidence, and the Schedule C
    gross-receipts reconciliation -- read from the already-adjusted
    workpaper value (the E3 double-count correction, once resolved), not
    re-derived independently from the forms' own totals."""
    notice = next(
        (
            n
            for n in packet.tax_agency_records.notices
            if "letter 566" in str(n.get("type", "")).lower()
        ),
        None,
    )
    if notice is None:
        return {"notice": None, "items": []}

    rv = packet.return_versions[-1]
    items: list[dict[str, Any]] = []
    for item_text in notice.get("items_under_examination", []):
        line = _line_mentioned_by_schedule_and_line(
            rv, item_text
        ) or _line_mentioned_by_schedule_and_label(rv, item_text)
        entry: dict[str, Any] = {"item": item_text, "line_key": None, "evidence": None}
        if line is not None:
            entry["line_key"] = line.key
            entry["evidence"] = {
                "sources": list(line.sources),
                "note": line.note,
            }
        if "gross receipts" in item_text.lower():
            forms_named = [
                {"form": form, "amount": str(parse_money(amount))}
                for form, amount in _DOLLAR_NEAR_FORM_RE.findall(item_text)
            ]
            workpaper = (
                resolved_line_value(packet, rv, line.key, adjustments)
                if line is not None
                else None
            )
            entry["reconciliation"] = {
                "forms_named": forms_named,
                "workpaper_value": str(workpaper) if workpaper is not None else None,
            }
        items.append(entry)

    return {
        "notice": {
            "id": notice.get("id"),
            "agency": notice.get("agency"),
            "type": notice.get("type"),
            "tax_year": notice.get("tax_year"),
            "dated": notice.get("dated"),
            "response_due": notice.get("response_due"),
            "document": notice.get("document"),
        },
        "items": items,
    }
