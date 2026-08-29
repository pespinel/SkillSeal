"""SARIF 2.1.0 output for `skillseal check --format sarif`.

Lights up GitHub code scanning: a finding shows up as a code-scanning alert
on the file/line it fired on, not just a CI log line.
https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.json
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillseal import __version__
from skillseal.models import Severity, SkillReport
from skillseal.reporters.terminal import display_path
from skillseal.rules.base import Rule, build_registry

_LEVEL = {Severity.INFO: "note", Severity.WARNING: "warning", Severity.ERROR: "error"}
_SCHEMA_URI = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
)
_INFORMATION_URI = "https://github.com/pespinel/SkillSeal"


def _rule_descriptor(rule: Rule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.id,
        "shortDescription": {"text": rule.description},
        "defaultConfiguration": {"level": _LEVEL[rule.severity]},
    }


def _results_for(report: SkillReport, root: Path | None) -> list[dict[str, Any]]:
    file = display_path(report.skill.path, root)
    results = []
    for f in report.findings:
        message = f.message if not f.detail else f"{f.message} ({f.detail})"
        # GitHub code scanning requires region.startLine on every location; a
        # handful of rules (e.g. too-many-responsibilities) have no specific
        # line, so those point at line 1 rather than omitting the region.
        physical_location: dict[str, Any] = {
            "artifactLocation": {"uri": file},
            "region": {"startLine": f.line or 1},
        }
        results.append(
            {
                "ruleId": f.id,
                "level": _LEVEL[f.severity],
                "message": {"text": message},
                "locations": [{"physicalLocation": physical_location}],
            }
        )
    return results


def check_reports_to_sarif(reports: list[SkillReport], root: Path | None = None) -> dict[str, Any]:
    return {
        "$schema": _SCHEMA_URI,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "SkillSeal",
                        "informationUri": _INFORMATION_URI,
                        "version": __version__,
                        "rules": [_rule_descriptor(r) for r in build_registry()],
                    }
                },
                "results": [r for report in reports for r in _results_for(report, root)],
            }
        ],
    }
