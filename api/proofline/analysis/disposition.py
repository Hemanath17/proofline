"""C4 rule-based disposition proposal (docs/CONTRACTS.md C4): "Rules
propose a disposition and the preparer confirms it." Every rule here is
generic -- same issuer and document type, which lines actually use a
document -- reusing the exact detection `proofline.provenance.tracing`
and `proofline.analysis.signoff` already do, never a packet-specific id.
"""

from __future__ import annotations

from dataclasses import dataclass

from proofline.analysis.signoff import document_replacements
from proofline.packet import Packet, ReturnVersion
from proofline.provenance.tracing import trace_document


@dataclass(frozen=True)
class DispositionProposal:
    disposition: str
    reason: str | None
    extraction_complete: bool


def propose_disposition(
    packet: Packet, rv: ReturnVersion, document_id: str
) -> DispositionProposal:
    document = packet.document(document_id)
    extraction_complete = document.extraction.status == "extracted"
    trace = trace_document(packet, document_id, version=rv.version)
    if trace.used:
        return DispositionProposal(
            disposition="used", reason=None, extraction_complete=extraction_complete
        )

    replacements = document_replacements(packet, rv)
    if document_id in replacements:
        new_id = replacements[document_id]
        return DispositionProposal(
            disposition="superseded_by",
            reason=f"replaced by {new_id}, same issuer and document type",
            extraction_complete=extraction_complete,
        )

    used_elsewhere = {
        other.id
        for other in packet.documents
        if other.id != document_id
        and trace_document(packet, other.id, version=rv.version).used
    }
    duplicate_of = next(
        (
            other_id
            for other_id in used_elsewhere
            if packet.document(other_id).issuer == document.issuer
            and packet.document(other_id).document_type == document.document_type
        ),
        None,
    )
    if duplicate_of is not None:
        return DispositionProposal(
            disposition="duplicate_of",
            reason=(
                f"same issuer ({document.issuer}) and document type "
                f"({document.document_type}) as {duplicate_of}, but contributes to "
                f"no line itself"
            ),
            extraction_complete=extraction_complete,
        )

    return DispositionProposal(
        disposition="pending",
        reason=trace.note or "no rule found a reason; the preparer decides",
        extraction_complete=extraction_complete,
    )
