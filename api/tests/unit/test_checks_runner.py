from types import SimpleNamespace

from proofline.checks.models import CheckResult
from proofline.checks.runner import discover_check_modules, run_all_checks, run_modules
from proofline.packet import load_packet

from tests.unit.factories import minimal_packet


def test_discovers_every_check_module() -> None:
    assert discover_check_modules() == [
        "dependent_ssn_independent_source",
        "document_total_disagrees_with_extracted_detail",
        "rsu_lot_zero_basis_supplement_available",
        "third_party_processor_income_double_counted",
    ]


def test_runs_every_check_against_the_real_packet() -> None:
    packet = load_packet()
    result = run_all_checks(packet)

    check_ids = {f.check_id for f in result.findings}
    assert check_ids == {
        "DEPENDENT_SSN_INDEPENDENT_SOURCE",
        "RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE",
        "THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED",
        "DOCUMENT_TOTAL_DISAGREES_WITH_EXTRACTED_DETAIL",
    }
    assert result.failures == []


def _ok_module(check_id: str, finding: CheckResult) -> SimpleNamespace:
    return SimpleNamespace(run=lambda packet: [finding])


def _broken_module(error: Exception) -> SimpleNamespace:
    def run(packet):
        raise error

    return SimpleNamespace(run=run)


def test_one_failing_check_does_not_stop_the_others() -> None:
    packet = minimal_packet()
    good_finding = CheckResult(
        check_id="GOOD_CHECK",
        check_version=1,
        area="identity",
        scope="return",
        finding_type="possible_discrepancy",
        severity="info",
        observed="fine",
        expected="fine",
        tax_effect=None,
        limitations="none",
        recommended_action="none",
    )
    modules = {
        "good_check": _ok_module("GOOD_CHECK", good_finding),
        "broken_check": _broken_module(ValueError("boom")),
    }

    result = run_modules(modules, packet)

    assert result.findings == [good_finding]
    assert len(result.failures) == 1
    assert result.failures[0].check_id == "broken_check"
    assert "boom" in result.failures[0].error


def _generator_module_that_raises_partway(finding: CheckResult) -> SimpleNamespace:
    def run(packet):
        yield finding
        raise ValueError("boom partway through")

    return SimpleNamespace(run=run)


def test_a_generator_that_raises_partway_leaves_no_partial_findings() -> None:
    """A check that returns a generator instead of a plain list must not be
    able to leave some of its findings in the result while also being
    recorded as failed -- it's either fully in, or fully a CheckFailure."""
    packet = minimal_packet()
    good_finding = CheckResult(
        check_id="GOOD_CHECK",
        check_version=1,
        area="identity",
        scope="return",
        finding_type="possible_discrepancy",
        severity="info",
        observed="fine",
        expected="fine",
        tax_effect=None,
        limitations="none",
        recommended_action="none",
    )
    modules = {
        "half_broken": _generator_module_that_raises_partway(good_finding),
    }

    result = run_modules(modules, packet)

    assert result.findings == []
    assert len(result.failures) == 1
    assert result.failures[0].check_id == "half_broken"


def test_a_check_returning_the_wrong_type_is_a_failure_not_a_finding() -> None:
    """A check module with a bug that returns something other than
    CheckResult objects must be isolated as a CheckFailure, not silently
    pollute the findings list with malformed data."""
    packet = minimal_packet()
    modules = {
        "wrong_type": SimpleNamespace(run=lambda packet: ["not a CheckResult"]),
    }

    result = run_modules(modules, packet)

    assert result.findings == []
    assert len(result.failures) == 1
    assert result.failures[0].check_id == "wrong_type"
