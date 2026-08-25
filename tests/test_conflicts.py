from pathlib import Path

from skillseal.conflicts import find_conflicts


def _write_skill(root: Path, dir_name: str, name: str, description: str) -> None:
    skill_dir = root / dir_name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\nBody.\n"
    )


def test_no_conflicts_for_distinct_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path, "a", "payment-review", "Use this skill when reviewing payment code.")
    _write_skill(tmp_path, "b", "poem-writer", "Use this skill when writing a poem about nature.")

    report = find_conflicts(tmp_path)

    assert report.skills_scanned == 2
    assert not report.has_conflicts


def test_duplicate_name_detected(tmp_path: Path) -> None:
    _write_skill(tmp_path, "a", "helper", "Use this skill when doing task A for the user.")
    _write_skill(tmp_path, "b", "helper", "Use this skill when doing task B for the user.")

    report = find_conflicts(tmp_path)

    assert len(report.duplicate_names) == 1
    assert report.duplicate_names[0].name == "helper"
    assert len(report.duplicate_names[0].paths) == 2


def test_routing_overlap_detected_for_near_duplicate_descriptions(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "a",
        "alpha-reviewer",
        "Use this skill when reviewing pull requests for code quality, style, and bugs.",
    )
    _write_skill(
        tmp_path,
        "b",
        "beta-reviewer",
        "Use this skill when reviewing PRs for code style problems, quality issues, and bugs.",
    )

    report = find_conflicts(tmp_path, threshold=0.3)

    assert len(report.routing_overlaps) == 1
    overlap = report.routing_overlaps[0]
    assert {overlap.skill_a, overlap.skill_b} == {"alpha-reviewer", "beta-reviewer"}
    assert overlap.similarity >= 0.3


def test_unrelated_skills_not_flagged_as_overlap(tmp_path: Path) -> None:
    _write_skill(tmp_path, "a", "payment-review", "Use this skill when reviewing payment code.")
    _write_skill(tmp_path, "b", "poem-writer", "Use this skill when writing a poem about nature.")

    report = find_conflicts(tmp_path, threshold=0.3)

    assert report.routing_overlaps == []


def test_single_skill_has_no_conflicts(tmp_path: Path) -> None:
    _write_skill(tmp_path, "a", "solo-skill", "Use this skill when doing the one thing it does.")

    report = find_conflicts(tmp_path)

    assert report.skills_scanned == 1
    assert not report.has_conflicts


def test_invalid_frontmatter_skill_excluded_from_both_checks(tmp_path: Path) -> None:
    skill_dir = tmp_path / "bad"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: [unclosed\n---\nbody\n")
    _write_skill(tmp_path, "a", "helper", "Use this skill when doing things.")

    report = find_conflicts(tmp_path)

    assert report.skills_scanned == 2
    assert not report.has_conflicts
