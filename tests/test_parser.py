from pathlib import Path

from skillseal.parser import discover_skills, parse_skill

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

    assert skill.frontmatter_error is not None
    assert skill.frontmatter_error_kind == "missing-frontmatter"
    assert skill.frontmatter == {}
    assert skill.name == ""


def test_parse_skill_strips_leading_bom(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("\ufeff" + GOOD_SKILL)

    skill = parse_skill(skill_file)

    assert skill.frontmatter_error is None
    assert skill.name == "my-skill"


def test_parse_skill_frontmatter_not_at_start(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("\n" + GOOD_SKILL)

    skill = parse_skill(skill_file)

    assert skill.frontmatter_error_kind == "frontmatter-not-at-start"
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


def test_discover_skills_finds_skills_under_dot_claude(tmp_path: Path) -> None:
    # .claude/skills/<name>/SKILL.md is Claude Code's own canonical location
    # for personal/project skills — blanket-skipping every dotdir used to
    # make every skill there invisible to `check` (found via a real-world
    # scan: "no SKILL.md files found" against a repo that had one there)
    skill_dir = tmp_path / ".claude" / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(GOOD_SKILL)

    found = discover_skills(tmp_path)

    assert found == [skill_dir / "SKILL.md"]


def test_discover_skills_finds_skills_under_dot_github(tmp_path: Path) -> None:
    # .github/plugins/.../skills/ is a real convention too (seen in a real
    # microsoft/azure-skills scan)
    skill_dir = tmp_path / ".github" / "plugins" / "my-plugin" / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(GOOD_SKILL)

    found = discover_skills(tmp_path)

    assert found == [skill_dir / "SKILL.md"]


def test_discover_skills_still_skips_vcs_and_cache_dirs(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "SKILL.md").write_text(GOOD_SKILL)
    for skip_dir in (".git", ".venv", "node_modules", "__pycache__", ".tox", ".mypy_cache"):
        d = tmp_path / skip_dir / "not-a-skill"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(GOOD_SKILL)

    found = discover_skills(tmp_path)

    assert found == [tmp_path / "real" / "SKILL.md"]


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


def test_discover_skills_ignores_skill_md_nested_under_another_skill(tmp_path: Path) -> None:
    (tmp_path / "my-skill" / "references").mkdir(parents=True)
    (tmp_path / "my-skill" / "SKILL.md").write_text(GOOD_SKILL)
    (tmp_path / "my-skill" / "references" / "SKILL.md").write_text(GOOD_SKILL)

    found = discover_skills(tmp_path)

    assert found == [tmp_path / "my-skill" / "SKILL.md"]
