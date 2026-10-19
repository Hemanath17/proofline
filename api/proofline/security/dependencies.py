"""`get_current_actor` is a DEMO ROLE SWITCHER, not authentication. It
trusts whatever actor id the caller names in the `X-Proofline-Actor`
header -- there's no password, no session, no signature. It exists so the
prototype (and `/simulate`) can act as any staff member, client or the AI
assistant without building real sign-in, and every place it's used must
say so, in code and in docs.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request

from proofline.packet import load_packet
from proofline.security.actors import Actor, load_actors

ACTOR_HEADER = "X-Proofline-Actor"


def get_current_actor(
    request: Request,
    x_proofline_actor: str | None = Header(default=None, alias=ACTOR_HEADER),
) -> Actor:
    if x_proofline_actor is None:
        raise HTTPException(
            status_code=401,
            detail=f"missing {ACTOR_HEADER} header (demo role switcher, not auth)",
        )
    actors = load_actors(load_packet())
    actor = actors.get(x_proofline_actor)
    if actor is None:
        raise HTTPException(status_code=401, detail="unknown actor")
    # Stashed so an exception handler further out (e.g. the 409 handler for
    # a stale revision) can redact its response body for this same actor
    # without re-deriving it -- FastAPI dependency results aren't otherwise
    # reachable from an exception handler.
    request.state.actor = actor
    return actor
