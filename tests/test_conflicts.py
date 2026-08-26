from pathlib import Path

from skillseal.conflicts import (
    _containment,
    _edit_distance_le_1,
    _is_near_duplicate_name,
    _jaccard,
    find_conflicts,
)


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


# --- pure helpers -----------------------------------------------------------


def test_containment_is_asymmetric_length_insensitive() -> None:
    small = {"payment", "audit", "code"}
    big = {"payment", "audit", "code", "compliance", "encryption", "tokenization", "merchant"}
    assert _jaccard(small, big) < 0.5
    assert _containment(small, big) == 1.0


def test_edit_distance_le_1_substitution() -> None:
    assert _edit_distance_le_1("code-review", "code-reviaw")


def test_edit_distance_le_1_insertion() -> None:
    assert _edit_distance_le_1("code-review", "code-reviews")


def test_edit_distance_of_2_is_not_le_1() -> None:
    # "reviewer" needs two insertions ("er") over "review" - deliberately out
    # of scope for the Levenshtein-1/normalized-form heuristic.
    assert not _edit_distance_le_1("code-review", "code-reviewer")


def test_is_near_duplicate_name_normalized_separators() -> None:
    assert _is_near_duplicate_name("code-review", "code_review")


def test_is_near_duplicate_name_exact_match_is_not_near_duplicate() -> None:
    assert not _is_near_duplicate_name("code-review", "code-review")


def test_is_near_duplicate_name_unrelated_names() -> None:
    assert not _is_near_duplicate_name("code-review", "poem-writer")


# --- find_conflicts integration ---------------------------------------------


def test_near_duplicate_name_detected(tmp_path: Path) -> None:
    _write_skill(tmp_path, "a", "code-review", "Use this skill when reviewing pull requests.")
    _write_skill(tmp_path, "b", "code_review", "Use this skill when writing a poem about trees.")

    report = find_conflicts(tmp_path)

    assert len(report.near_duplicate_names) == 1
    nd = report.near_duplicate_names[0]
    assert {nd.name_a, nd.name_b} == {"code-review", "code_review"}


def test_exact_duplicate_name_not_also_reported_as_near_duplicate(tmp_path: Path) -> None:
    _write_skill(tmp_path, "a", "helper", "Use this skill when doing task A for the user.")
    _write_skill(tmp_path, "b", "helper", "Use this skill when doing task B for the user.")

    report = find_conflicts(tmp_path)

    assert report.near_duplicate_names == []


_VAGUE_DESC = "Use this skill when reviewing payment code for security issues."
_SPECIFIC_DESC = (
    "Use this skill when reviewing payment code for security issues, checking "
    "encryption of card numbers, validating tokenization flows, and auditing "
    "merchant account configurations for PCI compliance across the pipeline."
)


def test_containment_overlap_detected_for_vague_subset(tmp_path: Path) -> None:
    _write_skill(tmp_path, "a", "quick-check", _VAGUE_DESC)
    _write_skill(tmp_path, "b", "thorough-audit", _SPECIFIC_DESC)

    report = find_conflicts(tmp_path, threshold=0.9, containment_threshold=0.7)

    assert report.routing_overlaps == []
    assert len(report.containment_overlaps) == 1
    co = report.containment_overlaps[0]
    assert {co.skill_a, co.skill_b} == {"quick-check", "thorough-audit"}
    assert co.containment > co.jaccard
    assert co.containment >= 0.7


def test_containment_overlap_not_double_reported_when_also_routing_overlap(
    tmp_path: Path,
) -> None:
    _write_skill(tmp_path, "a", "quick-check", _VAGUE_DESC)
    _write_skill(tmp_path, "b", "thorough-audit", _SPECIFIC_DESC)

    report = find_conflicts(tmp_path, threshold=0.1, containment_threshold=0.1)

    assert len(report.routing_overlaps) == 1
    assert report.containment_overlaps == []
