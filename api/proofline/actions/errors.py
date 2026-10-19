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
    field: a review note's `body`/`resolution`, a reveal's `reason`.
    Whitespace-only ("   ") is rejected the same as empty -- checked
    against the stripped value, but the original (unstripped) value is
    still what's returned and stored, so this only closes the blank-looking
    loophole without otherwise changing what callers get back."""
    value = payload.get(key)
    check_value = value.strip() if isinstance(value, str) else value
    if check_value in (None, ""):
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
    Carries `current` as a plain dict or `None` -- the caller must capture
    it (e.g. `case.to_dict()`) while the session is still open, never pass
    the ORM row itself, which would raise `DetachedInstanceError` once the
    request's session closes, turning this into a bare 500 instead of the
    409 it's supposed to be (confirmed over HTTP against real Postgres)."""

    def __init__(self, detail: str, current: dict[str, Any] | None):
        self.detail = detail
        self.current = current
        super().__init__(detail)
