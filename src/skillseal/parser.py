"""Discovery and parsing of SKILL.md files into Skill models."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from skillseal.models import Skill

_SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__"}
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\r?\n?", re.DOTALL)


def discover_skills(path: Path) -> list[Path]:
    """Find SKILL.md files under `path`.

    `path` may point directly at a SKILL.md file, at a single skill directory,
    or at a directory containing many skill directories.
    """
    path = Path(path)
    if path.is_file():
        return [path] if path.name == "SKILL.md" else []
    if not path.is_dir():
        return []

    found: list[Path] = []
    for candidate in path.rglob("SKILL.md"):
        rel_parts = candidate.relative_to(path).parts[:-1]
        if any(part in _SKIP_DIRS or part.startswith(".") for part in rel_parts):
            continue
        found.append(candidate)
    return sorted(found)


def parse_skill(path: Path) -> Skill:
    """Parse a SKILL.md file into a Skill. Never raises on malformed frontmatter."""
    raw_text = path.read_text(encoding="utf-8")

    match = _FRONTMATTER_RE.match(raw_text)
    if match is None:
        return Skill(
            name="",
            description="",
            frontmatter={},
            body=raw_text,
            raw_text=raw_text,
            path=path,
            dir=path.parent,
            frontmatter_error=None,
        )

    body = raw_text[match.end() :]
    frontmatter: dict[str, object] = {}
    frontmatter_error: str | None = None
    try:
        loaded = yaml.safe_load(match.group(1))
        if loaded is None:
            loaded = {}
        if not isinstance(loaded, dict):
            frontmatter_error = "Frontmatter must be a YAML mapping (key: value pairs)"
        else:
            frontmatter = loaded
    except yaml.YAMLError as exc:
        frontmatter_error = str(exc)

    name = ""
    description = ""
    if frontmatter_error is None:
        raw_name = frontmatter.get("name")
        raw_description = frontmatter.get("description")
        name = str(raw_name).strip() if raw_name is not None else ""
        description = str(raw_description).strip() if raw_description is not None else ""

    return Skill(
        name=name,
        description=description,
        frontmatter=frontmatter,
        body=body,
        raw_text=raw_text,
        path=path,
        dir=path.parent,
        frontmatter_error=frontmatter_error,
    )
