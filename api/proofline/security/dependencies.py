"""`get_current_actor` is a DEMO ROLE SWITCHER, not authentication. It
trusts whatever actor id the caller names in the `X-Proofline-Actor`
header -- there's no password, no session, no signature. It exists so the
prototype (and `/simulate`) can act as any staff member, client or the AI
assistant without building real sign-in, and every place it's used must
say so, in code and in docs.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request

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


def require_non_client(actor: Actor = Depends(get_current_actor)) -> Actor:
    """Step 9 (S5): the staff surface (areas, cases, documents, trace,
    readiness, review notes, checks, filing status) is not for a client --
    "not the staff UI with fewer buttons, a genuinely smaller API surface."
    The AI assistant keeps read access here (CONTRACTS.md: "the AI... can
    read"), so this blocks only `client`, never every non-staff role."""
    if actor.role == "client":
        raise HTTPException(
            status_code=403,
            detail="clients use the client workspace (/api/client/*), not this endpoint",
        )
    return actor


def require_client(actor: Actor = Depends(get_current_actor)) -> Actor:
    """The reverse guard, for the new `/api/client/*` surface itself --
    staff and the AI assistant have their own full surface already."""
    if actor.role != "client":
        raise HTTPException(
            status_code=403,
            detail="the client workspace is for the client role only",
        )
    return actor
