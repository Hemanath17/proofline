import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from proofline.actions.errors import ActionConflict, ActionValidationError
from proofline.db.connection import DatabaseUnavailable
from proofline.db.repository import EntityNotFound, StaleRevision
from proofline.packet import load_packet
from proofline.routes import (
    actors,
    areas,
    cases,
    checks,
    documents,
    filing,
    health,
    household,
    readiness,
    return_info,
    reveal,
    review_notes,
    trace,
)
from proofline.security.permissions import PermissionDenied
from proofline.security.redact import install_logging_filter, redact_for_actor

logger = logging.getLogger(__name__)

app = FastAPI(title="Proofline API")

app.include_router(health.router, prefix="/api")
app.include_router(household.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(trace.router, prefix="/api")
app.include_router(checks.router, prefix="/api")
app.include_router(review_notes.router, prefix="/api")
app.include_router(reveal.router, prefix="/api")
app.include_router(actors.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(return_info.router, prefix="/api")
app.include_router(areas.router, prefix="/api")
app.include_router(readiness.router, prefix="/api")
app.include_router(filing.router, prefix="/api")

install_logging_filter()


async def _database_unreachable(request: Request, exc: Exception) -> JSONResponse:
    """One handler for every way "the database isn't reachable" can surface
    -- a missing DATABASE_URL (DatabaseUnavailable) or a real connection
    failure (SQLAlchemy's OperationalError) -- so no route needs its own
    try/except, and a failure while resolving a dependency (before a
    route's own code even runs) still gets this response instead of a bare
    500. The driver's exception can carry hostnames or database names; it's
    logged here, never returned."""
    logger.error("Database unreachable", exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "database unreachable"})


async def _permission_denied(request: Request, exc: PermissionDenied) -> JSONResponse:
    """A 403 that names the rule (CONTRACTS.md, acceptance test I3)."""
    return JSONResponse(status_code=403, content={"detail": exc.rule})


def _conflict_response(
    request: Request, detail: str, current: dict[str, Any] | None
) -> JSONResponse:
    """Shared by both 409 cases below: a stale revision and a status
    conflict differ in *why* the write was refused, but both carry the
    entity's current state, redacted for whichever actor asked (the actor
    is read from `request.state`, stashed there by
    `proofline.security.dependencies.get_current_actor`, since a
    dependency's return value isn't otherwise reachable from a handler).

    `current` must already be a plain dict (or `None`) by the time it
    gets here -- `StaleRevision`/`ActionConflict` only ever carry one,
    captured by the raise site while its session was still open. This
    handler runs after that session has closed (the request's `finally`
    already ran), so touching an ORM row here instead would raise
    `DetachedInstanceError` and turn every 409 into a bare 500 -- exactly
    what happened before this was fixed, confirmed over HTTP against real
    Postgres under two racing responses at the same revision."""
    body: dict[str, Any] = {"detail": detail}
    if current is not None:
        body["current_state"] = current
    actor = getattr(request.state, "actor", None)
    if actor is not None:
        body = redact_for_actor(actor, load_packet(), body)
    return JSONResponse(status_code=409, content=body)


async def _stale_revision(request: Request, exc: StaleRevision) -> JSONResponse:
    """Acceptance test I2: a stale revision gets a 409 with the current
    state."""
    return _conflict_response(request, "stale revision", exc.current)


async def _action_conflict(request: Request, exc: ActionConflict) -> JSONResponse:
    """A 409 for a refusal based on the entity's own state, not a stale
    revision -- e.g. responding to an already-resolved review note."""
    return _conflict_response(request, exc.detail, exc.current)


async def _entity_not_found(request: Request, exc: EntityNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "not found"})


async def _action_validation_error(
    request: Request, exc: ActionValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.detail})


app.add_exception_handler(DatabaseUnavailable, _database_unreachable)
app.add_exception_handler(OperationalError, _database_unreachable)
app.add_exception_handler(PermissionDenied, _permission_denied)
app.add_exception_handler(StaleRevision, _stale_revision)
app.add_exception_handler(ActionConflict, _action_conflict)
app.add_exception_handler(EntityNotFound, _entity_not_found)
app.add_exception_handler(ActionValidationError, _action_validation_error)
