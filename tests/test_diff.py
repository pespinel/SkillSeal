from pathlib import Path

import pytest

from skillseal.diff import DiffTargetError, diff_skills


def _write_skill(root: Path, version: str, name: str, description: str, body: str = "") -> Path:
    # `name` is also the leaf directory name, so frontmatter 'name' matches the
    # skill's directory - a mismatch is a SPECIFICATION ERROR (caps score at 50)
    # and would swamp the description-quality deltas these tests exercise.
    skill_dir = root / version / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}"
    )
    return skill_dir


def test_diff_detects_improvement(tmp_path: Path) -> None:
    old = _write_skill(tmp_path, "old", "helper", "Helps with tasks.")
    new = _write_skill(
        tmp_path,
        "new",
        "helper",
        "Use this skill when the user needs help completing a specific task.",
    )

    diff = diff_skills(old, new)

    assert diff.score_delta > 0
    assert not diff.regressed
    assert any(f.id == "description-too-vague" for f in diff.removed)
    assert diff.added == []


def test_diff_detects_regression(tmp_path: Path) -> None:
    old = _write_skill(
        tmp_path,
        "old",
        "helper",
        "Use this skill when the user needs help completing a specific task.",
    )
    new = _write_skill(tmp_path, "new", "helper", "Helps with tasks.")

    diff = diff_skills(old, new)

    assert diff.score_delta < 0
    assert diff.regressed
    assert any(f.id == "description-too-vague" for f in diff.added)


def test_diff_no_changes(tmp_path: Path) -> None:
    old = _write_skill(tmp_path, "old", "helper", "Use this skill when doing a specific task.")
    new = _write_skill(tmp_path, "new", "helper", "Use this skill when doing a specific task.")

    diff = diff_skills(old, new)

    assert diff.score_delta == 0
    assert not diff.regressed
    assert diff.added == []
    assert diff.removed == []


def test_diff_target_must_resolve_to_exactly_one_skill(tmp_path: Path) -> None:
    old = _write_skill(tmp_path, "old", "helper", "Use this skill when doing things.")
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(DiffTargetError):
        diff_skills(old, empty_dir)
