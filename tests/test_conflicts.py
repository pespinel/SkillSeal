from pathlib import Path

from skillseal.conflicts import find_conflicts


def _write_skill(
    root: Path, dir_name: str, name: str, description: str, extra_frontmatter: str = ""
) -> None:
    skill_dir = root / dir_name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n{extra_frontmatter}---\nBody.\n"
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


def test_conflict_ignore_suppresses_routing_overlap(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "a",
        "alpha-reviewer",
        "Use this skill when reviewing pull requests for code quality, style, and bugs.",
        extra_frontmatter="conflict_ignore:\n  - beta-reviewer\n",
    )
    _write_skill(
        tmp_path,
        "b",
        "beta-reviewer",
        "Use this skill when reviewing PRs for code style problems, quality issues, and bugs.",
    )

    report = find_conflicts(tmp_path, threshold=0.3)

    assert report.routing_overlaps == []


def test_conflict_ignore_does_not_over_match_by_substring(tmp_path: Path) -> None:
    # regression: a short conflict_ignore entry must not silently suppress
    # comparisons against unrelated skills just because it's a substring of
    # their path (e.g. "e" matching almost any directory name).
    _write_skill(
        tmp_path,
        "a",
        "alpha-reviewer",
        "Use this skill when reviewing pull requests for code quality, style, and bugs.",
        extra_frontmatter='conflict_ignore:\n  - "e"\n',
    )
    _write_skill(
        tmp_path,
        "b",
        "beta-reviewer",
        "Use this skill when reviewing PRs for code style problems, quality issues, and bugs.",
    )

    report = find_conflicts(tmp_path, threshold=0.3)

    assert len(report.routing_overlaps) == 1


def test_against_only_reports_pairs_involving_target(tmp_path: Path) -> None:
    target_root = tmp_path / "target"
    corpus_root = tmp_path / "corpus"
    target_root.mkdir()
    corpus_root.mkdir()

    _write_skill(
        target_root,
        "new-skill",
        "gamma-reviewer",
        "Use this skill when reviewing pull requests for code quality, style, and bugs.",
    )
    _write_skill(
        corpus_root,
        "alpha",
        "alpha-reviewer",
        "Use this skill when reviewing PRs for code style problems, quality issues, and bugs.",
    )
    # a duplicate name that exists entirely within the corpus, unrelated to the target skill
    _write_skill(
        corpus_root,
        "alpha-2",
        "alpha-reviewer",
        "Use this skill when doing something completely unrelated to reviews.",
    )

    report = find_conflicts(target_root, threshold=0.3, against=corpus_root)

    assert report.skills_scanned == 1
    # the pre-existing corpus-internal duplicate must not be reported
    assert report.duplicate_names == []
    assert len(report.routing_overlaps) == 1
    assert {report.routing_overlaps[0].skill_a, report.routing_overlaps[0].skill_b} == {
        "gamma-reviewer",
        "alpha-reviewer",
    }
