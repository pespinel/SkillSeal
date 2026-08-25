"""Deterministic 0-100 scoring.

Each category starts at 100 and loses points per finding:
  ERROR   -25
  WARNING -10
  INFO     -0   (purely informational findings never cost points)

Rules aggregate repeated occurrences of the same issue into a single finding
(see rules/*.py), so a category realistically accumulates a handful of
findings at most — no additional per-category cap is needed beyond the 0 floor.

The total score is a weighted sum of the four category scores:
  SPECIFICATION 30%  QUALITY 30%  SECURITY 25%  PORTABILITY 15%

Specification and quality carry the most weight because they most directly
determine whether a skill is usable and routes reliably; security is weighted
close behind since it flags real risk; portability is weighted lowest because
declared environment dependencies are often expected, not defects.
"""

from __future__ import annotations

from skillseal.models import Category, Finding, Severity, Skill, SkillReport

_DEDUCTIONS: dict[Severity, int] = {
    Severity.ERROR: 25,
    Severity.WARNING: 10,
    Severity.INFO: 0,
}

WEIGHTS: dict[Category, float] = {
    Category.SPECIFICATION: 0.30,
    Category.QUALITY: 0.30,
    Category.SECURITY: 0.25,
    Category.PORTABILITY: 0.15,
}

_STATUS_ORDER = [Severity.ERROR, Severity.WARNING, Severity.INFO]


def category_status(findings: list[Finding]) -> str:
    """Worst-severity status for a category: PASS, WARN, or FAIL."""
    severities = {f.severity for f in findings}
    if Severity.ERROR in severities:
        return "FAIL"
    if Severity.WARNING in severities:
        return "WARN"
    return "PASS"


def score_category(findings: list[Finding]) -> int:
    total = 100 - sum(_DEDUCTIONS[f.severity] for f in findings)
    return max(0, min(100, total))


def score_skill(findings: list[Finding]) -> tuple[dict[Category, int], int]:
    category_scores = {
        category: score_category([f for f in findings if f.category == category])
        for category in Category
    }
    total = sum(category_scores[c] * WEIGHTS[c] for c in Category)
    return category_scores, round(total)


def build_report(skill: Skill, findings: list[Finding]) -> SkillReport:
    category_scores, total = score_skill(findings)
    return SkillReport(skill=skill, findings=findings, category_scores=category_scores, score=total)
