"""Discovers and runs every check module in proofline/checks/."""

from __future__ import annotations

import importlib
import pkgutil

import proofline.checks as checks_package
from proofline.checks.models import CheckResult
from proofline.packet import Packet

_EXCLUDED_MODULES = {"models", "runner", "baseline"}


def discover_check_modules() -> list[str]:
    names = [
        module_info.name
        for module_info in pkgutil.iter_modules(checks_package.__path__)
        if module_info.name not in _EXCLUDED_MODULES
    ]
    return sorted(names)


def run_all_checks(packet: Packet) -> list[CheckResult]:
    findings: list[CheckResult] = []
    for module_name in discover_check_modules():
        module = importlib.import_module(f"proofline.checks.{module_name}")
        findings.extend(module.run(packet))
    return findings
