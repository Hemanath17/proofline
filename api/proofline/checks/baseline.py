"""Runs every check against the real packet and reports precision and
recall against docs/ERRORS.md's confirmed errors. Findings that don't match
a confirmed error are classified as matching a Possible error/lead, or
left unexplained.

The expectations this compares against live in
api/fixtures/baseline_expectations.json -- not inside checks/, so this
file (and its real evidence references) never trips the no-hardcoded-
values grep that's scoped to api/proofline/checks/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from proofline.checks.models import CheckResult
from proofline.checks.runner import run_all_checks
from proofline.packet import Packet, load_packet

_EXPECTATIONS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures"
    / "baseline_expectations.json"
)


def _load_expectations() -> dict:
    with _EXPECTATIONS_PATH.open() as f:
        return json.load(f)


@dataclass
class BaselineReport:
    confirmed_found: list[str] = field(default_factory=list)
    confirmed_missing: list[str] = field(default_factory=list)
    matched_confirmed_findings: list[CheckResult] = field(default_factory=list)
    possible_matches: list[tuple[CheckResult, str]] = field(default_factory=list)
    unexplained: list[CheckResult] = field(default_factory=list)
    total_error_findings: int = 0

    @property
    def recall(self) -> float:
        total = len(self.confirmed_found) + len(self.confirmed_missing)
        return len(self.confirmed_found) / total if total else 0.0

    @property
    def precision(self) -> float:
        if not self.total_error_findings:
            return 0.0
        return len(self.matched_confirmed_findings) / self.total_error_findings


def build_report(packet: Packet | None = None) -> BaselineReport:
    packet = packet or load_packet()
    expectations = _load_expectations()
    findings = run_all_checks(packet)

    confirmed_found: list[str] = []
    confirmed_missing: list[str] = []
    matched_confirmed_findings: list[CheckResult] = []
    matched_ids: set[int] = set()

    for expected in expectations["confirmed"]:
        match = next((f for f in findings if f.check_id == expected["check_id"]), None)
        if match is not None:
            confirmed_found.append(expected["error_id"])
            matched_confirmed_findings.append(match)
            matched_ids.add(id(match))
        else:
            confirmed_missing.append(expected["error_id"])

    remaining = [f for f in findings if id(f) not in matched_ids]

    possible_matches: list[tuple[CheckResult, str]] = []
    unexplained: list[CheckResult] = []
    for finding in remaining:
        finding_refs = set(finding.evidence_refs)
        matched_possible_id = next(
            (
                possible["error_id"]
                for possible in expectations["possible"]
                if finding_refs & set(possible["evidence_refs"])
            ),
            None,
        )
        if matched_possible_id:
            possible_matches.append((finding, matched_possible_id))
        else:
            unexplained.append(finding)

    total_error_findings = len([f for f in findings if f.finding_type == "error"])

    return BaselineReport(
        confirmed_found=confirmed_found,
        confirmed_missing=confirmed_missing,
        matched_confirmed_findings=matched_confirmed_findings,
        possible_matches=possible_matches,
        unexplained=unexplained,
        total_error_findings=total_error_findings,
    )


def print_report(report: BaselineReport | None = None) -> None:
    report = report or build_report()
    total_confirmed = len(report.confirmed_found) + len(report.confirmed_missing)

    print(
        f"Recall: {len(report.confirmed_found)}/{total_confirmed} confirmed errors found"
    )
    if report.confirmed_missing:
        print(f"  Missing: {', '.join(report.confirmed_missing)}")
    print(
        f"Precision: {report.precision:.2f} ({len(report.matched_confirmed_findings)}/{report.total_error_findings} error findings matched a confirmed error)"
    )

    if report.possible_matches:
        print("Findings matching a Possible error or lead:")
        for finding, error_id in report.possible_matches:
            print(f"  {finding.check_id} -> {error_id}")

    if report.unexplained:
        print("Unexplained findings:")
        for finding in report.unexplained:
            print(f"  {finding.check_id}: {finding.observed}")


if __name__ == "__main__":
    print_report()
