"""SPECIFICATION rules: frontmatter validity and required metadata."""

from __future__ import annotations

import re

from skillseal.config import Config
from skillseal.models import Category, Severity, Skill
from skillseal.rules.base import Draft, FuncRule, Rule, frontmatter_key_line

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Per the agentskills.io spec: name/description/license/compatibility/metadata/allowed-tools
# are the only recognized top-level keys. "keywords" and "conflict_ignore" are SkillSeal-specific
# extensions (not spec-standard), used by the heuristic routing evaluator and `conflicts`
# respectively — kept here so they don't warn.
_KNOWN_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
    "keywords",
    "conflict_ignore",
}
_MAX_NAME_LEN = 64  # agentskills.io: name must be 1-64 characters
# min description length is our own heuristic floor (overridable via skillseal.toml);
# spec only requires non-empty
_MAX_DESCRIPTION_LEN = 1024  # agentskills.io: description must be 1-1024 characters
_MAX_COMPATIBILITY_LEN = 500  # agentskills.io: compatibility must be 1-500 characters
_RESERVED_WORDS = {
    "claude",
    "anthropic",
    "openai",
    "chatgpt",
    "gpt",
    "gemini",
    "copilot",
    "cursor",
    "codex",
}
_RESERVED_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _RESERVED_WORDS) + r")\b", re.IGNORECASE
)


def _has_valid_frontmatter(skill: Skill) -> bool:
    """Guard used by every other rule: skip them entirely on a parse failure."""
    return skill.frontmatter_error is None


def _missing_frontmatter(skill: Skill, config: Config) -> list[Draft]:
    if skill.frontmatter_error_kind != "missing-frontmatter":
        return []
    return [Draft(message="No frontmatter block found.", detail=skill.frontmatter_error, line=1)]


def _frontmatter_not_at_start(skill: Skill, config: Config) -> list[Draft]:
    if skill.frontmatter_error_kind != "frontmatter-not-at-start":
        return []
    return [
        Draft(
            message="Frontmatter block exists but isn't at the very start of the file.",
            detail="Check for a leading blank line, whitespace, or invisible character "
            "before the opening '---'.",
            line=1,
        )
    ]


def _invalid_frontmatter(skill: Skill, config: Config) -> list[Draft]:
    if skill.frontmatter_error_kind != "invalid-frontmatter":
        return []
    return [
        Draft(
            message="Frontmatter YAML is invalid.",
            detail=skill.frontmatter_error,
            line=skill.frontmatter_error_line or 1,
        )
    ]


def _missing_name(skill: Skill, config: Config) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or "name" in skill.frontmatter:
        return []
    return [
        Draft(
            message="Frontmatter is missing required field 'name'.",
            line=frontmatter_key_line(skill, "name"),
        )
    ]


def _empty_name(skill: Skill, config: Config) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or "name" not in skill.frontmatter or skill.name:
        return []
    return [Draft(message="'name' is present but empty.", line=frontmatter_key_line(skill, "name"))]


def _name_format(skill: Skill, config: Config) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or not skill.name:
        return []
    if _NAME_RE.match(skill.name) and len(skill.name) <= _MAX_NAME_LEN:
        return []
    return [
        Draft(
            message=f"Name should be lowercase, hyphen-separated, and at most "
            f"{_MAX_NAME_LEN} characters.",
            detail=f"name: {skill.name!r}",
            line=frontmatter_key_line(skill, "name"),
        )
    ]


def _name_matches_directory(skill: Skill, config: Config) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or not skill.name:
        return []
    if skill.name == skill.dir_name:
        return []
    return [
        Draft(
            message="Frontmatter 'name' does not match the skill's directory name.",
            detail=f"name: {skill.name!r}, directory: {skill.dir_name!r}",
            line=frontmatter_key_line(skill, "name"),
        )
    ]


def _reserved_word_in_name(skill: Skill, config: Config) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or not skill.name:
        return []
    match = _RESERVED_WORD_RE.search(skill.name)
    if match is None:
        return []
    return [
        Draft(
            message="Name contains a reserved/vendor term, which can read as an official "
            "or endorsed skill when it isn't.",
            detail=f"name: {skill.name!r}, matched: {match.group(1)!r}",
            line=frontmatter_key_line(skill, "name"),
        )
    ]


def _missing_description(skill: Skill, config: Config) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or "description" in skill.frontmatter:
        return []
    return [
        Draft(
            message="Frontmatter is missing required field 'description'.",
            line=frontmatter_key_line(skill, "description"),
        )
    ]


def _description_too_short(skill: Skill, config: Config) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or "description" not in skill.frontmatter:
        return []
    if len(skill.description) >= config.min_description_length:
        return []
    return [
        Draft(
            message="Description is excessively short to provide reliable routing.",
            detail=f"{len(skill.description)} characters",
            line=frontmatter_key_line(skill, "description"),
        )
    ]


def _description_too_long(skill: Skill, config: Config) -> list[Draft]:
    if not _has_valid_frontmatter(skill) or "description" not in skill.frontmatter:
        return []
    if len(skill.description) <= _MAX_DESCRIPTION_LEN:
        return []
    return [
        Draft(
            message="Description is excessively long.",
            detail=f"{len(skill.description)} characters",
            line=frontmatter_key_line(skill, "description"),
        )
    ]


def _compatibility_too_long(skill: Skill, config: Config) -> list[Draft]:
    if not _has_valid_frontmatter(skill):
        return []
    compatibility = skill.frontmatter.get("compatibility")
    if not isinstance(compatibility, str) or len(compatibility) <= _MAX_COMPATIBILITY_LEN:
        return []
    return [
        Draft(
            message="'compatibility' is excessively long.",
            detail=f"{len(compatibility)} characters (max {_MAX_COMPATIBILITY_LEN})",
            line=frontmatter_key_line(skill, "compatibility"),
        )
    ]


def _unknown_frontmatter_keys(skill: Skill, config: Config) -> list[Draft]:
    if not _has_valid_frontmatter(skill):
        return []
    unknown = sorted(set(skill.frontmatter) - _KNOWN_KEYS)
    if not unknown:
        return []
    return [
        Draft(
            message="Frontmatter has unrecognized keys.",
            detail=", ".join(unknown),
            line=frontmatter_key_line(skill, unknown[0]),
        )
    ]


RULES: list[Rule] = [
    FuncRule(
        id="missing-frontmatter",
        category=Category.SPECIFICATION,
        severity=Severity.ERROR,
        description="A SKILL.md must have a '---' frontmatter block.",
        fn=_missing_frontmatter,
    ),
    FuncRule(
        id="frontmatter-not-at-start",
        category=Category.SPECIFICATION,
        severity=Severity.ERROR,
        description="The frontmatter block must be the very first thing in the file.",
        fn=_frontmatter_not_at_start,
    ),
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
        id="reserved-word-in-name",
        category=Category.SPECIFICATION,
        severity=Severity.WARNING,
        description="'name' should not contain a reserved vendor/agent term.",
        fn=_reserved_word_in_name,
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
        id="compatibility-too-long",
        category=Category.SPECIFICATION,
        severity=Severity.WARNING,
        description="'compatibility' should not be excessively long.",
        fn=_compatibility_too_long,
    ),
    FuncRule(
        id="unknown-frontmatter-keys",
        category=Category.SPECIFICATION,
        severity=Severity.INFO,
        description="Frontmatter should only use recognized keys.",
        fn=_unknown_frontmatter_keys,
    ),
]
