"""
Template for a Proofline check.

Copy this file to api/proofline/checks/<check_name>.py and replace the example
logic. The example below is a real, general rule: a dependent's SSN this year
should match the SSN on last year's filed return. It never mentions a specific
person, number or ID from the packet.
"""

from proofline.checks.models import CheckResult
from proofline.packet import Packet
from proofline.provenance.claim_identity import household_fact

CHECK_ID = "DEPENDENT_SSN_PRIOR_YEAR"
CHECK_VERSION = 1


def run(packet: Packet) -> list[CheckResult]:
    findings: list[CheckResult] = []

    # Step 1: collect this year's dependents, as the client entered them.
    current_dependents = [
        person for person in packet.household.people if person.role == "dependent"
    ]

    # Step 2: collect last year's dependents, from the filed prior-year return.
    prior_dependents = packet.prior_years.return_2024.get("dependents", [])

    # Step 3: compare each current dependent with the prior-year dependent of the same name.
    for person in current_dependents:
        current_name = person.name
        current_ssn = person.ssn

        for prior_index, prior in enumerate(prior_dependents):
            prior_name = prior["name"]
            prior_ssn = prior["ssn"]

            same_person = prior_name.strip().lower() == current_name.strip().lower()
            if not same_person:
                continue

            ssn_matches = prior_ssn == current_ssn
            if ssn_matches:
                continue

            finding = CheckResult(
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
                observed=f"This year's organizer lists {current_name} with a different SSN than last year's filed return.",
                expected="A dependent's SSN is the same every year.",
                tax_effect=None,
                impact_unknown=False,
                limitations="Compares against the prior-year return only; a Social Security card or other third-party record is needed to confirm which number is correct.",
                recommended_action="Ask the client for the dependent's Social Security card and correct the return before filing.",
            )
            findings.append(finding)

    return findings
