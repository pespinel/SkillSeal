from skillseal.models import Category, Finding, Severity
from skillseal.scoring import build_report, category_status, score_category, score_skill


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
    findings = [_finding(Category.SPECIFICATION, Severity.ERROR)]  # SPEC -> 75
    category_scores, total = score_skill(findings)
    assert category_scores[Category.SPECIFICATION] == 75
    assert category_scores[Category.QUALITY] == 100
    # 75*0.30 + 100*0.30 + 100*0.25 + 100*0.15 = 92.5 -> rounds to 92 or 93 (banker's rounding)
    assert total in (92, 93)


def test_build_report_attaches_scores(make_skill) -> None:
    skill = make_skill()
    findings = [_finding(Category.SECURITY, Severity.WARNING)]
    report = build_report(skill, findings)
    assert report.skill is skill
    assert report.findings == findings
    assert report.category_scores[Category.SECURITY] == 90
    assert report.score < 100
