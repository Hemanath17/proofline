"""One shared way to turn a packet value into money. Every check should read
an amount through `parse_money` rather than calling `Decimal(str(x))`
directly, so `None`, a float, and a printed string like "71,965.00" or
"$1,234.50" (cents sometimes omitted) are all handled the same way, once.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_STRIP_RE = re.compile(r"[,$\s]")
_PARENS_RE = re.compile(r"^\((.*)\)$")


def parse_money(value: Any) -> Decimal | None:
    if value is None:
        return None
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
