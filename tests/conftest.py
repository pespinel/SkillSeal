from pathlib import Path

import pytest

from skillseal.models import Skill


@pytest.fixture
def make_skill(tmp_path: Path):
    def _make(
        name: str = "my-skill",
        description: str = "Use this skill when doing the thing that needs doing.",
        body: str = "# My Skill\n\nDo the thing.\n",
        frontmatter: dict | None = None,
        frontmatter_error: str | None = None,
        frontmatter_error_kind: str | None = None,
        dir_name: str = "my-skill",
    ) -> Skill:
        skill_dir = tmp_path / dir_name
        skill_dir.mkdir(exist_ok=True)
        path = skill_dir / "SKILL.md"
        fm = frontmatter if frontmatter is not None else {"name": name, "description": description}
        # Built from `fm` (not hardcoded to name/description) so frontmatter_text
        # stays positionally consistent with whatever a test overrides — line-number
        # lookups (frontmatter_key_line) rely on this actually matching.
        frontmatter_lines = "".join(f"{k}: {v}\n" for k, v in fm.items())
        raw_text = f"---\n{frontmatter_lines}---\n{body}"
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
            frontmatter_error_kind=(
                frontmatter_error_kind
                if frontmatter_error_kind is not None
                else ("invalid-frontmatter" if frontmatter_error is not None else None)
            ),
            frontmatter_text=frontmatter_lines if frontmatter_error is None else "",
        )

    return _make
