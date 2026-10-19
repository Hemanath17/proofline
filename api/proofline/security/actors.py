"""Who can act. An `Actor` is built fresh from the packet's firm data on
every request (there's no actor table -- `firm.staff` and
`firm.client_users` already are the source of truth), plus one synthetic
`ai_assistant` actor that isn't in the packet at all (CLAUDE.md: "The AI is
a user with its own role").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from proofline.packet import Packet, Person

Role = Literal[
    "preparer",
    "reviewer",
    "partner",
    "firm_administrator",
    "quality_reviewer",
    "client",
    "ai_assistant",
    # Step 5: a synthetic actor for transitions CONTRACTS.md C1 marks
    # "System" (e.g. a case clearing because its finding stopped firing) --
    # never built from the packet, never staff, never returned by
    # `load_actors`.
    "system",
]

STAFF_ROLES: frozenset[Role] = frozenset(
    {"preparer", "reviewer", "partner", "firm_administrator", "quality_reviewer"}
)

AI_ASSISTANT_ID = "ai-assistant"


@dataclass(frozen=True)
class Actor:
    id: str
    name: str
    role: Role
    clearance: bool
    household_person_id: str | None = None

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES


def _match_household_person(name: str, people: list[Person]) -> Person | None:
    """Matches a client user to the household person with the same name.
    The packet has no field linking `firm.client_users` to
    `household.people` directly, so this is the general rule that stands in
    for one: exact match first, falling back to a case-insensitive
    comparison so a client packet with different capitalization still
    links correctly, rather than hardcoding either person's id."""
    for person in people:
        if person.name == name:
            return person
    lowered = name.lower()
    for person in people:
        if person.name.lower() == lowered:
            return person
    return None


def load_actors(packet: Packet) -> dict[str, Actor]:
    """Every actor who can call the API: the firm's staff (clearance from
    `sensitive_data_clearance`), the client users (never cleared -- clients
    see the same masked values as Marcus and the AI assistant until the
    client workspace, Step 9, decides otherwise), and the AI assistant
    (read/propose only, built nowhere but here until Step 10)."""
    actors: dict[str, Actor] = {}
    for staff in packet.firm.staff:
        actors[staff.id] = Actor(
            id=staff.id,
            name=staff.name,
            role=staff.role,  # type: ignore[arg-type]
            clearance=staff.sensitive_data_clearance,
        )
    for client_user in packet.firm.client_users:
        person = _match_household_person(client_user.name, packet.household.people)
        actors[client_user.id] = Actor(
            id=client_user.id,
            name=client_user.name,
            role="client",
            clearance=False,
            household_person_id=person.id if person is not None else None,
        )
    actors[AI_ASSISTANT_ID] = Actor(
        id=AI_ASSISTANT_ID, name="AI assistant", role="ai_assistant", clearance=False
    )
    return actors
