"""Shared ways to turn a packet value into money or a plain yes/no, so every
check reads these the same way instead of each guessing at the extraction
pipeline's exact output type.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_STRIP_RE = re.compile(r"[,$\s]")
_PARENS_RE = re.compile(r"^\((.*)\)$")
_TRUE_STRINGS = {"true", "yes", "y", "1"}
_FALSE_STRINGS = {"false", "no", "n", "0"}


def parse_money(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        # bool is a subclass of int, so this must come before the int/float
        # check below -- otherwise Decimal(str(True)) raises
        # decimal.InvalidOperation. ValueError (not TypeError) to match
        # every other "not a money value" case below.
        raise ValueError(f"not a money value: {value!r}")  # noqa: TRY004
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        negative = False
        parens = _PARENS_RE.match(text)
        if parens:
            negative = True
            text = parens.group(1)
        if text.startswith("-"):
            negative = True
            text = text[1:]
        text = _STRIP_RE.sub("", text)
        try:
            amount = Decimal(text)
        except InvalidOperation:
            raise ValueError(f"not a money value: {value!r}") from None
        return -amount if negative else amount
    raise ValueError(f"not a money value: {value!r}")


def parse_bool(value: Any) -> bool | None:
    """True/False from a real bool, a 0/1 number, or printed text
    ("Yes"/"No", "True"/"False", case-insensitive). Returns None -- not an
    exception -- when the value can't be confidently read as either, so a
    caller can treat an unrecognized value (and a missing one) as "unknown"
    rather than silently guessing False."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE_STRINGS:
            return True
        if text in _FALSE_STRINGS:
            return False
    return None
