"""A little metadata for the top bar (docs/UX.md: "return name, engine
version badge, ... the current return and 'as of' date"). Not sensitive on
its own, but goes through the same redaction as everything else for
consistency.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor
from proofline.security.redact import redact_for_actor

router = APIRouter()


@router.get("/return")
def get_return_info(actor: Actor = Depends(get_current_actor)) -> dict:
    packet = load_packet()
    current = packet.return_versions[-1]
    taxpayer_names = [
        person.name
        for person in packet.household.people
        if person.role in ("taxpayer", "spouse")
    ]
    body = {
        "household_names": taxpayer_names,
        "tax_year": packet.household.tax_year,
        "engine_version": current.version,
        "computed_at": current.computed_at,
    }
    return redact_for_actor(actor, packet, body)
