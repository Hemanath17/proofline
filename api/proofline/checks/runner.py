"""Discovers and runs every check module in proofline/checks/.

Each module is run on its own: if one raises, that's recorded as a
CheckFailure and the rest keep running, rather than one broken check
taking down the whole run.
"""

from __future__ import annotations

import importlib
import pkgutil
import traceback
from dataclasses import dataclass, field
from types import ModuleType

import proofline.checks as checks_package
from proofline.checks.models import CheckFailure, CheckResult
from proofline.packet import Packet

_EXCLUDED_MODULES = {"models", "runner", "baseline", "money"}


def discover_check_modules() -> list[str]:
    names = [
        module_info.name
        for module_info in pkgutil.iter_modules(checks_package.__path__)
        if module_info.name not in _EXCLUDED_MODULES
    ]
    return sorted(names)


@dataclass
class CheckRunResult:
    findings: list[CheckResult] = field(default_factory=list)
    failures: list[CheckFailure] = field(default_factory=list)


def _run_module(module: ModuleType, packet: Packet) -> list[CheckResult]:
    """Fully materializes and validates the module's findings before
    returning anything, so a generator that raises partway through, or a
    check that returns the wrong type, can't leave a partial or malformed
    result in the caller's findings list."""
    findings = list(module.run(packet))
    for finding in findings:
        if not isinstance(finding, CheckResult):
            raise TypeError(
                f"{module.__name__}.run() returned {finding!r}, not a CheckResult"
            )
    return findings


def run_modules(modules: dict[str, ModuleType], packet: Packet) -> CheckRunResult:
    """Run every given module against the packet, isolating each one so a
    raised exception becomes a CheckFailure instead of stopping the run."""
    result = CheckRunResult()
    for check_id, module in modules.items():
        try:
            findings = _run_module(module, packet)
        except Exception as exc:  # noqa: BLE001 -- a check's failure must not propagate
            result.failures.append(
                CheckFailure(
                    check_id=check_id,
                    error="".join(
                        traceback.format_exception_only(type(exc), exc)
                    ).strip(),
                )
            )
        else:
            result.findings.extend(findings)
    return result


def run_all_checks(packet: Packet) -> CheckRunResult:
    modules = {
        module_name: importlib.import_module(f"proofline.checks.{module_name}")
        for module_name in discover_check_modules()
    }
    return run_modules(modules, packet)
