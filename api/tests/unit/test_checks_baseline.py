from decimal import Decimal

from proofline.checks.baseline import build_report
from proofline.checks.runner import run_all_checks
from proofline.packet import Document, ExtractedValue, Extraction, Line, load_packet

from tests.unit.factories import minimal_packet, minimal_return_version


def test_baseline_recall_is_four_of_four_on_the_real_packet() -> None:
    report = build_report(load_packet())

    assert sorted(report.confirmed_found) == ["E1", "E2", "E3", "E4"]
    assert report.confirmed_missing == []
    assert report.recall == 1.0


def test_baseline_precision_on_the_real_packet() -> None:
    report = build_report(load_packet())

    assert report.precision == 1.0
    assert report.unexplained == []


def _ev(document_id: str, field: str, value, index: int) -> ExtractedValue:
    return ExtractedValue(
        id=f"ev-{index:04d}",
        document_id=document_id,
        page=1,
        field=field,
        value=value,
        value_type="money" if "basis" in field else "text",
        confidence=0.99,
    )


def test_matching_on_check_id_alone_would_wrongly_count_an_unrelated_fix_as_found() -> (
    None
):
    """Fix the RSU lots this check was built around (give them real, nonzero
    basis) but leave an *unrelated* noncovered lot at zero basis on a date
    that happens to be a genuine vest date for a different supplement lot.
    The fixed check correctly flags that unrelated lot -- it's still a real
    gap -- but its evidence has nothing to do with the original E2 claims.
    Matching only on check_id would count this as "E2 found"; matching on
    evidence/claims overlap correctly reports E2 as still missing."""
    documents = [
        Document(
            id="D11",
            title="Stock plan supplement",
            document_type="stock_plan_supplement",
            issuer="Acme Corp equity plan administrator",
            page_count=1,
            extraction=Extraction(status="extracted", values=0),
        ),
        Document(
            id="D28",
            title="Brokerage 1099-B",
            document_type="1099-composite",
            issuer="Some Broker",
            page_count=1,
            extraction=Extraction(status="extracted", values=0),
        ),
    ]
    extracted_values = [
        _ev("D11", "RSU-FIXED_adjusted_basis", 5000.0, 1),
        _ev("D11", "RSU-FIXED_acquired", "2025-01-01", 2),
        _ev("D11", "RSU-OTHER_adjusted_basis", 7000.0, 3),
        _ev("D11", "RSU-OTHER_acquired", "2025-06-01", 4),
        # The original lot, now fixed (nonzero basis) -- no longer a finding.
        _ev("D28", "FIXED1_description", "Acme Corp (RSU)", 5),
        _ev("D28", "FIXED1_acquired", "2025-01-01", 6),
        _ev("D28", "FIXED1_basis", 5000.0, 7),
        _ev("D28", "FIXED1_covered", False, 8),
        _ev("D28", "FIXED1_term", "short", 9),
        # An unrelated lot that genuinely matches a different supplement lot.
        _ev("D28", "OTHER1_description", "Acme Corp (RSU)", 10),
        _ev("D28", "OTHER1_acquired", "2025-06-01", 11),
        _ev("D28", "OTHER1_basis", 0.0, 12),
        _ev("D28", "OTHER1_covered", False, 13),
        _ev("D28", "OTHER1_term", "short", 14),
    ]
    line_fixed = Line(
        key="F8949.A.FIXED1",
        jurisdiction="federal",
        form="F8949",
        line="A.FIXED1",
        label="Some Broker (acquired 2025-01-01)",
        value=Decimal(0),
        rule="R-8949-LOT",
        sources=["ev-0005", "ev-0006", "ev-0007", "ev-0008", "ev-0009"],
    )
    line_other = Line(
        key="F8949.A.OTHER1",
        jurisdiction="federal",
        form="F8949",
        line="A.OTHER1",
        label="Some Broker (acquired 2025-06-01)",
        value=Decimal(100),
        rule="R-8949-LOT",
        sources=["ev-0010", "ev-0011", "ev-0012", "ev-0013", "ev-0014"],
    )
    rv = minimal_return_version(lines=[line_fixed, line_other])
    packet = minimal_packet(
        documents=documents, extracted_values=extracted_values, return_versions=[rv]
    )

    findings = run_all_checks(packet).findings
    assert any(
        f.check_id == "RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE" for f in findings
    ), "the fixed check should still flag the unrelated lot"

    stale_expectations = {
        "confirmed": [
            {
                "error_id": "E2",
                "check_id": "RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE",
                "claims": [
                    "1099b_lot:Northlake Securities:N1",
                    "1099b_lot:Northlake Securities:N3",
                    "1099b_lot:Northlake Securities:N4",
                ],
            }
        ],
        "possible": [],
    }

    report = build_report(packet, expectations=stale_expectations)

    assert report.confirmed_missing == ["E2"]
    assert report.confirmed_found == []
    assert len(report.unexplained) == 1
