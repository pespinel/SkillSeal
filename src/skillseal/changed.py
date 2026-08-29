"""`skillseal check --changed`: scope discovery to skills touched between two git refs.

For a monorepo with many skills, re-linting the whole tree on every PR is
wasted work — this narrows discovery to just the skills whose directory
contains a file that changed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class GitDiffError(Exception):
    """Raised for a git failure (bad ref, not a repo) — callers treat this as a usage error."""


def _run_git(args: list[str], cwd: Path) -> str:
    # LC_ALL=C so git's own error text (e.g. "ambiguous argument") is
    # consistently in English regardless of the runner's locale — a CI log
    # is not the place for locale-dependent error messages.
    env = {**os.environ, "LC_ALL": "C"}
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30, env=env
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitDiffError(f"Failed to run git {' '.join(args)}: {exc}") from exc
    if result.returncode != 0:
        raise GitDiffError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def changed_files(path: Path, base_ref: str, head_ref: str = "HEAD") -> set[Path]:
    """Absolute paths of files that differ between base_ref and head_ref.

    `path` only needs to be *inside* the repo — git resolves the toplevel and
    the ref range itself, so this works the same whether `path` is the repo
    root or a subdirectory.
    """
    toplevel = Path(_run_git(["rev-parse", "--show-toplevel"], cwd=path).strip())
    output = _run_git(["diff", "--name-only", f"{base_ref}...{head_ref}"], cwd=path)
    return {(toplevel / line).resolve() for line in output.splitlines() if line}


def filter_changed_skills(skill_paths: list[Path], changed: set[Path]) -> list[Path]:
    """Keep only SKILL.md paths whose skill directory contains a changed file.

    Not just "did SKILL.md itself change" — a change to a bundled
    scripts/references/assets file should re-lint the skill too, since
    security/portability rules scan those.
    """
    kept = []
    for skill_path in skill_paths:
        skill_dir = skill_path.parent.resolve()
        if any(skill_dir == f.parent or skill_dir in f.parents for f in changed):
            kept.append(skill_path)
    return kept
