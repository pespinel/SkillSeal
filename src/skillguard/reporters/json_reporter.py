"""Stable JSON schema for `--format json`, for CI integration.

Payloads are hand-built rather than a raw pydantic model_dump() of Skill,
since that would leak the full frontmatter dict and markdown body into every
report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillguard.models import Category, RoutingSummary, Skill, SkillReport
from skillguard.reporters.terminal import display_path

SCHEMA_VERSION = 1


def check_reports_to_json(reports: list[SkillReport], root: Path | None = None) -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "skills": [_report_to_dict(r, root) for r in reports]}


def _report_to_dict(report: SkillReport, root: Path | None) -> dict[str, Any]:
    skill = report.skill
    return {
        "name": skill.name,
        "path": display_path(skill.path, root),
        "score": report.score,
        "category_scores": {c.value: report.category_scores[c] for c in Category},
        "findings": [
            {
                "id": f.id,
                "category": f.category.value,
                "severity": f.severity.value,
                "message": f.message,
                "detail": f.detail,
            }
            for f in report.findings
        ],
    }


def routing_summaries_to_json(summaries: list[tuple[Skill, RoutingSummary]]) -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "skills": [_summary_to_dict(skill, s) for skill, s in summaries],
    }


def _summary_to_dict(skill: Skill, summary: RoutingSummary) -> dict[str, Any]:
    should_trigger = summary.should_trigger_results
    should_not_trigger = summary.should_not_trigger_results
    return {
        "name": skill.name or skill.dir_name,
        "skipped": summary.skipped,
        "skip_reason": summary.skip_reason,
        "threshold": summary.threshold,
        "accuracy": summary.accuracy,
        "passed": summary.passed,
        "should_trigger": {
            "total": len(should_trigger),
            "passed": sum(1 for r in should_trigger if r.passed),
        },
        "should_not_trigger": {
            "total": len(should_not_trigger),
            "passed": sum(1 for r in should_not_trigger if r.passed),
        },
        "results": [
            {
                "prompt": r.prompt,
                "expected": r.expected,
                "actual": r.actual,
                "confidence": r.confidence,
                "reason": r.reason,
                "passed": r.passed,
            }
            for r in summary.results
        ],
    }
