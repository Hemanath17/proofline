import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Engine

from proofline.db.connection import check_connection, get_engine

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
def health(engine: Engine = Depends(get_engine)) -> dict[str, str]:
    try:
        check_connection(engine)
    except Exception as exc:
        # The driver's exception can carry hostnames, database names or
        # other connection details -- log it for whoever's debugging, but
        # never put it in the response, which is unauthenticated.
        logger.error("Health check failed: database unreachable", exc_info=exc)
        raise HTTPException(status_code=503, detail="database unreachable") from exc
    return {"status": "ok"}
