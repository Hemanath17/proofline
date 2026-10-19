"""Exceptions an action handler raises for a malformed request -- distinct
from `proofline.security.permissions.PermissionDenied` (403) and
`proofline.db.repository.StaleRevision`/`EntityNotFound` (409/404)."""

from __future__ import annotations

from typing import Any


class ActionValidationError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def require(payload: dict[str, Any], key: str) -> Any:
    """Returns `payload[key]`, raising `ActionValidationError` if it's
    missing or blank. Shared by every action with a required free-text
    field: a review note's `body`/`resolution`, a reveal's `reason`."""
    value = payload.get(key)
    if value in (None, ""):
        raise ActionValidationError(f"{key} is required")
    return value


class ActionConflict(Exception):
    """Raised when an action is refused not because of a stale revision or
    an unknown entity, but because the entity's own current state
    conflicts with what the action means -- e.g. responding to a review
    note that's already been resolved. Distinct from
    `proofline.db.repository.StaleRevision`: that's about a caller acting
    on an outdated revision number; this is about the entity being in a
    state the action never makes sense against, regardless of revision.
    Carries `current` (the entity's current state, same as `StaleRevision`)
    so the 409 can show it, redacted."""

    def __init__(self, detail: str, current: Any):
        self.detail = detail
        self.current = current
        super().__init__(detail)
