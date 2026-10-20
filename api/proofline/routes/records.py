"""The sixteen CPA record views (R01-R16, docs/PLAN.md Step 9) -- one GET
per view, each a thin read over `proofline/analysis/records.py`. Staff +
AI assistant only, like every other staff-surface read.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from proofline.analysis import records as records_analysis
from proofline.db.connection import get_session
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter(prefix="/records")


@router.get("/return-summary")
def get_r01(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    body = {"rows": records_analysis.return_summary_vs_last_year(session, packet)}
    return redact_for_actor(actor, packet, body)


@router.get("/tax-computation")
def get_r02(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    body = {"rows": records_analysis.tax_computation_lines(session, packet)}
    return redact_for_actor(actor, packet, body)


@router.get("/area-summaries")
def get_r03(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    body = {"rows": records_analysis.area_summaries(session, packet)}
    return redact_for_actor(actor, packet, body)


@router.get("/documents")
def get_r04(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    body = {"rows": records_analysis.document_index(session, packet)}
    return redact_for_actor(actor, packet, body)


@router.get("/depreciation")
def get_r05(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    body = {"rows": records_analysis.depreciation_by_asset(packet)}
    return redact_for_actor(actor, packet, body)


@router.get("/sales-detail")
def get_r06(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    body = {"rows": records_analysis.sales_detail(session, packet)}
    return redact_for_actor(actor, packet, body)


@router.get("/books-to-tax")
def get_r07(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    return redact_for_actor(actor, packet, records_analysis.books_to_tax_bridge(packet))


@router.get("/rentals-passive")
def get_r08(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    return redact_for_actor(
        actor, packet, records_analysis.rentals_and_passive_losses(packet)
    )


@router.get("/k1-lines")
def get_r09(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    body = {"rows": records_analysis.k1_lines(packet)}
    return redact_for_actor(actor, packet, body)


@router.get("/retirement-foreign")
def get_r10(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    return redact_for_actor(
        actor, packet, records_analysis.retirement_and_foreign_items(session, packet)
    )


@router.get("/deductions-credits")
def get_r11(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    return redact_for_actor(
        actor, packet, records_analysis.deductions_and_credits(packet)
    )


@router.get("/payments")
def get_r12(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    return redact_for_actor(actor, packet, records_analysis.payments(packet))


@router.get("/state-split")
def get_r13(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    return redact_for_actor(actor, packet, records_analysis.state_split(packet))


@router.get("/carryovers")
def get_r14(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    return redact_for_actor(actor, packet, records_analysis.carryovers(packet))


@router.get("/basis")
def get_r15(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    return redact_for_actor(actor, packet, records_analysis.basis_by_year(packet))


@router.get("/prior-preparer")
def get_r16(
    actor: Actor = Depends(require_non_client), session: Session = Depends(get_session)
) -> dict:
    packet = load_packet()
    body = {"rows": records_analysis.prior_preparer_items(session, packet)}
    return redact_for_actor(actor, packet, body)
