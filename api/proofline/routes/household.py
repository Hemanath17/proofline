from __future__ import annotations

from fastapi import APIRouter, Depends

from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter()


@router.get("/household")
def get_household(actor: Actor = Depends(require_non_client)) -> dict:
    packet = load_packet()
    data = packet.household.model_dump(mode="json")
    return redact_for_actor(actor, packet, data)
