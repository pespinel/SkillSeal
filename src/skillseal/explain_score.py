"""`--explain-score`: a breakdown of the existing score, not a new number (#24).

Reuses exactly the findings and deductions `scoring.py` already computes for
every category — this adds visibility, not a second scoring model. The
QUALITY section additionally surfaces the description's raw signals (word
count, corpus percentile, when-to-use cue) so a description that currently
scores clean isn't a black box either.
"""

from __future__ import annotations

from dataclasses import dataclass

from skillseal.description_corpus import word_count_percentile
from skillseal.models import Category, Finding, SkillReport
from skillseal.rules.quality import WHEN_CUE_RE
from skillseal.scoring import DEDUCTIONS


@dataclass(frozen=True)
class FindingCost:
    finding: Finding
    points: int


@dataclass(frozen=True)
class CategoryBreakdown:
    category: Category
    score: int
    costs: list[FindingCost]


@dataclass(frozen=True)
class DescriptionSignals:
    word_count: int
    percentile: int
    has_when_cue: bool


def category_breakdown(report: SkillReport, category: Category) -> CategoryBreakdown:
    findings = report.findings_for(category)
    costs = [FindingCost(f, DEDUCTIONS[f.severity]) for f in findings]
    return CategoryBreakdown(category=category, score=report.category_scores[category], costs=costs)


def description_signals(description: str) -> DescriptionSignals:
    word_count = len(description.split())
    return DescriptionSignals(
        word_count=word_count,
        percentile=word_count_percentile(word_count),
        has_when_cue=bool(WHEN_CUE_RE.search(description)),
    )
