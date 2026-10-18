"""Resolves every packet reference format into the object it points at.

One resolver per format, dispatched by pattern. Every format raises
UnresolvedReferenceError on a miss rather than returning None, so a caller
walking a list of references can't silently swallow a bad one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from proofline.packet import Packet


class UnresolvedReferenceError(LookupError):
    pass


@dataclass(frozen=True)
class Resolved:
    ref: str
    kind: str
    value: Any


_EV_RE = re.compile(r"^ev-\d{4}$")
_DOC_RE = re.compile(r"^D\d{2}$")
_DOC_PAGE_RE = re.compile(r"^doc:(D\d{2})#page(\d+)$")
_QA_RE = re.compile(r"^qa-\d{2}$")
_MSG_RE = re.compile(r"^msg-\d{2}$")
_CALL_RE = re.compile(r"^call-\d{2}$")
_PY_RE = re.compile(r"^py:(/.*)$")
_AGENCY_RE = re.compile(r"^agency:(/.*)$")
_ASSET_RE = re.compile(r"^asset:(.+)$")
_HOUSEHOLD_RE = re.compile(r"^household:(.+)$")
_REF_PARAM_RE = re.compile(r"^ref:param\.(.+)$")
_REF_FX_RE = re.compile(r"^ref:fx\.([A-Za-z]+)\.(.+)$")
_TIMELINE_RE = re.compile(r"^timeline:(.+)$")
_LINE_KEY_RE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


def _json_pointer(root: Any, pointer: str) -> Any:
    """A small RFC-6901-style walk: '/asset_records/0' -> root['asset_records'][0]."""
    node = root
    stripped = pointer.strip("/")
    if stripped == "":
        return node
    for part in stripped.split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            node = node[int(part)]
        else:
            node = node[part]
    return node


def resolve(ref: str, packet: Packet, version: str = "v3") -> Resolved:
    if _EV_RE.match(ref):
        try:
            return Resolved(ref, "extracted_value", packet.extracted_value(ref))
        except KeyError as exc:
            raise UnresolvedReferenceError(str(exc)) from None

    if _DOC_RE.match(ref):
        try:
            return Resolved(ref, "document", packet.document(ref))
        except KeyError as exc:
            raise UnresolvedReferenceError(str(exc)) from None

    m = _DOC_PAGE_RE.match(ref)
    if m:
        document_id, page_number = m.group(1), int(m.group(2))
        try:
            document = packet.document(document_id)
        except KeyError as exc:
            raise UnresolvedReferenceError(str(exc)) from None
        for page in document.pages:
            if page.page == page_number:
                return Resolved(ref, "document_page", page)
        raise UnresolvedReferenceError(
            f"{ref}: document {document_id} has no page {page_number}"
        )

    if _QA_RE.match(ref):
        try:
            return Resolved(ref, "questionnaire_item", packet.questionnaire_item(ref))
        except KeyError as exc:
            raise UnresolvedReferenceError(str(exc)) from None

    if _MSG_RE.match(ref):
        try:
            return Resolved(ref, "message", packet.message(ref))
        except KeyError as exc:
            raise UnresolvedReferenceError(str(exc)) from None

    if _CALL_RE.match(ref):
        try:
            return Resolved(ref, "call_note", packet.call_note(ref))
        except KeyError as exc:
            raise UnresolvedReferenceError(str(exc)) from None

    m = _PY_RE.match(ref)
    if m:
        try:
            value = _json_pointer(packet.prior_years.model_dump(), m.group(1))
        except (KeyError, IndexError, ValueError) as exc:
            raise UnresolvedReferenceError(f"{ref}: {exc}") from None
        return Resolved(ref, "prior_years", value)

    m = _AGENCY_RE.match(ref)
    if m:
        try:
            value = _json_pointer(packet.tax_agency_records.model_dump(), m.group(1))
        except (KeyError, IndexError, ValueError) as exc:
            raise UnresolvedReferenceError(f"{ref}: {exc}") from None
        return Resolved(ref, "tax_agency_records", value)

    m = _ASSET_RE.match(ref)
    if m:
        try:
            return Resolved(
                ref, "asset", packet.return_version(version).asset(m.group(1))
            )
        except KeyError as exc:
            raise UnresolvedReferenceError(str(exc)) from None

    m = _HOUSEHOLD_RE.match(ref)
    if m:
        try:
            return Resolved(
                ref, "household_person", packet.household.person(m.group(1))
            )
        except KeyError as exc:
            raise UnresolvedReferenceError(str(exc)) from None

    m = _REF_PARAM_RE.match(ref)
    if m:
        name = m.group(1)
        if name not in packet.engine_reference.parameters:
            raise UnresolvedReferenceError(
                f"{ref}: no engine_reference.parameters.{name}"
            )
        return Resolved(
            ref, "engine_parameter", packet.engine_reference.parameters[name]
        )

    m = _REF_FX_RE.match(ref)
    if m:
        currency, rate_name = m.groups()
        fx = packet.engine_reference.parameters.get("fx", {})
        try:
            value = fx[currency][rate_name]
        except (KeyError, TypeError) as exc:
            raise UnresolvedReferenceError(f"{ref}: {exc}") from None
        return Resolved(ref, "fx_rate", value)

    m = _TIMELINE_RE.match(ref)
    if m:
        try:
            return Resolved(ref, "timeline_event", packet.timeline_event(m.group(1)))
        except KeyError as exc:
            raise UnresolvedReferenceError(str(exc)) from None

    if _LINE_KEY_RE.match(ref):
        try:
            return Resolved(ref, "line", packet.return_version(version).line(ref))
        except KeyError as exc:
            raise UnresolvedReferenceError(str(exc)) from None

    raise UnresolvedReferenceError(f"{ref}: unrecognized reference format")
