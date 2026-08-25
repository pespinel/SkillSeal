from pathlib import Path

import pytest

from skillguard.models import Skill


@pytest.fixture
def make_skill(tmp_path: Path):
    def _make(
        name: str = "my-skill",
        description: str = "Use this skill when doing the thing that needs doing.",
        body: str = "# My Skill\n\nDo the thing.\n",
        frontmatter: dict | None = None,
        frontmatter_error: str | None = None,
        dir_name: str = "my-skill",
    ) -> Skill:
        skill_dir = tmp_path / dir_name
        skill_dir.mkdir(exist_ok=True)
        path = skill_dir / "SKILL.md"
        fm = frontmatter if frontmatter is not None else {"name": name, "description": description}
        raw_text = f"---\nname: {name}\ndescription: {description}\n---\n{body}"
        path.write_text(raw_text)
        return Skill(
            name=name if frontmatter_error is None else "",
            description=description if frontmatter_error is None else "",
            frontmatter=fm if frontmatter_error is None else {},
            body=body,
            raw_text=raw_text,
            path=path,
            dir=skill_dir,
            frontmatter_error=frontmatter_error,
        )

    return _make
