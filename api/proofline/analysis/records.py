"""The sixteen CPA record views (R01-R16, docs/PLAN.md Step 9). Each is a
view over data Steps 1-8 already computed -- no new engine logic, and
R06/R12/R13 in particular are "the same thing already built, surfaced as
a report." Functions take whatever of (session, packet) they actually
need; several need neither beyond the packet itself.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from proofline.analysis.calculation import adjustments_by_claim, workpaper_value
from proofline.analysis.judgments import list_judgments
from proofline.analysis.outside_filings import outside_filings_report
from proofline.analysis.readiness import (
    california_estimated_payments_posted,
    federal_estimated_payments_posted,
)
from proofline.analysis.signoff import scope_detail_rows, scope_lines
from proofline.analysis.tie_outs import scope_tie_outs
from proofline.analysis.time_tracking import time_budget_report
from proofline.checks.models import Area
from proofline.checks.money import parse_money
from proofline.db.repository import (
    get_document_disposition,
    get_latest_sign_off,
    list_adjustments,
    list_cases,
)
from proofline.packet import Line, Packet, ReturnVersion
from proofline.provenance.tracing import trace_document

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

_OPEN_CASE_STATUSES = {
    "open",
    "investigating",
    "waiting_on_client",
    "in_review",
    "awaiting_partner",
}


def _line_row(
    packet: Packet, rv: ReturnVersion, line: Line, adjustments: dict[str, Any]
) -> dict[str, Any]:
    workpaper = workpaper_value(packet, rv, line.key, adjustments)
    return {
        "line_key": line.key,
        "label": line.label,
        "form": line.form,
        "value": workpaper.value,
        "provenance_label": workpaper.label,
    }


def _line_rows(
    packet: Packet,
    rv: ReturnVersion,
    lines: Iterable[Line],
    adjustments: dict[str, Any],
) -> list[dict[str, Any]]:
    return [_line_row(packet, rv, line, adjustments) for line in lines]


# --- R01: return summary vs last year -------------------------------------


def return_summary_vs_last_year(
    session: Session, packet: Packet
) -> list[dict[str, Any]]:
    """The firm's own variance rule (`firm.starter_standards.variance_review`)
    flags a row -- read from the packet, never a second hardcoded threshold."""
    rv = packet.return_versions[-1]
    adjustments = adjustments_by_claim(list_adjustments(session))
    prior_lines: dict[str, Any] = packet.prior_years.return_2024.get("lines", {})
    variance = packet.firm.starter_standards.variance_review

    rows = []
    for key, old_raw in prior_lines.items():
        try:
            line = rv.line(key)
        except KeyError:
            continue
        try:
            old_value = parse_money(old_raw)
            new_value = parse_money(workpaper_value(packet, rv, key, adjustments).value)
        except ValueError:
            # Not every line in last year's or this year's file is money
            # (some are status strings like "Yes"/"Not completed") -- a
            # variance comparison only makes sense for the ones that are.
            continue
        if old_value is None or new_value is None:
            continue
        difference = new_value - old_value
        percent_change = (
            (abs(difference) / abs(old_value) * 100) if old_value != 0 else Decimal(0)
        )
        flagged = variance is not None and (
            abs(difference) > variance.and_over_amount
            and percent_change > variance.flag_if_change_over_percent
        )
        rows.append(
            {
                "line_key": key,
                "label": line.label,
                "old_value": old_value,
                "new_value": new_value,
                "difference": difference,
                "percent_change": percent_change,
                "flagged": flagged,
            }
        )
    return rows


# --- R02: tax computation ---------------------------------------------------


def tax_computation_lines(session: Session, packet: Packet) -> list[dict[str, Any]]:
    rv = packet.return_versions[-1]
    adjustments = adjustments_by_claim(list_adjustments(session))
    return _line_rows(packet, rv, scope_lines(rv, "tax_computation"), adjustments)


# --- R03: area summaries -----------------------------------------------------


def area_summaries(session: Session, packet: Packet) -> list[dict[str, Any]]:
    rv = packet.return_versions[-1]
    adjustments = adjustments_by_claim(list_adjustments(session))
    budget_by_area = {row.area: row for row in time_budget_report(session, packet)}
    rows = []
    for area in AREAS:
        lines = scope_lines(rv, area)
        tie_outs = scope_tie_outs(packet, rv, area, adjustments)
        broken = [t for t in tie_outs if not t.ok]
        open_cases = [
            c
            for c in list_cases(session)
            if c.scope == area and c.status in _OPEN_CASE_STATUSES
        ]
        sign_off = get_latest_sign_off(session, area)
        budget = budget_by_area.get(area)
        rows.append(
            {
                "area": area,
                "line_count": len(lines),
                "tie_outs_ok": len(tie_outs) - len(broken),
                "tie_outs_broken": len(broken),
                "open_case_count": len(open_cases),
                "sign_off_version": sign_off.version if sign_off else None,
                "budget_hours": str(budget.budget_hours)
                if budget and budget.budget_hours is not None
                else None,
                "logged_hours": str(budget.logged_hours) if budget else "0",
            }
        )
    return rows


# --- R04: document index -----------------------------------------------------


def document_index(session: Session, packet: Packet) -> list[dict[str, Any]]:
    from proofline.analysis.disposition import propose_disposition

    rv = packet.return_versions[-1]
    rows = []
    for document in packet.documents:
        confirmed = get_document_disposition(session, document.id)
        proposal = propose_disposition(packet, rv, document.id)
        trace = trace_document(packet, document.id, version=rv.version)
        rows.append(
            {
                "id": document.id,
                "title": document.title,
                "document_type": document.document_type,
                "issuer": document.issuer,
                "received_at": document.received_at,
                "disposition": confirmed.disposition
                if confirmed
                else proposal.disposition,
                "extraction_status": document.extraction.status,
                "landed_in_count": len(trace.lines_using),
                "used": trace.used,
                "note": trace.note,
            }
        )
    return rows


# --- R05: depreciation by asset ---------------------------------------------


def depreciation_by_asset(packet: Packet) -> list[dict[str, Any]]:
    rv = packet.return_versions[-1]
    return [
        {
            "asset_id": asset.asset_id,
            "description": asset.description,
            "method": asset.method,
            "life_years": asset.life_years,
            "placed_in_service": asset.placed_in_service,
            "federal": asset.federal,
            "california": asset.california,
            "amt": asset.amt,
            "disposed": asset.disposed,
            "disposition": asset.disposition,
        }
        for asset in rv.assets
    ]


# --- R06: sales detail (Form 8949) ------------------------------------------


def sales_detail(session: Session, packet: Packet) -> list[dict[str, Any]]:
    """The Investments large-detail grouping already built in Step 7
    (`scope_detail_rows`), surfaced as its own report -- no new logic."""
    rv = packet.return_versions[-1]
    adjustments = adjustments_by_claim(list_adjustments(session))
    return scope_detail_rows(session, packet, rv, "investments", adjustments)


# --- R07: books to tax (Schedule C bridge) ----------------------------------


def books_to_tax_bridge(packet: Packet) -> dict[str, Any]:
    rv = packet.return_versions[-1]
    books_document = next(
        (d for d in packet.documents if d.document_type == "books_profit_loss"), None
    )
    books_lines = [
        {"field": v.field, "label": v.label, "value": v.value}
        for v in packet.extracted_values
        if books_document is not None and v.document_id == books_document.id
    ]
    net_income = next(
        (
            v.value
            for v in packet.extracted_values
            if books_document is not None
            and v.document_id == books_document.id
            and v.field == "net_income"
        ),
        None,
    )
    adjustment_lines = [
        {
            "line_key": line.key,
            "label": line.label,
            "value": line.value,
            "note": line.note,
        }
        for line in rv.lines
        if line.form == "SchC" and line.note
    ]
    schedule_c_net_profit = next(
        (line.value for line in rv.lines if line.key == "SchC.31"), None
    )
    return {
        "books_document_id": books_document.id if books_document else None,
        "books_lines": books_lines,
        "net_income_books": net_income,
        "schedule_c_net_profit": schedule_c_net_profit,
        "adjustments": adjustment_lines,
    }


# --- R08: rentals and passive losses -----------------------------------------


def rentals_and_passive_losses(packet: Packet) -> dict[str, Any]:
    rv = packet.return_versions[-1]
    prior_lines: dict[str, Any] = packet.prior_years.return_2024.get("lines", {})
    return {
        "schedule_e_lines": [
            {"line_key": l.key, "label": l.label, "value": l.value}
            for l in rv.lines
            if l.form == "SchE"
        ],
        "form_8582_lines": [
            {"line_key": l.key, "label": l.label, "value": l.value}
            for l in rv.lines
            if l.form == "F8582"
        ],
        "prior_year_unallowed": {
            key: value for key, value in prior_lines.items() if key.startswith("F8582.")
        },
        "carried_out": (
            rv.carryovers_out.get("federal", {}).get("passive_1450_fremont"),
            rv.carryovers_out.get("federal", {}).get("passive_1200_barton_hills"),
        ),
    }


# --- R09: K-1 lines ------------------------------------------------------------


def k1_lines(packet: Packet) -> list[dict[str, Any]]:
    """Every K-1 document's extracted boxes, each mapped to the return
    line(s) it feeds via the provenance resolver's own `line.sources` --
    never a hardcoded box-to-line table."""
    rv = packet.return_versions[-1]
    ev_to_lines: dict[str, list[str]] = {}
    for line in rv.lines:
        for ref in line.sources:
            if ref.startswith("ev-"):
                ev_to_lines.setdefault(ref, []).append(line.key)

    rows = []
    for document in packet.documents:
        if not document.document_type.startswith("K-1"):
            continue
        for value in packet.extracted_values:
            if value.document_id != document.id:
                continue
            rows.append(
                {
                    "document_id": document.id,
                    "document_title": document.title,
                    "field": value.field,
                    "label": value.label,
                    "value": value.value,
                    "feeds_lines": ev_to_lines.get(value.id, []),
                }
            )
    return rows


# --- R10: retirement and foreign items ---------------------------------------


def retirement_and_foreign_items(session: Session, packet: Packet) -> dict[str, Any]:
    rv = packet.return_versions[-1]
    fbar_status = next(
        (s for s in outside_filings_report(session, packet) if s.item == "fbar"), None
    )
    sep_line = next((l for l in rv.lines if l.key == "Sch1.16"), None)
    return {
        "form_8606_lines": [
            {"line_key": l.key, "label": l.label, "value": l.value}
            for l in rv.lines
            if l.form == "F8606"
        ],
        "form_8889_lines": [
            {"line_key": l.key, "label": l.label, "value": l.value}
            for l in rv.lines
            if l.form == "F8889"
        ],
        "form_8938_lines": [
            {"line_key": l.key, "label": l.label, "value": l.value}
            for l in rv.lines
            if l.form == "F8938"
        ],
        "sep_deduction": (
            {"line_key": sep_line.key, "label": sep_line.label, "value": sep_line.value}
            if sep_line
            else None
        ),
        "foreign_account_values": [
            {"field": v.field, "label": v.label, "value": v.value}
            for v in packet.extracted_values
            if v.field.endswith("_sek")
        ],
        "fx_rates": packet.fx_rates.SEK_per_USD,
        "fbar": (
            {"decided": fbar_status.decided, "decision": fbar_status.decision}
            if fbar_status
            else None
        ),
    }


# --- R11: deductions and credits with limits ----------------------------------


def deductions_and_credits(packet: Packet) -> dict[str, Any]:
    rv = packet.return_versions[-1]
    return {
        "schedule_a_lines": [
            {"line_key": l.key, "label": l.label, "value": l.value}
            for l in rv.lines
            if l.form == "SchA"
        ],
        "form_8283_lines": [
            {"line_key": l.key, "label": l.label, "value": l.value}
            for l in rv.lines
            if l.form == "F8283"
        ],
        "credit_lines": [
            {"line_key": l.key, "label": l.label, "value": l.value}
            for l in rv.lines
            if l.form == "F8812"
        ],
        "standard_deduction_param": packet.engine_reference.parameters.get(
            "std_deduction_mfj"
        ),
    }


# --- R12: payments -------------------------------------------------------------


def payments(packet: Packet) -> dict[str, Any]:
    """Reuses Step 8's estimated-payments tie-out, surfaced as its own
    report rather than a second computation."""
    rv = packet.return_versions[-1]
    federal_line = next((l for l in rv.lines if l.rule == "R-ESTIMATED-PAYMENTS"), None)
    california_line = next(
        (l for l in rv.lines if l.rule == "R-CA-ESTIMATED-PAYMENTS"), None
    )
    return {
        "federal_declared": federal_line.value if federal_line else None,
        "federal_posted": str(federal_estimated_payments_posted(packet)),
        "california_declared": california_line.value if california_line else None,
        "california_posted": str(california_estimated_payments_posted(packet)),
    }


# --- R13: state split -----------------------------------------------------------


def state_split(packet: Packet) -> dict[str, Any]:
    rv = packet.return_versions[-1]
    return {
        "residency": [
            {
                "state": r.state,
                "from": r.from_,
                "to": r.to,
                "status": r.status,
            }
            for r in packet.household.residency
        ],
        "lines": [
            {"line_key": l.key, "label": l.label, "form": l.form, "value": l.value}
            for l in rv.lines
            if l.jurisdiction == "california"
        ],
    }


# --- R14: carryovers ------------------------------------------------------------


def carryovers(packet: Packet) -> dict[str, Any]:
    rv = packet.return_versions[-1]
    return {
        "in_from_2024": packet.prior_years.carryovers_into_2025,
        "out_to_2026": rv.carryovers_out,
    }


# --- R15: basis by year ----------------------------------------------------------


def basis_by_year(packet: Packet) -> dict[str, Any]:
    """A gap in the prior-year file (a null ending balance) is returned as
    `None`, exactly as the packet itself records it -- never guessed."""
    records = packet.prior_years.basis_records
    return {
        "scorp_stock_basis": records.get("scorp_lindqvist_family_woodworks", []),
        "partnership_capital": records.get("partnership_ridgeline", []),
        "ira_basis": records.get("ira_nondeductible_basis_ngozi", []),
        "home_cost": records.get("home_7709_barton_ridge", []),
    }


# --- R16: prior preparer vs. what we changed -------------------------------------


def _word_overlap(a: str, b: str) -> int:
    import re

    words_a = set(re.findall(r"[a-z]+", a.lower()))
    words_b = set(re.findall(r"[a-z]+", b.lower()))
    return len(words_a & words_b)


def prior_preparer_items(session: Session, packet: Packet) -> list[dict[str, Any]]:
    open_items: list[str] = packet.prior_years.prior_preparer_workpaper.get(
        "open_items_left_by_prior_preparer", []
    )
    judgments = list_judgments(session)
    outside = outside_filings_report(session, packet)

    rows = []
    for text in open_items:
        matched_judgment = max(
            judgments,
            key=lambda j: _word_overlap(text, j.reasoning or ""),
            default=None,
        )
        judgment_overlap = (
            _word_overlap(text, matched_judgment.reasoning or "")
            if matched_judgment
            else 0
        )
        matched_outside = max(
            outside, key=lambda s: _word_overlap(text, s.note), default=None
        )
        outside_overlap = (
            _word_overlap(text, matched_outside.note) if matched_outside else 0
        )

        addressed_by_judgment = matched_judgment.id if judgment_overlap >= 2 else None
        addressed_by_outside = (
            matched_outside.item
            if outside_overlap >= 2 and matched_outside.decided
            else None
        )
        rows.append(
            {
                "open_item": text,
                "addressed_by_judgment": addressed_by_judgment,
                "addressed_by_outside_filing": addressed_by_outside,
                "status": "addressed"
                if (addressed_by_judgment or addressed_by_outside)
                else "open",
            }
        )
    return rows
