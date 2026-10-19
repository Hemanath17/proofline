from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from proofline.db.models import Event


@dataclass
class ActionResult:
    event: Event
    current_state: Any | None
