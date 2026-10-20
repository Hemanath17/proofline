"""Part G: the Form 8867 due-diligence checklist, as data. The packet
itself has no itemized checklist (no structured list of items anywhere) --
only the firm's own written rule naming which credits need it
(`firm.starter_standards.rules`) and the engine's own `F8867.status` line.
Both are read generically (by scanning rule text / matching the line key),
never hardcoded as a client-specific answer.

This checklist's "done" status is the *existing* `due_diligence_done`
readiness attestation (Step 8) -- CLAUDE.md: don't build a second,
competing notion of done.
"""

from __future__ import annotations

from typing import Any

from proofline.packet import Packet


def due_diligence_checklist(packet: Packet) -> list[dict[str, Any]]:
    rv = packet.return_versions[-1]
    items: list[dict[str, Any]] = []

    rule = next(
        (
            r
            for r in packet.firm.starter_standards.rules
            if "due diligence" in r.lower()
        ),
        None,
    )
    if rule is not None:
        items.append({"item": "credits_due_diligence", "description": rule})

    status_line = next((line for line in rv.lines if line.key == "F8867.status"), None)
    if status_line is not None:
        items.append(
            {
                "item": "f8867_status",
                "description": f"{status_line.label}: {status_line.value}",
                "line_key": status_line.key,
            }
        )

    return items
