"""Keeps the Step 3 Done criterion ("no hard-coded packet values in
api/proofline/checks/") enforced automatically, not just checked once by
hand. Scans every check's source text for SSN- and packet-id-shaped string
literals -- the kinds of values a check should always be deriving from the
packet at runtime, never writing in literally."""

import re
from pathlib import Path

import pytest

_CHECKS_DIR = Path(__file__).resolve().parents[2] / "proofline" / "checks"

_FORBIDDEN_PATTERNS = {
    "SSN-shaped literal": re.compile(r"\d{3}-\d{2}-\d{4}"),
    "quoted document id": re.compile(r"""["']D\d{2}["']"""),
    "quoted extracted value id": re.compile(r"""["']ev-\d{4}["']"""),
    "quoted questionnaire/message/call id": re.compile(
        r"""["'](?:qa|msg|call)-\d{2}["']"""
    ),
}


def _check_files() -> list[Path]:
    return sorted(
        path for path in _CHECKS_DIR.glob("*.py") if path.name not in {"__init__.py"}
    )


@pytest.mark.parametrize("path", _check_files(), ids=lambda p: p.name)
def test_no_hardcoded_packet_values(path: Path) -> None:
    source = path.read_text()
    violations = []
    for name, pattern in _FORBIDDEN_PATTERNS.items():
        match = pattern.search(source)
        if match:
            violations.append(f"{name}: {match.group(0)!r}")
    assert violations == [], f"{path.name} has hardcoded packet values: {violations}"
