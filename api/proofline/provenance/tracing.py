"""Tracing in both directions, plus the dependency graph over line inputs.

A line's "excluded" documents are found generically, not by name: for each
document actually behind a line's sources, find other documents sharing the
same issuer and document type that contribute to *no* line anywhere in this
return version. For F1040.1a that finds D10 relative to D09 purely from the
packet's own data (same issuer, same document type, zero lines use any of
its extracted values) — no document id is ever hardcoded here. The line's
own `note` field, when present, is carried along as a human-readable
explanation, not used to detect the exclusion.
"""

from __future__ import annotations

from dataclasses import dataclass

from proofline.packet import Packet, ReturnVersion


@dataclass(frozen=True)
class ExcludedDocument:
    document_id: str
    reason: str


@dataclass(frozen=True)
class LineTrace:
    line_key: str
    version: str
    primary_sources: frozenset[str]
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
    packet: Packet, rv: ReturnVersion, source_ref: str
) -> set[str]:
    if source_ref.startswith("ev-"):
        return {packet.extracted_value(source_ref).document_id}
    if source_ref.startswith("asset:"):
        asset_id = source_ref.split(":", 1)[1]
        try:
            asset = rv.asset(asset_id)
        except KeyError:
            return set()
        documents: set[str] = set()
        for nested_ref in asset.sources:
            documents |= _documents_behind_source(packet, rv, nested_ref)
        return documents
    # qa-, msg- and call- sources are client items, not documents.
    return set()


def _documents_for_line(
    packet: Packet, rv: ReturnVersion, line_sources: list[str]
) -> set[str]:
    documents: set[str] = set()
    for source_ref in line_sources:
        documents |= _documents_behind_source(packet, rv, source_ref)
    return documents


def _documents_used_by_any_line(packet: Packet, rv: ReturnVersion) -> set[str]:
    documents: set[str] = set()
    for line in rv.lines:
        documents |= _documents_for_line(packet, rv, line.sources)
    return documents


def trace_line(packet: Packet, line_key: str, version: str = "v3") -> LineTrace:
    rv = packet.return_version(version)
    line = rv.line(line_key)

    primary_sources = _documents_for_line(packet, rv, line.sources)
    documents_used_anywhere = _documents_used_by_any_line(packet, rv)

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
        primary_sources=frozenset(primary_sources),
        excluded=tuple(excluded),
        note=line.note,
    )


def trace_document(
    packet: Packet, document_id: str, version: str = "v3"
) -> DocumentTrace:
    rv = packet.return_version(version)
    lines_using = tuple(
        line.key
        for line in rv.lines
        if document_id in _documents_for_line(packet, rv, line.sources)
    )
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
