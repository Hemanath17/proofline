"""C4 rule-based disposition proposal, proven against the real packet's
documented examples (docs/CONTRACTS.md C4, docs/PACKET.md): D09 is used,
D10 is a same-issuer/same-type duplicate that lands on no line, D30 is
superseded by D31.
"""

from proofline.analysis.disposition import propose_disposition
from proofline.packet import load_packet


def test_d09_proposes_used() -> None:
    packet = load_packet()
    rv = packet.return_versions[-1]
    proposal = propose_disposition(packet, rv, "D09")
    assert proposal.disposition == "used"
    assert proposal.reason is None


def test_d10_proposes_duplicate_of_d09() -> None:
    packet = load_packet()
    rv = packet.return_versions[-1]
    proposal = propose_disposition(packet, rv, "D10")
    assert proposal.disposition == "duplicate_of"
    assert "D09" in proposal.reason


def test_d30_proposes_superseded_by_d31() -> None:
    packet = load_packet()
    rv = packet.return_version("v2")
    proposal = propose_disposition(packet, rv, "D30")
    assert proposal.disposition == "superseded_by"
    assert "D31" in proposal.reason


def test_d31_proposes_used_but_is_not_extraction_complete() -> None:
    packet = load_packet()
    rv = packet.return_versions[-1]
    proposal = propose_disposition(packet, rv, "D31")
    assert proposal.disposition == "used"
    assert proposal.extraction_complete is False
