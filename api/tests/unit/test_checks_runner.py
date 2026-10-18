from proofline.checks.runner import discover_check_modules, run_all_checks
from proofline.packet import load_packet


def test_discovers_every_check_module() -> None:
    assert discover_check_modules() == [
        "dependent_ssn_independent_source",
        "document_total_disagrees_with_extracted_detail",
        "rsu_lot_zero_basis_supplement_available",
        "third_party_processor_income_double_counted",
    ]


def test_runs_every_check_against_the_real_packet() -> None:
    packet = load_packet()
    findings = run_all_checks(packet)

    check_ids = {f.check_id for f in findings}
    assert check_ids == {
        "DEPENDENT_SSN_INDEPENDENT_SOURCE",
        "RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE",
        "THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED",
        "DOCUMENT_TOTAL_DISAGREES_WITH_EXTRACTED_DETAIL",
    }
