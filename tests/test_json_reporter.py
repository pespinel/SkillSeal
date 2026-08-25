from skillseal.models import Category, RoutingCaseResult, RoutingSummary, Severity
from skillseal.reporters.json_reporter import check_reports_to_json, routing_summaries_to_json
from skillseal.scoring import build_report


def test_check_reports_to_json_schema(make_skill) -> None:
    skill = make_skill()
    from skillseal.models import Finding

    finding = Finding(
        id="test-id", category=Category.SECURITY, severity=Severity.WARNING, message="msg", line=7
    )
    report = build_report(skill, [finding])

    payload = check_reports_to_json([report], root=skill.dir)

    assert payload["version"] == 2
    assert len(payload["skills"]) == 1
    entry = payload["skills"][0]
    assert entry["name"] == skill.name
    assert entry["path"] == "SKILL.md"
    assert entry["score"] == report.score
    assert set(entry["category_scores"]) == {c.value for c in Category}
    assert entry["findings"] == [
        {
            "id": "test-id",
            "category": "SECURITY",
            "severity": "WARNING",
            "message": "msg",
            "detail": None,
            "line": 7,
        }
    ]
    # frontmatter/body must not leak into the payload
    assert "frontmatter" not in entry
    assert "body" not in entry


def test_routing_summaries_to_json_schema(make_skill) -> None:
    skill = make_skill()
    summary = RoutingSummary(
        skill_name=skill.name,
        threshold=0.9,
        results=[
            RoutingCaseResult(
                prompt="hi", expected=True, actual=True, confidence=1.0, reason="matched"
            ),
        ],
    )

    payload = routing_summaries_to_json([(skill, summary)])

    assert payload["version"] == 2
    assert payload["skills_scanned"] == 1
    assert payload["skills_with_tests"] == 1
    entry = payload["skills"][0]
    assert entry["name"] == skill.name
    assert entry["should_trigger"] == {"total": 1, "passed": 1}
    assert entry["should_not_trigger"] == {"total": 0, "passed": 0}
    assert entry["accuracy"] == 1.0
    assert entry["passed"] is True
