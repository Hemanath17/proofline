"""B20, C5's last condition: filings outside this engagement's own scope
(FBAR, contractor 1099-NECs, the 2023 Form 3520 question, the Oregon
composite) -- each found generically from where the packet already
mentions it (a diagnostic, the prior preparer's open items, a related
return), never a hardcoded name with no packet reference behind it.
Decided/not-decided status is log-only, like a readiness attestation item
(`proofline.actions.outside_filings.confirm_outside_filing`), read back by
replaying each item's own events.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from proofline.db.repository import list_events_for_entity
from proofline.packet import Packet

# Diagnostic code -> (stable item key, plain-language label). Tax-form
# domain knowledge about which diagnostics name an outside filing, the
# same kind of fixed mapping `analysis/signoff.py`'s `_FORM_SCOPE` already
# uses for forms -> scopes -- it never reads a packet *value* to decide,
# only whether a diagnostic with this *code* is present at all.
_DIAGNOSTIC_ITEMS: dict[str, tuple[str, str]] = {
    "FBAR_OUTSIDE_RETURN": ("fbar", "FBAR (FinCEN Form 114)"),
    "FORM_1099_FILING": ("contractor_1099_nec", "Contractor Form 1099-NEC filings"),
}


@dataclass(frozen=True)
class OutsideFilingItem:
    item: str
    label: str
    evidence_refs: tuple[str, ...]
    note: str


def outside_filing_items(packet: Packet) -> list[OutsideFilingItem]:
    rv = packet.return_versions[-1]
    items: list[OutsideFilingItem] = []

    for diagnostic in rv.diagnostics:
        found = _DIAGNOSTIC_ITEMS.get(diagnostic.code)
        if found is None:
            continue
        item_key, label = found
        items.append(
            OutsideFilingItem(
                item=item_key,
                label=label,
                evidence_refs=tuple(diagnostic.refs),
                note=diagnostic.message,
            )
        )

    open_items = packet.prior_years.prior_preparer_workpaper.get(
        "open_items_left_by_prior_preparer", []
    )
    for index, text in enumerate(open_items):
        if "3520" in str(text):
            items.append(
                OutsideFilingItem(
                    item="form_3520_2023",
                    label="2023 Form 3520 (foreign inheritance)",
                    evidence_refs=(
                        f"py:/prior_years/prior_preparer_workpaper/open_items_left_by_prior_preparer/{index}",
                    ),
                    note=str(text),
                )
            )

    for index, entry in enumerate(packet.household.related_returns):
        text = json.dumps(entry).lower()
        if "oregon" in text and "composite" in text:
            items.append(
                OutsideFilingItem(
                    item="oregon_composite",
                    label="Oregon composite return",
                    evidence_refs=(f"py:/household/related_returns/{index}",),
                    note=json.dumps(entry),
                )
            )

    return items


@dataclass(frozen=True)
class OutsideFilingStatus:
    item: str
    label: str
    evidence_refs: tuple[str, ...]
    note: str
    decided: bool
    decision: str | None
    decided_by: str | None
    decided_note: str | None


def outside_filings_report(
    session: Session, packet: Packet
) -> list[OutsideFilingStatus]:
    report = []
    for found in outside_filing_items(packet):
        events = list_events_for_entity(session, "outside_filing", found.item)
        latest = events[-1] if events else None
        report.append(
            OutsideFilingStatus(
                item=found.item,
                label=found.label,
                evidence_refs=found.evidence_refs,
                note=found.note,
                decided=latest is not None,
                decision=latest.payload.get("decision") if latest else None,
                decided_by=latest.actor_id if latest else None,
                decided_note=latest.payload.get("note") if latest else None,
            )
        )
    return report
