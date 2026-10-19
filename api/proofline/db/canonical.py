"""Canonical JSON for event payloads and check-run findings.

Postgres's JSONB storage reorders object keys, so anything hashed from a
stored payload must be recomputed from a canonical form (sorted keys, no
duplicates), never from however the payload happened to be read back.
`Decimal` isn't JSON-serializable by Python's default encoder, so every
payload is walked and its `Decimal` values turned into strings before it
ever reaches a JSON column -- this is the one place that conversion
happens, used by every caller through `prepare_payload_for_storage`.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any


def _convert_decimals(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _convert_decimals(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_convert_decimals(item) for item in value]
    return value


def prepare_payload_for_storage(payload: dict) -> dict:
    """Recursively converts every `Decimal` in `payload` to a string.

    Money inside an event payload must already be a string by the time it's
    written (per CONTRACTS.md Storage), but callers build payloads out of
    domain objects that naturally carry `Decimal`. Converting here, in one
    place, means no caller has to remember to do it, and a `Decimal` can
    never reach the JSON column and crash the save.
    """
    return _convert_decimals(payload)


def to_canonical_json(payload: dict) -> str:
    """Sorted keys, no extra whitespace, every `Decimal` already a string.

    This is the form anything hashed from a payload must be computed from --
    never the order JSONB happens to return keys in.
    """
    converted = _convert_decimals(payload)
    return json.dumps(converted, sort_keys=True, separators=(",", ":"))


def canonical_hash(payload: dict) -> str:
    """sha256 hex digest of `to_canonical_json(payload)`."""
    return hashlib.sha256(to_canonical_json(payload).encode("utf-8")).hexdigest()
