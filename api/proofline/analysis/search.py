"""B38: full-text search across cases, lines, documents and review notes.
A document snippet is always redacted, regardless of the searching actor's
clearance -- a search result is a quick preview, not "opening the
document" the way the document page view is (which still goes through its
own reveal-and-log flow when someone actually clicks through); see
docs/DECISIONS.md. Reuses `security/redact.py`'s existing sensitive-value
list rather than a second redaction path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from proofline.db.models import Case, ReviewNote
from proofline.db.repository import list_cases, list_review_notes
from proofline.packet import Packet
from proofline.security.redact import collect_sensitive_values, redact_text

ResultType = Literal["case", "line", "document", "note"]

_SNIPPET_RADIUS = 60


@dataclass(frozen=True)
class SearchResult:
    type: ResultType
    id: str
    title: str
    snippet: str


def _snippet(text: str, query: str) -> str:
    lowered = text.lower()
    index = lowered.find(query.lower())
    if index == -1:
        return text[: _SNIPPET_RADIUS * 2]
    start = max(0, index - _SNIPPET_RADIUS)
    end = min(len(text), index + len(query) + _SNIPPET_RADIUS)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _matches(query: str, *fields: str | None) -> bool:
    lowered = query.lower()
    return any(field and lowered in field.lower() for field in fields)


def _search_cases(cases: list[Case], query: str) -> list[SearchResult]:
    results = []
    for case in cases:
        if _matches(query, case.case_id, case.observed, case.expected, case.scope):
            field = next(f for f in (case.observed, case.expected, case.case_id) if f)
            results.append(
                SearchResult(
                    type="case",
                    id=case.case_id,
                    title=case.observed or case.case_id,
                    snippet=_snippet(field, query),
                )
            )
    return results


def _search_lines(packet: Packet, query: str) -> list[SearchResult]:
    rv = packet.return_versions[-1]
    results = []
    for line in rv.lines:
        if _matches(query, line.key, line.label):
            results.append(
                SearchResult(
                    type="line",
                    id=line.key,
                    title=line.label or line.key,
                    snippet=line.key,
                )
            )
    return results


def _search_documents(packet: Packet, query: str) -> list[SearchResult]:
    sensitive_values = collect_sensitive_values(packet)
    results = []
    for document in packet.documents:
        if _matches(query, document.title, document.issuer, document.document_type):
            field = next(f for f in (document.title, document.issuer) if f)
            results.append(
                SearchResult(
                    type="document",
                    id=document.id,
                    title=document.title,
                    snippet=redact_text(_snippet(field, query), sensitive_values),
                )
            )
            continue
        for page in document.pages:
            if query.lower() in page.printed_content.lower():
                results.append(
                    SearchResult(
                        type="document",
                        id=document.id,
                        title=f"{document.title} (page {page.page})",
                        snippet=redact_text(
                            _snippet(page.printed_content, query), sensitive_values
                        ),
                    )
                )
                break
    return results


def _search_notes(notes: list[ReviewNote], query: str) -> list[SearchResult]:
    results = []
    for note in notes:
        if _matches(query, note.body, note.resolution):
            field = next(f for f in (note.body, note.resolution) if f)
            results.append(
                SearchResult(
                    type="note",
                    id=note.id,
                    title=f"Review note on {note.about_type} {note.about_id}",
                    snippet=_snippet(field, query),
                )
            )
    return results


def search(packet: Packet, session: Session, query: str) -> list[SearchResult]:
    query = query.strip()
    if not query:
        return []
    return [
        *_search_cases(list_cases(session), query),
        *_search_lines(packet, query),
        *_search_documents(packet, query),
        *_search_notes(list_review_notes(session), query),
    ]
