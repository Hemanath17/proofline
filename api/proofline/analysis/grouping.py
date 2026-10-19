"""Root-cause grouping (CONTRACTS.md C1): "findings that share a root cause
become one case, not a pile of alerts. The root-cause key is the check id
plus its claim identities."

Claim identity keys are already stable strings independent of where a claim
sits on the return (proofline.provenance.claim_identity), so sorting them
before joining means two findings about the same claims always produce the
same key regardless of the order a check happened to list them in.
"""

from __future__ import annotations

from proofline.checks.models import CheckResult


def root_cause_key(finding: CheckResult) -> str:
    claim_keys = sorted(str(claim) for claim in finding.claims)
    return f"{finding.check_id}:{'|'.join(claim_keys)}"


def hand_opened_root_cause_key(origin: str, origin_ref: str) -> str:
    """The root-cause key for a case opened by a person rather than a
    check (CONTRACTS.md: "...or the replaced document, the notice, the
    question thread, or a fresh id for a case someone opened by hand").
    `origin_ref` must already be unique for a given `origin` (e.g. a
    document id, a notice id, a freshly generated id for a from-scratch
    case) -- this function only namespaces it so it can never collide with
    a check-origin key, which always starts with a check id."""
    return f"hand:{origin}:{origin_ref}"
