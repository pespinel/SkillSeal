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

A category with nothing to evaluate defaults to 100 (nothing found = nothing
deducted), which means a structurally broken skill — missing name and
description entirely — can still average out to a misleadingly high total,
since QUALITY/SECURITY/PORTABILITY have no findings to dock either. Any
SPECIFICATION ERROR (invalid/missing frontmatter, missing name or
description) therefore caps the total at 50: a skill that isn't structurally
valid can't be a passing skill regardless of what the other categories say.
"""

from __future__ import annotations

from skillseal.models import Category, Finding, Severity, Skill, SkillReport

DEDUCTIONS: dict[Severity, int] = {
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

# A structurally invalid skill (bad/missing frontmatter, no name/description)
# can't be a passing skill no matter what the other categories say.
SPEC_ERROR_SCORE_CAP = 50


def category_status(findings: list[Finding]) -> str:
    """Worst-severity status for a category: PASS, WARN, or FAIL."""
    severities = {f.severity for f in findings}
    if Severity.ERROR in severities:
        return "FAIL"
    if Severity.WARNING in severities:
        return "WARN"
    return "PASS"


def score_category(findings: list[Finding]) -> int:
    total = 100 - sum(DEDUCTIONS[f.severity] for f in findings)
    return max(0, min(100, total))


def score_skill(findings: list[Finding]) -> tuple[dict[Category, int], int]:
    category_scores = {
        category: score_category([f for f in findings if f.category == category])
        for category in Category
    }
    total = round(sum(category_scores[c] * WEIGHTS[c] for c in Category))
    has_spec_error = any(
        f.category is Category.SPECIFICATION and f.severity is Severity.ERROR for f in findings
    )
    if has_spec_error:
        total = min(total, SPEC_ERROR_SCORE_CAP)
    return category_scores, total


def build_report(skill: Skill, findings: list[Finding]) -> SkillReport:
    category_scores, total = score_skill(findings)
    return SkillReport(skill=skill, findings=findings, category_scores=category_scores, score=total)
