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
    found.sort(key=lambda p: len(p.parts))

    # Drop a SKILL.md nested under another SKILL.md's own directory (e.g. a
    # bundled `references/SKILL.md`) — it's reference material, not a second
    # top-level skill, and counting it inflates skills_scanned/conflicts.
    top_level: list[Path] = []
    for candidate in found:
        if not any(candidate.is_relative_to(kept.parent) for kept in top_level):
            top_level.append(candidate)
    return sorted(top_level)


def parse_skill(path: Path) -> Skill:
    """Parse a SKILL.md file into a Skill. Never raises on malformed frontmatter."""
    # A leading UTF-8 BOM (common from Windows editors/some CI checkouts) would
    # otherwise defeat the \A anchor and get misdiagnosed as "missing frontmatter".
    raw_text = path.read_text(encoding="utf-8").lstrip("\ufeff")

    match = _FRONTMATTER_RE.match(raw_text)
    if match is None:
        stripped = raw_text.lstrip()
        # A block exists once leading whitespace (e.g. a blank first line) is
        # removed: the frontmatter is real, just not at offset 0 as required.
        if stripped != raw_text and _FRONTMATTER_RE.match(stripped) is not None:
            error_kind = "frontmatter-not-at-start"
            error_detail = "A '---' frontmatter block was found, but not at the start of the file."
        else:
            error_kind = "missing-frontmatter"
            error_detail = "No '---' frontmatter block was found."
        return Skill(
            name="",
            description="",
            frontmatter={},
            body=raw_text,
            raw_text=raw_text,
            path=path,
            dir=path.parent,
            frontmatter_error=error_detail,
            frontmatter_error_kind=error_kind,
        )

    body = raw_text[match.end() :]
    frontmatter_text = match.group(1)
    frontmatter: dict[str, object] = {}
    frontmatter_error: str | None = None
    frontmatter_error_line: int | None = None
    try:
        loaded = yaml.safe_load(frontmatter_text)
        if loaded is None:
            loaded = {}
        if not isinstance(loaded, dict):
            frontmatter_error = "Frontmatter must be a YAML mapping (key: value pairs)"
        else:
            frontmatter = loaded
    except yaml.YAMLError as exc:
        frontmatter_error = str(exc)
        mark = getattr(exc, "problem_mark", None)
        # mark.line is 0-indexed within frontmatter_text; +1 for 1-indexing, +1
        # because frontmatter_text's own line 1 is file line 2 (after the '---').
        frontmatter_error_line = mark.line + 2 if mark is not None else None

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
        frontmatter_error_kind="invalid-frontmatter" if frontmatter_error is not None else None,
        frontmatter_text=frontmatter_text,
        frontmatter_error_line=frontmatter_error_line,
    )
