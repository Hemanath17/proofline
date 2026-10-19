"""Who can act, for the frontend's "Demo role switcher" (docs/UX.md Top
bar). Staff names and roles aren't sensitive data -- no redaction needed
here, unlike every route that touches the household or documents.
"""

from __future__ import annotations

from fastapi import APIRouter

from proofline.packet import load_packet
from proofline.security.actors import load_actors

router = APIRouter()


@router.get("/actors")
def list_actors() -> dict:
    actors = load_actors(load_packet())
    return {
        "actors": [
            {
                "id": actor.id,
                "name": actor.name,
                "role": actor.role,
                "clearance": actor.clearance,
            }
            for actor in actors.values()
        ]
    }
