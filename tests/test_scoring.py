from skillseal.models import Category, Finding, Severity
from skillseal.scoring import (
    SPEC_ERROR_SCORE_CAP,
    build_report,
    category_status,
    score_category,
    score_skill,
)


def _finding(category: Category, severity: Severity) -> Finding:
    return Finding(id="test-id", category=category, severity=severity, message="msg")


def test_score_category_no_findings_is_100() -> None:
    assert score_category([]) == 100


def test_score_category_deducts_by_severity() -> None:
    findings = [_finding(Category.SECURITY, Severity.ERROR)]
    assert score_category(findings) == 75  # 100 - 25


def test_score_category_info_deducts_nothing() -> None:
    findings = [_finding(Category.PORTABILITY, Severity.INFO) for _ in range(5)]
    assert score_category(findings) == 100


def test_score_category_floors_at_zero() -> None:
    findings = [_finding(Category.SECURITY, Severity.ERROR) for _ in range(10)]
    assert score_category(findings) == 0


def test_category_status() -> None:
    assert category_status([]) == "PASS"
    assert category_status([_finding(Category.QUALITY, Severity.INFO)]) == "PASS"
    assert category_status([_finding(Category.QUALITY, Severity.WARNING)]) == "WARN"
    assert category_status([_finding(Category.QUALITY, Severity.ERROR)]) == "FAIL"


def test_score_skill_is_deterministic_and_weighted() -> None:
    # a WARNING (not ERROR) in a non-SPECIFICATION category doesn't trigger
    # the spec-error cap, so the plain weighted-average arithmetic applies.
    findings = [_finding(Category.SECURITY, Severity.WARNING)]  # SECURITY -> 90
    category_scores, total = score_skill(findings)
    assert category_scores[Category.SECURITY] == 90
    assert category_scores[Category.QUALITY] == 100
    # 100*0.30 + 100*0.30 + 90*0.25 + 100*0.15 = 97.5 -> rounds to 97 or 98 (banker's rounding)
    assert total in (97, 98)


def test_spec_error_caps_total_score_regardless_of_other_categories() -> None:
    # a structurally invalid skill can't be a passing skill just because
    # QUALITY/SECURITY/PORTABILITY have nothing to deduct from (see #13).
    findings = [_finding(Category.SPECIFICATION, Severity.ERROR)]
    category_scores, total = score_skill(findings)
    assert category_scores[Category.SPECIFICATION] == 75
    assert category_scores[Category.QUALITY] == 100  # unaffected, still granular
    assert total == SPEC_ERROR_SCORE_CAP


def test_spec_error_cap_does_not_raise_an_already_lower_score() -> None:
    # the cap is a ceiling (min), not a floor: when the plain weighted
    # average is already below it, the cap must not pull the score back up.
    findings = [
        _finding(Category.SPECIFICATION, Severity.ERROR),
        *[_finding(Category.QUALITY, Severity.ERROR) for _ in range(4)],
        *[_finding(Category.SECURITY, Severity.ERROR) for _ in range(4)],
        *[_finding(Category.PORTABILITY, Severity.ERROR) for _ in range(4)],
    ]
    _, total = score_skill(findings)
    assert total < SPEC_ERROR_SCORE_CAP


def test_build_report_attaches_scores(make_skill) -> None:
    skill = make_skill()
    findings = [_finding(Category.SECURITY, Severity.WARNING)]
    report = build_report(skill, findings)
    assert report.skill is skill
    assert report.findings == findings
    assert report.category_scores[Category.SECURITY] == 90
    assert report.score < 100
