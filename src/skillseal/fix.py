"""`skillseal fix`: safe, deterministic, byte-level normalizations for SKILL.md.

Scope is deliberately narrow (see AGENTS.md / issue #8): only fixes that are
unambiguous, idempotent, and can't change a skill's meaning — trailing
whitespace, a leading BOM, and hidden/bidi-override Unicode characters.

Explicitly out of scope for this pass:
- Frontmatter key reordering: needs a round-trip-preserving YAML writer to
  avoid silently reformatting a user's block scalars/comments/quoting —
  `ruamel.yaml` or similar, not a dependency this repo currently has.
- `name-directory-mismatch`: rewriting `name` vs. renaming the directory have
  opposite consequences (the latter breaks every existing reference to the
  skill) — a human choice, not something to auto-pick.
- Anything touching `description`: a mechanically-rewritten description is
  worse than the original because it *looks* fixed. Never in the
  deterministic path.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from skillseal.parser import discover_skills
from skillseal.rules.base import HIDDEN_UNICODE_RE


@dataclass(frozen=True)
class FileFix:
    path: Path
    trailing_whitespace_lines: int
    had_bom: bool
    hidden_unicode_chars: int

    @property
    def changed(self) -> bool:
        return self.trailing_whitespace_lines > 0 or self.had_bom or self.hidden_unicode_chars > 0


def _fixed_text(raw_text: str) -> tuple[str, int, bool, int]:
    had_bom = raw_text.startswith("﻿")
    text = raw_text[1:] if had_bom else raw_text

    # Scanned after the leading BOM is already removed, so it isn't double-counted.
    hidden_unicode_chars = len(HIDDEN_UNICODE_RE.findall(text))
    text = HIDDEN_UNICODE_RE.sub("", text)

    lines = text.split("\n")
    stripped_lines = [line.rstrip(" \t") for line in lines]
    trailing_whitespace_lines = sum(1 for a, b in zip(lines, stripped_lines, strict=True) if a != b)
    text = "\n".join(stripped_lines)

    return text, trailing_whitespace_lines, had_bom, hidden_unicode_chars


def plan_fixes(path: Path) -> list[FileFix]:
    """Dry-run: what would change, without touching anything on disk."""
    fixes = []
    for skill_path in discover_skills(path):
        raw_text = skill_path.read_text(encoding="utf-8")
        _, ws, bom, hidden = _fixed_text(raw_text)
        fixes.append(FileFix(skill_path, ws, bom, hidden))
    return fixes


def _is_dirty(path: Path) -> bool:
    """True if `path` has uncommitted git changes. False if clean, untracked-repo, or no git."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", str(path)],
            cwd=path.parent,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False  # not a git repo (or git unavailable) — nothing to protect
    return bool(result.stdout.strip())


@dataclass(frozen=True)
class ApplyResult:
    fixed: list[Path]
    skipped_dirty: list[Path]


def apply_fixes(path: Path, force: bool = False) -> ApplyResult:
    fixed: list[Path] = []
    skipped: list[Path] = []
    for skill_path in discover_skills(path):
        raw_text = skill_path.read_text(encoding="utf-8")
        new_text, ws, bom, hidden = _fixed_text(raw_text)
        if ws == 0 and not bom and hidden == 0:
            continue
        if not force and _is_dirty(skill_path):
            skipped.append(skill_path)
            continue
        skill_path.write_text(new_text, encoding="utf-8")
        fixed.append(skill_path)
    return ApplyResult(fixed=fixed, skipped_dirty=skipped)
