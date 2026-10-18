import json
from pathlib import Path

from proofline.checks.dependent_ssn_independent_source import run
from proofline.packet import Person, load_packet
from tests.unit.factories import minimal_household, minimal_packet

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "DEPENDENT_SSN_INDEPENDENT_SOURCE.json"
)


def test_real_packet_matches_fixture() -> None:
    packet = load_packet()
    findings = run(packet)

    actual = [f.model_dump(mode="json") for f in findings]
    expected = json.loads(_FIXTURE_PATH.read_text())

    assert actual == expected


def test_clean_packet_has_no_findings() -> None:
    household = minimal_household(
        people=[
            Person(
                id="taxpayer", role="taxpayer", name="Test Taxpayer", ssn="000-00-0001"
            ),
            Person(
                id="dep1", role="dependent", name="Test Dependent", ssn="000-00-0002"
            ),
        ]
    )
    packet = minimal_packet(
        household=household,
        prior_years={
            "return_2024": {
                "dependents": [{"name": "Test Dependent", "ssn": "000-00-0002"}]
            }
        },
    )

    assert run(packet) == []
