"""Tracing in both directions, plus the dependency graph over line inputs.

A line's "excluded" documents are found generically, not by name: for each
document actually behind a line's sources, find other documents sharing the
same issuer and document type that contribute to *no* line anywhere in this
return version. For F1040.1a that finds D10 relative to D09 purely from the
packet's own data (same issuer, same document type, zero lines use any of
its extracted values) — no document id is ever hardcoded here. The line's
own `note` field, when present, is carried along as a human-readable
explanation, not used to detect the exclusion.

Every source ref on a line resolves to something: an `ev-` ref contributes a
document to `primary_sources`; everything else (qa-, msg-, call-, py:,
household:, ref:, timeline:, asset: and line-key/version refs) resolves
through `provenance.resolver.resolve` and is kept in `other_sources`, so a
line sourced only from, say, a household fact never traces to nothing. A
genuinely dangling ref raises UnresolvedReferenceError (from the resolver),
never a bare KeyError.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from proofline.packet import Packet, ReturnVersion
from proofline.provenance.resolver import UnresolvedReferenceError, resolve


@dataclass(frozen=True)
class ExcludedDocument:
    document_id: str
    reason: str


@dataclass(frozen=True)
class OtherSource:
    ref: str
    kind: str


@dataclass(frozen=True)
class LineTrace:
    line_key: str
    version: str
    value: Any
    label: str
    rule: str
    inputs: tuple[str, ...]
    used_by: tuple[str, ...]
    primary_sources: frozenset[str]
    other_sources: tuple[OtherSource, ...]
    excluded: tuple[ExcludedDocument, ...]
    note: str | None


@dataclass(frozen=True)
class DocumentTrace:
    document_id: str
    version: str
    lines_using: tuple[str, ...]
    used: bool
    note: str | None


def _documents_behind_source(
    packet: Packet, rv: ReturnVersion, source_ref: str, version: str
) -> set[str]:
    if source_ref.startswith("ev-"):
        resolved = resolve(source_ref, packet, version)
        return {resolved.value.document_id}
    if source_ref.startswith("asset:"):
        resolved = resolve(source_ref, packet, version)
        asset = resolved.value
        documents: set[str] = set()
        for nested_ref in asset.sources:
            documents |= _documents_behind_source(packet, rv, nested_ref, version)
        return documents
    # qa-, msg-, call- and every other non-document reference format: confirm
    # it actually resolves (a dangling ref raises UnresolvedReferenceError),
    # but it contributes no document of its own.
    resolve(source_ref, packet, version)
    return set()


def _documents_for_line(
    packet: Packet, rv: ReturnVersion, line_sources: list[str], version: str
) -> set[str]:
    documents: set[str] = set()
    for source_ref in line_sources:
        documents |= _documents_behind_source(packet, rv, source_ref, version)
    return documents


def _documents_for_line_lenient(
    packet: Packet, rv: ReturnVersion, line_sources: list[str], version: str
) -> set[str]:
    """Like `_documents_for_line`, but a dangling ref on this line doesn't
    discard the line's *other*, resolvable sources -- a sweep over every
    line in the return version (to answer a question about a different
    line or document) shouldn't even partially blind itself to a line's
    good refs just because one of that same line's other refs is bad."""
    documents: set[str] = set()
    for source_ref in line_sources:
        try:
            documents |= _documents_behind_source(packet, rv, source_ref, version)
        except UnresolvedReferenceError:
            continue
    return documents


def _other_sources_for_line(
    packet: Packet, rv: ReturnVersion, line_sources: list[str], version: str
) -> tuple[OtherSource, ...]:
    other: list[OtherSource] = []
    for source_ref in line_sources:
        if source_ref.startswith("ev-"):
            continue
        resolved = resolve(source_ref, packet, version)
        other.append(OtherSource(ref=source_ref, kind=resolved.kind))
    return tuple(other)


def _documents_used_by_any_line(
    packet: Packet, rv: ReturnVersion, version: str
) -> frozenset[str]:
    """The documents behind any line's sources, across the whole return
    version -- used only to detect "excluded" duplicates (see module
    docstring). This sweep must tolerate a dangling ref anywhere: one bad
    ref on one line shouldn't make every other line's trace fail too, and
    (using the lenient per-ref variant) shouldn't even discard that same
    line's *other* good refs. The line actually being traced still raises
    on its own dangling ref, in `_documents_for_line` (strict), called
    directly from `trace_line`."""
    cached = rv.get_documents_used_by_any_line_cache()
    if cached is None:
        documents: set[str] = set()
        for line in rv.lines:
            documents |= _documents_for_line_lenient(packet, rv, line.sources, version)
        cached = frozenset(documents)
        rv.set_documents_used_by_any_line_cache(cached)
    return cached


def trace_line(packet: Packet, line_key: str, version: str = "v3") -> LineTrace:
    rv = packet.return_version(version)
    line = rv.line(line_key)

    primary_sources = _documents_for_line(packet, rv, line.sources, version)
    other_sources = _other_sources_for_line(packet, rv, line.sources, version)
    documents_used_anywhere = _documents_used_by_any_line(packet, rv, version)

    excluded: list[ExcludedDocument] = []
    for source_document_id in primary_sources:
        source_document = packet.document(source_document_id)
        for other in packet.documents:
            if other.id in primary_sources or other.id in documents_used_anywhere:
                continue
            if (
                other.issuer == source_document.issuer
                and other.document_type == source_document.document_type
            ):
                excluded.append(
                    ExcludedDocument(
                        document_id=other.id,
                        reason=(
                            f"same issuer ({other.issuer}) and document type "
                            f"({other.document_type}) as {source_document_id}, but none of its "
                            f"extracted values are used by any line in return version {version}"
                        ),
                    )
                )

    return LineTrace(
        line_key=line_key,
        version=version,
        value=line.value,
        label=line.label,
        rule=line.rule,
        inputs=tuple(line.inputs),
        used_by=tuple(sorted(dependents_of(rv, line_key))),
        primary_sources=frozenset(primary_sources),
        other_sources=other_sources,
        excluded=tuple(excluded),
        note=line.note,
    )


def trace_document(
    packet: Packet, document_id: str, version: str = "v3"
) -> DocumentTrace:
    """Which lines use this document. Like `_documents_used_by_any_line`,
    this has to check every line in the return version to answer a
    question about one unrelated document, so a dangling ref anywhere must
    not make tracing *this* document fail -- the lenient per-ref variant
    skips only the bad ref, not that whole line's other, resolvable ones."""
    rv = packet.return_version(version)
    lines_using_list: list[str] = []
    for line in rv.lines:
        documents = _documents_for_line_lenient(packet, rv, line.sources, version)
        if document_id in documents:
            lines_using_list.append(line.key)
    lines_using = tuple(lines_using_list)
    used = len(lines_using) > 0

    note: str | None = None
    if not used:
        if document_id in rv.documents_superseded:
            note = f"superseded in return version {version}"
        elif document_id in rv.documents_used:
            note = f"listed in documents_used for {version} but contributes to no line"

    return DocumentTrace(
        document_id=document_id,
        version=version,
        lines_using=lines_using,
        used=used,
        note=note,
    )


def dependency_graph(rv: ReturnVersion) -> dict[str, frozenset[str]]:
    return {line.key: frozenset(line.inputs) for line in rv.lines}


def dependents_of(rv: ReturnVersion, line_key: str) -> frozenset[str]:
    return frozenset(line.key for line in rv.lines if line_key in line.inputs)
