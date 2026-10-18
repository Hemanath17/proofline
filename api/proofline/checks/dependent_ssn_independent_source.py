"""DEPENDENT_SSN_INDEPENDENT_SOURCE

Rule: every household member's SSN must match an independently-sourced SSN
for that same person -- their own identity document (a Social Security
card scan, for example) and, for the taxpayer or spouse, their own W-2 box
a. This is checked regardless of whether the prior-year return happens to
agree, and regardless of whether the person is new to the return this year,
because the prior-year return isn't an independent source either. A
mismatch confirmed by an identity document or a W-2 is an error; with no
independent source at all, a mismatch against the prior-year return alone
is a possible discrepancy.
"""

from __future__ import annotations

import re

from proofline.checks.models import CheckResult
from proofline.packet import Document, Packet, Person
from proofline.provenance.claim_identity import household_fact

CHECK_ID = "DEPENDENT_SSN_INDEPENDENT_SOURCE"
CHECK_VERSION = 2


def _digits_only(ssn: str) -> str:
    return re.sub(r"\D", "", ssn)


def _belongs_to_token(person: Person) -> str:
    if person.role == "dependent":
        return f"dependent:{person.id}"
    return person.role


def _documents_belonging_to(packet: Packet, token: str) -> list[Document]:
    return [doc for doc in packet.documents if doc.belongs_to == token]


def _independent_ssn_sources(
    packet: Packet, person: Person
) -> list[tuple[str, str, str]]:
    """Every (evidence_ref, source_kind, ssn) triple from a source that's
    independent of the household record itself: an identity document, or,
    for the taxpayer and spouse, a W-2 box a."""
    token = _belongs_to_token(person)
    sources: list[tuple[str, str, str]] = []

    for document in _documents_belonging_to(packet, token):
        if document.document_type == "identity_document":
            for value in packet.extracted_values:
                if value.document_id == document.id and value.value_type == "ssn":
                    sources.append((value.id, "identity_document", str(value.value)))
        elif document.document_type == "W-2" and person.role in (
            "taxpayer",
            "spouse",
        ):
            for value in packet.extracted_values:
                if value.document_id == document.id and value.field == "employee_ssn":
                    sources.append((value.id, "w2_box_a", str(value.value)))

    return sources


def _prior_year_dependent_index_and_ssn(
    packet: Packet, person_name: str
) -> tuple[int, str] | None:
    dependents = packet.prior_years.return_2024.get("dependents", [])
    for index, prior in enumerate(dependents):
        if prior.get("name", "").strip().lower() == person_name.strip().lower():
            return index, prior.get("ssn")
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

    for person in packet.household.people:
        household_ssn = _digits_only(person.ssn)
        independent_sources = _independent_ssn_sources(packet, person)

        any_independent_match = False
        for evidence_ref, source_kind, source_ssn in independent_sources:
            if _digits_only(source_ssn) == household_ssn:
                any_independent_match = True
                continue

            evidence_refs = [f"household:{person.id}", evidence_ref]
            if person.role == "dependent":
                prior_match = _prior_year_dependent_index_and_ssn(packet, person.name)
                if prior_match is not None:
                    prior_index, prior_ssn = prior_match
                    if _digits_only(prior_ssn) != household_ssn:
                        evidence_refs.append(
                            f"py:/return_2024/dependents/{prior_index}"
                        )
            rejection_index = _efile_rejection_index_mentioning(packet, person.name)
            if rejection_index is not None:
                evidence_refs.append(f"agency:/efile/{rejection_index}")

            source_label = (
                "an identity document"
                if source_kind == "identity_document"
                else "their own W-2"
            )
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
                    observed=(
                        f"The household record's SSN for {person.name} doesn't match "
                        f"the SSN on {source_label} on file for them."
                    ),
                    expected="A person's SSN matches their own independent source.",
                    tax_effect=None,
                    impact_unknown=False,
                    limitations=(
                        f"Confirmed by {source_label}; doesn't rule out a further "
                        "data-entry error elsewhere."
                    ),
                    recommended_action=(
                        f"Correct {person.name}'s SSN in the household record to match "
                        f"{source_label} before filing."
                    ),
                )
            )

        if any_independent_match or independent_sources:
            # Either an independent source confirms the household record, or
            # every independent source that disagreed already produced an
            # error above -- in both cases the prior-year return adds
            # nothing further.
            continue

        if person.role != "dependent":
            continue

        prior_match = _prior_year_dependent_index_and_ssn(packet, person.name)
        if prior_match is None:
            continue
        prior_index, prior_ssn = prior_match
        if _digits_only(prior_ssn) == household_ssn:
            continue

        findings.append(
            CheckResult(
                check_id=CHECK_ID,
                check_version=CHECK_VERSION,
                area="identity",
                scope="return",
                finding_type="possible_discrepancy",
                severity="blocks_filing",
                evidence_refs=[
                    f"household:{person.id}",
                    f"py:/return_2024/dependents/{prior_index}",
                ],
                claims=[household_fact(person.id, "ssn")],
                observed=(
                    f"The household record's SSN for {person.name} differs from last "
                    "year's filed return."
                ),
                expected="A dependent's SSN is the same every year.",
                tax_effect=None,
                impact_unknown=False,
                limitations=(
                    "Compares against the prior-year return only; no independent source "
                    "is on file to confirm which number is correct."
                ),
                recommended_action=(
                    "Ask the client for the dependent's Social Security card and correct "
                    "the return before filing."
                ),
            )
        )

    return findings
