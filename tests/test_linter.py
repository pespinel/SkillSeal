from skillseal.linter import lint_skill


def test_template_suppresses_incomplete_description_findings(make_skill) -> None:
    skill = make_skill(
        description="TODO",
        body="Body not written yet. See [notes](./notes.md) for context.\n",
    )
    report = lint_skill(skill)

    ids = {f.id for f in report.findings}
    assert "detected-as-template" in ids
    assert "description-too-short" not in ids
    assert "description-missing-when-to-use" not in ids
    assert "dangling-file-reference" not in ids
    assert report.score == 100


def test_non_template_does_not_suppress_the_same_findings(make_skill) -> None:
    skill = make_skill(
        description="xyz",
        body="Body not written yet. See [notes](./notes.md) for context.\n",
    )
    report = lint_skill(skill)

    ids = {f.id for f in report.findings}
    assert "detected-as-template" not in ids
    assert "description-too-short" in ids
    assert "description-missing-when-to-use" in ids
    assert "dangling-file-reference" in ids
    assert report.score < 100
