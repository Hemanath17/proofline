from __future__ import annotations

from fastapi import APIRouter, Depends

from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor
from proofline.security.redact import redact_for_actor

router = APIRouter()


@router.get("/household")
def get_household(actor: Actor = Depends(get_current_actor)) -> dict:
    packet = load_packet()
    data = packet.household.model_dump(mode="json")
    return redact_for_actor(actor, packet, data)
