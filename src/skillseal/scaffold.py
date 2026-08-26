"""`skillseal init`: scaffold a new skill that scores 100/100 out of the box.

The generated SKILL.md is deliberately full of [bracketed] placeholders, which
Skill.is_template recognizes — so a freshly-scaffolded, unedited skill isn't
scored like a broken production one (see linter.py's suppression list).
"""

from __future__ import annotations

from pathlib import Path

from skillseal.rules.metadata import _NAME_RE

_SKILL_MD_TEMPLATE = """\
---
name: {name}
description: Use this skill when [describe the trigger], to [describe what it accomplishes].
---

# {title}

[Describe what this skill does, in 1-2 sentences.]

## Instructions

1. [First step.]
2. [Second step.]
"""

_SKILLSEAL_YAML_TEMPLATE = """\
version: 1

routing:
  should_trigger:
    - "[a prompt that SHOULD trigger this skill]"
    - "[another prompt that SHOULD trigger this skill]"
    - "[a third prompt that SHOULD trigger this skill]"

  should_not_trigger:
    - "[a prompt that should NOT trigger this skill]"
    - "[another unrelated prompt]"
    - "[a third unrelated prompt]"
"""


class ScaffoldError(Exception):
    """Raised for an invalid name or an already-existing target directory."""


def valid_skill_name(name: str) -> bool:
    return bool(_NAME_RE.match(name))


def scaffold_skill(dest_dir: Path, name: str) -> tuple[Path, Path]:
    """Create dest_dir/SKILL.md and dest_dir/skillseal.yaml. dest_dir must not exist."""
    if not valid_skill_name(name):
        raise ScaffoldError(
            f"invalid name {name!r} — must be lowercase kebab-case "
            "(letters, digits, hyphens), e.g. pdf-form-filler."
        )
    if dest_dir.exists():
        raise ScaffoldError(f"{dest_dir} already exists.")

    dest_dir.mkdir(parents=True)
    title = name.replace("-", " ").title()
    skill_md = dest_dir / "SKILL.md"
    skill_md.write_text(_SKILL_MD_TEMPLATE.format(name=name, title=title), encoding="utf-8")
    skillseal_yaml = dest_dir / "skillseal.yaml"
    skillseal_yaml.write_text(_SKILLSEAL_YAML_TEMPLATE, encoding="utf-8")
    return skill_md, skillseal_yaml
