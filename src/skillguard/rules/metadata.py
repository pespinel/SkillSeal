"""SPECIFICATION rules: frontmatter validity and required metadata."""

from __future__ import annotations

import re

from skillguard.models import Category, Severity, Skill
from skillguard.rules.base import Draft, FuncRule, Rule

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_KNOWN_KEYS = {"name", "description", "keywords", "license", "version", "allowed-tools", "metadata"}
_MAX_NAME_LEN = 64
_MIN_DESCRIPTION_LEN = 10
_MAX_DESCRIPTION_LEN = 1024


def _has_valid_frontmatter(skill: Skill) -> bool:
    """Guard used by every other rule: skip them entirely on a parse failure."""
    return skill.frontmatter_error is None


def _invalid_frontmatter(skill: Skill) -> list[Draft]:
    if skill.frontmatter_error is None:
        return []
    return [Draft(message="Frontmatter YAML is invalid.", detail=skill.frontmatter_error)]


def _missing_name(skill: Skill) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or "name" in skill.frontmatter:
        return []
    return [Draft(message="Frontmatter is missing required field 'name'.")]


def _empty_name(skill: Skill) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or "name" not in skill.frontmatter or skill.name:
        return []
    return [Draft(message="'name' is present but empty.")]


def _name_format(skill: Skill) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or not skill.name:
        return []
    if _NAME_RE.match(skill.name) and len(skill.name) <= _MAX_NAME_LEN:
        return []
    return [
        Draft(
            message=f"Name should be lowercase, hyphen-separated, and at most "
            f"{_MAX_NAME_LEN} characters.",
            detail=f"name: {skill.name!r}",
        )
    ]


def _name_matches_directory(skill: Skill) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or not skill.name:
        return []
    if skill.name == skill.dir_name:
        return []
    return [
        Draft(
            message="Frontmatter 'name' does not match the skill's directory name.",
            detail=f"name: {skill.name!r}, directory: {skill.dir_name!r}",
        )
    ]


def _missing_description(skill: Skill) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or "description" in skill.frontmatter:
        return []
    return [Draft(message="Frontmatter is missing required field 'description'.")]


def _description_too_short(skill: Skill) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or "description" not in skill.frontmatter:
        return []
    if len(skill.description) >= _MIN_DESCRIPTION_LEN:
        return []
    return [
        Draft(
            message="Description is excessively short to provide reliable routing.",
            detail=f"{len(skill.description)} characters",
        )
    ]


def _description_too_long(skill: Skill) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or "description" not in skill.frontmatter:
        return []
    if len(skill.description) <= _MAX_DESCRIPTION_LEN:
        return []
    return [
        Draft(
            message="Description is excessively long.",
            detail=f"{len(skill.description)} characters",
        )
    ]


def _unknown_frontmatter_keys(skill: Skill) -> list[Draft]:
    if not _has_valid_frontmatter(skill):
        return []
    unknown = sorted(set(skill.frontmatter) - _KNOWN_KEYS)
    if not unknown:
        return []
    return [Draft(message="Frontmatter has unrecognized keys.", detail=", ".join(unknown))]


RULES: list[Rule] = [
    FuncRule(
        id="invalid-frontmatter",
        category=Category.SPECIFICATION,
        severity=Severity.ERROR,
        description="Frontmatter YAML must parse as a mapping.",
        fn=_invalid_frontmatter,
    ),
    FuncRule(
        id="missing-name",
        category=Category.SPECIFICATION,
        severity=Severity.ERROR,
        description="Frontmatter must declare 'name'.",
        fn=_missing_name,
    ),
    FuncRule(
        id="empty-name",
        category=Category.SPECIFICATION,
        severity=Severity.ERROR,
        description="'name' must not be empty.",
        fn=_empty_name,
    ),
    FuncRule(
        id="invalid-name-format",
        category=Category.SPECIFICATION,
        severity=Severity.WARNING,
        description="'name' should be lowercase-hyphenated and reasonably short.",
        fn=_name_format,
    ),
    FuncRule(
        id="name-directory-mismatch",
        category=Category.SPECIFICATION,
        severity=Severity.WARNING,
        description="'name' should match the skill's directory name.",
        fn=_name_matches_directory,
    ),
    FuncRule(
        id="missing-description",
        category=Category.SPECIFICATION,
        severity=Severity.ERROR,
        description="Frontmatter must declare 'description'.",
        fn=_missing_description,
    ),
    FuncRule(
        id="description-too-short",
        category=Category.SPECIFICATION,
        severity=Severity.WARNING,
        description="Description should not be too short for reliable routing.",
        fn=_description_too_short,
    ),
    FuncRule(
        id="description-too-long",
        category=Category.SPECIFICATION,
        severity=Severity.WARNING,
        description="Description should not be excessively long.",
        fn=_description_too_long,
    ),
    FuncRule(
        id="unknown-frontmatter-keys",
        category=Category.SPECIFICATION,
        severity=Severity.INFO,
        description="Frontmatter should only use recognized keys.",
        fn=_unknown_frontmatter_keys,
    ),
]
