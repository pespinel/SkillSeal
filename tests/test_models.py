from pathlib import Path

from skillseal.models import Skill


def test_is_template_via_frontmatter_flag(make_skill) -> None:
    skill = make_skill(
        frontmatter={"name": "my-skill", "description": "xyz", "template": True},
    )
    assert skill.is_template


def test_is_template_via_todo_placeholder_description(make_skill) -> None:
    skill = make_skill(description="TODO")
    assert skill.is_template


def test_is_template_via_bracketed_placeholder_description(make_skill) -> None:
    skill = make_skill(description="Use this skill when [describe the trigger].")
    assert skill.is_template


def test_is_template_via_parent_directory_named_templates(tmp_path: Path) -> None:
    skill_dir = tmp_path / "templates" / "via-dirname"
    skill_dir.mkdir(parents=True)
    skill = Skill(
        name="via-dirname",
        description="xyz",
        frontmatter={"name": "via-dirname", "description": "xyz"},
        body="Body.\n",
        raw_text="---\nname: via-dirname\ndescription: xyz\n---\nBody.\n",
        path=skill_dir / "SKILL.md",
        dir=skill_dir,
    )
    assert skill.is_template


def test_is_not_template_for_a_normal_skill(make_skill) -> None:
    skill = make_skill(description="Use this skill when doing the thing that needs doing.")
    assert not skill.is_template
