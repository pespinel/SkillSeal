from pathlib import Path

from skillguard.parser import discover_skills, parse_skill

GOOD_SKILL = """---
name: my-skill
description: Use this skill when doing the thing.
---

# My Skill

Body text.
"""


def test_parse_skill_valid_frontmatter(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(GOOD_SKILL)

    skill = parse_skill(skill_file)

    assert skill.name == "my-skill"
    assert skill.description == "Use this skill when doing the thing."
    assert skill.frontmatter_error is None
    assert "# My Skill" in skill.body


def test_parse_skill_invalid_yaml(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\nname: [unclosed\n---\nbody\n")

    skill = parse_skill(skill_file)

    assert skill.frontmatter_error is not None
    assert skill.name == ""


def test_parse_skill_non_mapping_frontmatter(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\n- one\n- two\n---\nbody\n")

    skill = parse_skill(skill_file)

    assert skill.frontmatter_error is not None


def test_parse_skill_missing_frontmatter(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# No frontmatter here\n")

    skill = parse_skill(skill_file)

    assert skill.frontmatter_error is None
    assert skill.frontmatter == {}
    assert skill.name == ""


def test_discover_skills_recursive(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "SKILL.md").write_text(GOOD_SKILL)
    (tmp_path / "b" / "nested").mkdir(parents=True)
    (tmp_path / "b" / "nested" / "SKILL.md").write_text(GOOD_SKILL)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "SKILL.md").write_text(GOOD_SKILL)

    found = discover_skills(tmp_path)

    assert len(found) == 2
    assert found == sorted(found)


def test_discover_skills_direct_file(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(GOOD_SKILL)

    assert discover_skills(skill_file) == [skill_file]


def test_discover_skills_non_skill_file(tmp_path: Path) -> None:
    other = tmp_path / "README.md"
    other.write_text("hello")

    assert discover_skills(other) == []


def test_discover_skills_nonexistent_path(tmp_path: Path) -> None:
    assert discover_skills(tmp_path / "does-not-exist") == []
