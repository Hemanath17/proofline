"""DEPENDENT_SSN_INDEPENDENT_SOURCE

Rule: a dependent's household SSN must match an independently-sourced SSN
for that same person -- the prior-year filed return, and, where available,
an SSN extracted from an identity document (a Social Security card scan,
for example). A mismatch confirmed by an identity document is an error; a
mismatch against the prior-year return alone, with no identity document on
file, is a possible discrepancy.
"""

from __future__ import annotations

from proofline.checks.models import CheckResult
from proofline.packet import Packet
from proofline.provenance.claim_identity import household_fact

CHECK_ID = "DEPENDENT_SSN_INDEPENDENT_SOURCE"
CHECK_VERSION = 1


def _prior_year_dependent_index_and_ssn(
    packet: Packet, person_name: str
) -> tuple[int, str] | None:
    dependents = packet.prior_years.return_2024.get("dependents", [])
    for index, prior in enumerate(dependents):
        if prior.get("name", "").strip().lower() == person_name.strip().lower():
            return index, prior.get("ssn")
    return None


def _identity_document_ssn(packet: Packet, person_name: str) -> tuple[str, str] | None:
    """An (extracted_value id, ssn) pair from an identity document whose
    title mentions this person, if one exists."""
    for value in packet.extracted_values:
        if value.value_type != "ssn":
            continue
        document = packet.document(value.document_id)
        if document.document_type != "identity_document":
            continue
        if person_name.strip().lower() in document.title.lower():
            return value.id, str(value.value)
    return None


def _efile_rejection_index_mentioning(packet: Packet, person_name: str) -> int | None:
    for index, submission in enumerate(packet.tax_agency_records.efile):
        if submission.get("status") != "rejected":
            continue
        for error in submission.get("errors", []):
            if person_name.strip().lower() in error.get("message", "").lower():
                return index
    return None


def run(packet: Packet) -> list[CheckResult]:
    findings: list[CheckResult] = []

    dependents = [
        person for person in packet.household.people if person.role == "dependent"
    ]

    for person in dependents:
        prior_match = _prior_year_dependent_index_and_ssn(packet, person.name)
        if prior_match is None:
            continue
        prior_index, prior_ssn = prior_match
        if prior_ssn == person.ssn:
            continue

        evidence_refs = [
            f"household:{person.id}",
            f"py:/return_2024/dependents/{prior_index}",
        ]

        identity_match = _identity_document_ssn(packet, person.name)
        if identity_match is None:
            findings.append(
                CheckResult(
                    check_id=CHECK_ID,
                    check_version=CHECK_VERSION,
                    area="identity",
                    scope="return",
                    finding_type="possible_discrepancy",
                    severity="blocks_filing",
                    evidence_refs=evidence_refs,
                    claims=[household_fact(person.id, "ssn")],
                    observed=f"The household record's SSN for {person.name} differs from last year's filed return.",
                    expected="A dependent's SSN is the same every year.",
                    tax_effect=None,
                    impact_unknown=False,
                    limitations="Compares against the prior-year return only; no identity document is on file to confirm which number is correct.",
                    recommended_action="Ask the client for the dependent's Social Security card and correct the return before filing.",
                )
            )
            continue

        identity_ev_id, identity_ssn = identity_match
        if identity_ssn == person.ssn:
            # The identity document agrees with the household record even
            # though the prior-year return doesn't -- nothing to flag here.
            continue

        evidence_refs.append(identity_ev_id)
        rejection_index = _efile_rejection_index_mentioning(packet, person.name)
        if rejection_index is not None:
            evidence_refs.append(f"agency:/efile/{rejection_index}")

        findings.append(
            CheckResult(
                check_id=CHECK_ID,
                check_version=CHECK_VERSION,
                area="identity",
                scope="return",
                finding_type="error",
                severity="blocks_filing",
                evidence_refs=evidence_refs,
                claims=[household_fact(person.id, "ssn")],
                observed=f"The household record's SSN for {person.name} doesn't match the SSN on an identity document on file for them.",
                expected="A dependent's SSN matches their own identity document.",
                tax_effect=None,
                impact_unknown=False,
                limitations="Confirmed by one identity document; doesn't rule out a further data-entry error elsewhere.",
                recommended_action="Correct the dependent's SSN in the household record to match the identity document before filing.",
            )
        )

    return findings
