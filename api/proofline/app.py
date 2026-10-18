import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from proofline.db.connection import DatabaseUnavailable
from proofline.routes import events, health

logger = logging.getLogger(__name__)

app = FastAPI(title="Proofline API")

app.include_router(health.router, prefix="/api")
app.include_router(events.router, prefix="/api")


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


app.add_exception_handler(DatabaseUnavailable, _database_unreachable)
app.add_exception_handler(OperationalError, _database_unreachable)
