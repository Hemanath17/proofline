"""Masks every sensitive value in anything that leaves the API: normal
responses, 409 bodies, error messages, document text, and log lines
(CONTRACTS.md Redaction; acceptance test I4).

Sensitive values: SSNs and ITINs, bank and account numbers (IBANs too), IP
PINs and e-file signature PINs (CONTRACTS.md). `collect_sensitive_values`
gathers every one the packet actually contains; a regex backstop then
catches anything SSN- or account-shaped that isn't on that list, in case a
future document introduces a sensitive value we haven't cataloged.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from proofline.packet import Packet, load_packet
from proofline.security.actors import Actor

_PIN_CONTEXT_RE = re.compile(r"(?i)\bPIN\b[^.\n]{0,20}?(\d{4,6})")
_SSN_SHAPE_RE = re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")
_ACCOUNT_CONTEXT_RE = re.compile(
    r"(?i)\b(?:account|routing|iban|acct)\w*\b[^.\n]{0,24}?(\d[\d ]{5,24}\d)"
)


@dataclass(frozen=True)
class SensitiveValue:
    value: str
    category: str


def collect_sensitive_values(packet: Packet) -> list[SensitiveValue]:
    """Every sensitive value the packet is known to contain: household
    SSNs and IP PINs, the refund/payment bank account and routing numbers,
    every extracted value typed `ssn` or `account_number` (this is how
    corrected documents' SSN variants are caught too, without needing a
    separate scan of prior-year records), and the e-file signature PINs
    pulled out of free-text timeline entries (e.g. tl-20).
    """
    values: list[SensitiveValue] = []
    for person in packet.household.people:
        values.append(SensitiveValue(person.ssn, "ssn"))
        if person.ip_pin:
            values.append(SensitiveValue(person.ip_pin, "ip_pin"))
    bank = packet.household.bank_account_for_refund_or_payment
    if bank is not None:
        values.append(SensitiveValue(bank.account, "bank_account"))
        values.append(SensitiveValue(bank.routing, "bank_account"))
    for extracted in packet.extracted_values:
        if extracted.value_type in ("ssn", "account_number") and extracted.value:
            values.append(SensitiveValue(str(extracted.value), extracted.value_type))
    for event in packet.timeline:
        if not event.detail:
            continue
        for match in _PIN_CONTEXT_RE.finditer(event.detail):
            values.append(SensitiveValue(match.group(1), "efile_pin"))
    return values


def generate_variants(value: str) -> set[str]:
    """Dash / space / no-separator forms of `value`, so a reformatted
    occurrence of the same value still gets matched and masked."""
    variants = {value}
    stripped = re.sub(r"[\s-]", "", value)
    variants.add(stripped)
    if stripped.isdigit():
        if len(stripped) == 9:
            variants.add(f"{stripped[:3]}-{stripped[3:5]}-{stripped[5:]}")
            variants.add(f"{stripped[:3]} {stripped[3:5]} {stripped[5:]}")
        else:
            variants.add(
                " ".join(stripped[i : i + 4] for i in range(0, len(stripped), 4))
            )
    return variants


def mask(value: str) -> str:
    """Keeps the last four significant (alphanumeric) characters, masking
    every earlier one with `*` and leaving separators where they are --
    e.g. `666-74-3390` -> `***-**-3390`."""
    alnum_positions = [index for index, char in enumerate(value) if char.isalnum()]
    keep_from = len(alnum_positions) - 4
    masked = list(value)
    for rank, position in enumerate(alnum_positions):
        if rank < keep_from:
            masked[position] = "*"
    return "".join(masked)


def _mask_captured_group(match: re.Match[str]) -> str:
    full, digits = match.group(0), match.group(1)
    return full.replace(digits, mask(digits))


def redact_text(text: str, sensitive_values: list[SensitiveValue]) -> str:
    """Exact substring replace (every known value, every variant, longest
    first so a longer variant isn't partly consumed by a shorter one)
    followed by the regex backstop for anything SSN- or account/PIN-shaped
    that isn't already on the known-value list."""
    if not text:
        return text
    replacements: dict[str, str] = {}
    for sensitive_value in sensitive_values:
        masked = mask(sensitive_value.value)
        for variant in generate_variants(sensitive_value.value):
            if variant:
                replacements[variant] = masked
    for variant in sorted(replacements, key=len, reverse=True):
        if variant in text:
            text = text.replace(variant, replacements[variant])
    text = _SSN_SHAPE_RE.sub(lambda m: mask(m.group(0)), text)
    text = _PIN_CONTEXT_RE.sub(_mask_captured_group, text)
    text = _ACCOUNT_CONTEXT_RE.sub(_mask_captured_group, text)
    return text


def redact_json(data: Any, sensitive_values: list[SensitiveValue]) -> Any:
    """Recursively redacts every string leaf of a dict/list structure."""
    if isinstance(data, str):
        return redact_text(data, sensitive_values)
    if isinstance(data, dict):
        return {
            key: redact_json(value, sensitive_values) for key, value in data.items()
        }
    if isinstance(data, list):
        return [redact_json(item, sensitive_values) for item in data]
    return data


def redact_for_actor(actor: Actor, packet: Packet, data: Any) -> Any:
    """`data` unchanged for a cleared actor; fully redacted otherwise.
    Used for normal responses, 409 bodies and error details alike."""
    if actor.clearance:
        return data
    return redact_json(data, collect_sensitive_values(packet))


def values_present_in(
    text: str, sensitive_values: list[SensitiveValue]
) -> list[SensitiveValue]:
    """Which of `sensitive_values` actually occur (in any variant) in
    `text` -- used to decide whether showing a cleared actor this text
    unmasked counts as revealing something, and so needs a view-log event.
    """
    found = []
    for sensitive_value in sensitive_values:
        if any(variant in text for variant in generate_variants(sensitive_value.value)):
            found.append(sensitive_value)
    return found


class RedactingLogFilter(logging.Filter):
    """Masks sensitive values in every log record, regardless of who's
    asking -- logs aren't actor-scoped, so there's no "cleared" case here
    (CLAUDE.md: never log a sensitive value)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 -- logging must never itself raise
            return True
        record.msg = redact_text(message, collect_sensitive_values(load_packet()))
        record.args = ()
        return True


def install_logging_filter(logger: logging.Logger | None = None) -> None:
    (logger or logging.getLogger()).addFilter(RedactingLogFilter())
