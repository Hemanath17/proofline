"""The claim identity table from docs/CONTRACTS.md, as functions.

Each function returns a ClaimIdentity with a canonical string .key, which is
what CheckResult.claims carries. A claim is identified by the thing itself,
never by where it sits on the return (CONTRACTS.md "Claim identity").

One adaptation from the contract: a 1099-B lot's identity there is
"issuer + account + lot id", but the packet has no structured per-document
account field (account numbers, where printed at all, are inside free-text
printed_content). So lot_1099b keys on issuer + lot id, falling back to
issuer + security + acquired + sold + quantity when there's no lot id,
exactly as the contract already specifies for that case. A correction from
the same issuer (same account, by construction) keeps the same key even
when the lot moves boxes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClaimIdentity:
    key: str

    def __str__(self) -> str:
        return self.key


def household_fact(person_id: str, field: str) -> ClaimIdentity:
    return ClaimIdentity(f"household:{person_id}:{field}")


def w2_box(
    employer_ein: str, employee_id: str, tax_year: int, box: str
) -> ClaimIdentity:
    return ClaimIdentity(f"w2_box:{employer_ein}:{employee_id}:{tax_year}:{box}")


def lot_1099b(
    issuer: str,
    lot_id: str | None = None,
    *,
    security: str | None = None,
    acquired: str | None = None,
    sold: str | None = None,
    quantity: str | None = None,
) -> ClaimIdentity:
    if lot_id:
        return ClaimIdentity(f"1099b_lot:{issuer}:{lot_id}")
    if security is None or acquired is None or sold is None or quantity is None:
        raise ValueError(
            "a 1099-B lot needs either lot_id or security+acquired+sold+quantity"
        )
    return ClaimIdentity(f"1099b_lot:{issuer}:{security}:{acquired}:{sold}:{quantity}")


def digital_asset_lot(broker: str, lot_id: str) -> ClaimIdentity:
    return ClaimIdentity(f"digital_asset_lot:{broker}:{lot_id}")


def form_amount(payer: str, recipient: str, box: str) -> ClaimIdentity:
    return ClaimIdentity(f"form_amount:{payer}:{recipient}:{box}")


def k1_item(
    entity_ein: str, partner_or_shareholder: str, box_code: str
) -> ClaimIdentity:
    return ClaimIdentity(f"k1_item:{entity_ein}:{partner_or_shareholder}:{box_code}")


def depreciation_asset(asset_id: str) -> ClaimIdentity:
    return ClaimIdentity(f"asset:{asset_id}")


def rental_line(property_id: str, line: str) -> ClaimIdentity:
    return ClaimIdentity(f"rental_line:{property_id}:{line}")


def carryover(name: str) -> ClaimIdentity:
    return ClaimIdentity(f"carryover:{name}")


def return_total(line_key: str) -> ClaimIdentity:
    return ClaimIdentity(line_key)
