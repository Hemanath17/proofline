from proofline.checks.baseline import build_report
from proofline.packet import load_packet


def test_baseline_recall_is_four_of_four_on_the_real_packet() -> None:
    report = build_report(load_packet())

    assert sorted(report.confirmed_found) == ["E1", "E2", "E3", "E4"]
    assert report.confirmed_missing == []
    assert report.recall == 1.0


def test_baseline_precision_on_the_real_packet() -> None:
    report = build_report(load_packet())

    assert report.precision == 1.0
    assert report.unexplained == []
