from skillseal.explain_score import category_breakdown, description_signals
from skillseal.linter import lint_skill
from skillseal.models import Category


def test_category_breakdown_lists_findings_and_costs(make_skill) -> None:
    skill = make_skill(description="Helps with tasks.")  # vague-phrase hit -> WARNING
    report = lint_skill(skill)

    breakdown = category_breakdown(report, Category.QUALITY)

    assert breakdown.score == report.category_scores[Category.QUALITY]
    ids = {c.finding.id for c in breakdown.costs}
    assert "description-too-vague" in ids
    vague_cost = next(c for c in breakdown.costs if c.finding.id == "description-too-vague")
    assert vague_cost.points == 10


def test_category_breakdown_empty_when_no_findings(make_skill) -> None:
    skill = make_skill()
    report = lint_skill(skill)

    breakdown = category_breakdown(report, Category.SECURITY)

    assert breakdown.costs == []
    assert breakdown.score == 100


def test_description_signals_word_count_and_when_cue() -> None:
    sig = description_signals("Use this skill when reviewing payment code for security issues.")
    assert sig.word_count == 10
    assert sig.has_when_cue is True


def test_description_signals_no_when_cue() -> None:
    sig = description_signals("Reviews payment code for correctness and security.")
    assert sig.has_when_cue is False
