"""Version-to-version comparison: does a skill's score/findings look better or worse now?"""

from __future__ import annotations

from pathlib import Path

from skillseal.config import DEFAULT_CONFIG, Config
from skillseal.linter import lint_skill
from skillseal.models import SkillDiff
from skillseal.parser import discover_skills, parse_skill


class DiffTargetError(Exception):
    """Raised when a diff side doesn't resolve to exactly one skill. A usage error."""


def _resolve_one(path: Path) -> Path:
    found = discover_skills(path)
    if len(found) != 1:
        raise DiffTargetError(f"expected exactly one skill under {path}, found {len(found)}")
    return found[0]


def diff_skills(old_path: Path, new_path: Path, config: Config = DEFAULT_CONFIG) -> SkillDiff:
    old_report = lint_skill(parse_skill(_resolve_one(old_path)), config)
    new_report = lint_skill(parse_skill(_resolve_one(new_path)), config)

    old_ids = {f.id for f in old_report.findings}
    new_ids = {f.id for f in new_report.findings}
    added = [f for f in new_report.findings if f.id not in old_ids]
    removed = [f for f in old_report.findings if f.id not in new_ids]

    return SkillDiff(old=old_report, new=new_report, added=added, removed=removed)
