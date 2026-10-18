import json
from pathlib import Path

from proofline.checks.dependent_ssn_independent_source import run
from proofline.packet import Document, ExtractedValue, Extraction, Person, load_packet

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


def _identity_document(document_id: str, belongs_to: str) -> Document:
    return Document(
        id=document_id,
        title="Social Security card",
        document_type="identity_document",
        belongs_to=belongs_to,
        page_count=1,
        extraction=Extraction(status="extracted", values=1),
    )


def _ssn_value(document_id: str, ssn: str, index: int) -> ExtractedValue:
    return ExtractedValue(
        id=f"ev-{index:04d}",
        document_id=document_id,
        page=1,
        field="ssn",
        value=ssn,
        value_type="ssn",
        confidence=0.99,
    )


def test_new_dependent_with_no_prior_year_entry_is_still_checked_against_identity_doc() -> (
    None
):
    """A dependent who's new this year has no prior-year entry to compare
    against at all -- but their own identity document is still an
    independent source, and a mismatch there is still an error."""
    household = minimal_household(
        people=[
            Person(
                id="taxpayer", role="taxpayer", name="Test Taxpayer", ssn="000-00-0001"
            ),
            Person(
                id="newdep", role="dependent", name="New Dependent", ssn="111-22-3333"
            ),
        ]
    )
    documents = [_identity_document("D50", "dependent:newdep")]
    extracted_values = [_ssn_value("D50", "111-22-3399", 1)]
    packet = minimal_packet(
        household=household, documents=documents, extracted_values=extracted_values
    )

    findings = run(packet)

    assert len(findings) == 1
    assert findings[0].finding_type == "error"
    assert [c.key for c in findings[0].claims] == ["household:newdep:ssn"]


def test_prior_year_agreeing_does_not_excuse_an_identity_document_mismatch() -> None:
    """Even when the prior-year return agrees with the household record,
    a disagreeing identity document is still an independent source and
    still an error."""
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
    documents = [_identity_document("D50", "dependent:dep1")]
    extracted_values = [_ssn_value("D50", "000-00-0009", 1)]
    packet = minimal_packet(
        household=household,
        documents=documents,
        extracted_values=extracted_values,
        prior_years={
            "return_2024": {
                "dependents": [{"name": "Test Dependent", "ssn": "000-00-0002"}]
            }
        },
    )

    findings = run(packet)

    assert len(findings) == 1
    assert findings[0].finding_type == "error"


def test_taxpayer_w2_box_a_mismatch_is_an_error() -> None:
    """The taxpayer and spouse don't have a "last year's return" comparison
    in this check -- their own W-2 box a is the independent source."""
    household = minimal_household(
        people=[
            Person(
                id="taxpayer", role="taxpayer", name="Test Taxpayer", ssn="000-00-0001"
            ),
        ]
    )
    documents = [
        Document(
            id="D01",
            title="W-2",
            document_type="W-2",
            belongs_to="taxpayer",
            page_count=1,
            extraction=Extraction(status="extracted", values=1),
        )
    ]
    extracted_values = [
        ExtractedValue(
            id="ev-0001",
            document_id="D01",
            page=1,
            field="employee_ssn",
            value="000-00-0009",
            value_type="ssn",
            confidence=0.99,
        )
    ]
    packet = minimal_packet(
        household=household, documents=documents, extracted_values=extracted_values
    )

    findings = run(packet)

    assert len(findings) == 1
    assert findings[0].finding_type == "error"
    assert "W-2" in findings[0].observed


def test_ssn_compared_digits_only_ignores_dash_formatting() -> None:
    """An SSN printed without dashes should still be recognized as a match
    against the dashed household record."""
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
    documents = [_identity_document("D50", "dependent:dep1")]
    extracted_values = [_ssn_value("D50", "000000002", 1)]
    packet = minimal_packet(
        household=household, documents=documents, extracted_values=extracted_values
    )

    assert run(packet) == []
