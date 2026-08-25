"""Ties discovery, parsing, rules, and scoring together."""

from __future__ import annotations

from pathlib import Path

from skillseal.models import Skill, SkillReport
from skillseal.parser import discover_skills, parse_skill
from skillseal.rules.base import build_registry
from skillseal.scoring import build_report

_RULES = build_registry()


def lint_skill(skill: Skill) -> SkillReport:
    findings = [finding for rule in _RULES for finding in rule.check(skill)]
    return build_report(skill, findings)


def lint_path(path: Path) -> list[SkillReport]:
    return [lint_skill(parse_skill(p)) for p in discover_skills(path)]
