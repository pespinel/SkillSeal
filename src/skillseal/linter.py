"""Ties discovery, parsing, rules, and scoring together."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from skillseal.config import DEFAULT_CONFIG, Config
from skillseal.models import Skill, SkillReport
from skillseal.parser import discover_skills, parse_skill
from skillseal.rules.base import build_registry
from skillseal.scoring import build_report

_RULES = build_registry()

# Findings that are expected/inherent to an unfinished template and shouldn't
# score it like a broken production skill (see Skill.is_template).
_TEMPLATE_SUPPRESSED_IDS = {
    "description-too-vague",
    "description-missing-when-to-use",
    "description-too-short",
    "dangling-file-reference",
}


def lint_skill(
    skill: Skill, config: Config = DEFAULT_CONFIG, ignore_prefixes: Sequence[str] = ()
) -> SkillReport:
    findings = [finding for rule in _RULES for finding in rule.check(skill, config)]
    if skill.is_template:
        findings = [f for f in findings if f.id not in _TEMPLATE_SUPPRESSED_IDS]
    if ignore_prefixes:
        findings = [f for f in findings if not any(f.id.startswith(p) for p in ignore_prefixes)]
    return build_report(skill, findings)


def lint_path(
    path: Path, config: Config = DEFAULT_CONFIG, ignore_prefixes: Sequence[str] = ()
) -> list[SkillReport]:
    return [lint_skill(parse_skill(p), config, ignore_prefixes) for p in discover_skills(path)]
