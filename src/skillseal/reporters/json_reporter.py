"""Stable JSON schema for `--format json`, for CI integration.

Payloads are hand-built rather than a raw pydantic model_dump() of Skill,
since that would leak the full frontmatter dict and markdown body into every
report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillseal.models import (
    Category,
    ConflictReport,
    Finding,
    RoutingSummary,
    Skill,
    SkillDiff,
    SkillReport,
)
from skillseal.reporters.terminal import display_path
from skillseal.rules.base import RULE_THRESHOLD_FIELD, Rule

SCHEMA_VERSION = 2


def check_reports_to_json(reports: list[SkillReport], root: Path | None = None) -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "skills": [_report_to_dict(r, root) for r in reports]}


def _finding_to_dict(f: Finding) -> dict[str, Any]:
    return {
        "id": f.id,
        "category": f.category.value,
        "severity": f.severity.value,
        "message": f.message,
        "detail": f.detail,
        "line": f.line,
    }


def _report_to_dict(report: SkillReport, root: Path | None) -> dict[str, Any]:
    skill = report.skill
    return {
        "name": skill.name,
        "path": display_path(skill.path, root),
        "score": report.score,
        "category_scores": {c.value: report.category_scores[c] for c in Category},
        "findings": [_finding_to_dict(f) for f in report.findings],
    }


def routing_summaries_to_json(summaries: list[tuple[Skill, RoutingSummary]]) -> dict[str, Any]:
    tested = sum(1 for _, s in summaries if not s.skipped)
    return {
        "version": SCHEMA_VERSION,
        "skills_scanned": len(summaries),
        "skills_with_tests": tested,
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


def conflict_report_to_json(report: ConflictReport, root: Path | None = None) -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "threshold": report.threshold,
        "skills_scanned": report.skills_scanned,
        "has_conflicts": report.has_conflicts,
        "duplicate_names": [
            {
                "name": d.name,
                "paths": [display_path(p, root) for p in d.paths],
            }
            for d in report.duplicate_names
        ],
        "routing_overlaps": [
            {
                "skill_a": o.skill_a,
                "skill_b": o.skill_b,
                "path_a": display_path(o.path_a, root),
                "path_b": display_path(o.path_b, root),
                "similarity": o.similarity,
                "shared_terms": o.shared_terms,
            }
            for o in report.routing_overlaps
        ],
    }


def skill_diff_to_json(diff: SkillDiff, root: Path | None = None) -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "old": _report_to_dict(diff.old, root),
        "new": _report_to_dict(diff.new, root),
        "score_delta": diff.score_delta,
        "regressed": diff.regressed,
        "added": [_finding_to_dict(f) for f in diff.added],
        "removed": [_finding_to_dict(f) for f in diff.removed],
    }


def rules_to_json(rules: list[Rule]) -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "rules": [
            {
                "id": r.id,
                "category": r.category.value,
                "severity": r.severity.value,
                "description": r.description,
                "configurable": r.id in RULE_THRESHOLD_FIELD,
                "threshold_field": RULE_THRESHOLD_FIELD.get(r.id),
            }
            for r in sorted(rules, key=lambda r: r.id)
        ],
    }
