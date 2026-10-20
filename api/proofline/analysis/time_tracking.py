"""B37: time logged against the packet's own per-area budget
(`firm.budget_hours`). Log-only, like `proofline.actions.sign_offs.
confirm_carryover` -- a time entry is a fact nobody edits or CASes
against, read back by replaying its own events, never stored as a second
current-state table.

`firm.budget_hours` uses the packet's own area keys (e.g.
"investments_and_digital_assets"), not the engine's `Area` literal
(e.g. "investments") -- `AREA_TO_BUDGET_KEY` is the one place that maps
between them, domain knowledge about this firm's naming, not a packet
value.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from proofline.checks.models import Area
from proofline.checks.money import parse_money
from proofline.db.repository import list_events_by_type
from proofline.packet import Packet

AREA_TO_BUDGET_KEY: dict[Area, str] = {
    "identity": "intake_and_engagement",
    "wages": "wages_and_stock_compensation",
    "investments": "investments_and_digital_assets",
    "business": "business",
    "rentals": "rentals_and_sale",
    "pass_throughs": "pass_throughs_and_basis",
    "deductions_credits": "deductions_and_credits",
    "california": "california",
    "tax_computation": "partner_review",
}


@dataclass(frozen=True)
class TimeEntry:
    event_id: str
    actor_id: str | None
    area: str
    hours: Decimal
    date: str
    note: str | None


def list_time_entries(session: Session) -> list[TimeEntry]:
    entries = []
    for event in list_events_by_type(session, "time_logged"):
        hours = parse_money(event.payload.get("hours")) or Decimal(0)
        entries.append(
            TimeEntry(
                event_id=str(event.id),
                actor_id=event.actor_id,
                area=event.payload.get("area"),
                hours=hours,
                date=event.payload.get("date"),
                note=event.payload.get("note"),
            )
        )
    return entries


def hours_logged_by_area(session: Session) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for entry in list_time_entries(session):
        totals[entry.area] = totals.get(entry.area, Decimal(0)) + entry.hours
    return totals


@dataclass(frozen=True)
class AreaTimeBudget:
    area: str
    budget_hours: Decimal | None
    logged_hours: Decimal
    over_budget: bool


def time_budget_report(session: Session, packet: Packet) -> list[AreaTimeBudget]:
    logged = hours_logged_by_area(session)
    report = []
    for area, budget_key in AREA_TO_BUDGET_KEY.items():
        budget = packet.firm.budget_hours.get(budget_key)
        area_logged = logged.get(area, Decimal(0))
        report.append(
            AreaTimeBudget(
                area=area,
                budget_hours=budget,
                logged_hours=area_logged,
                over_budget=budget is not None and area_logged > budget,
            )
        )
    return report
