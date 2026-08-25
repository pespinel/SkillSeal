"""QUALITY rules: heuristic checks for instruction quality and skill size/focus."""

from __future__ import annotations

import re
from collections import Counter

from skillguard.models import Category, Severity, Skill
from skillguard.rules.base import (
    Draft,
    FuncRule,
    Rule,
    estimate_tokens,
    markdown_link_targets,
    split_sections,
)

_TOKEN_WARN_THRESHOLD = 2000
_LONG_SECTION_WORD_THRESHOLD = 800
_MAX_TOP_LEVEL_SECTIONS = 8
_MIN_REPEATED_LINE_LEN = 15

_VAGUE_PHRASES = [
    "use this skill when needed",
    "use when needed",
    "helps with tasks",
    "helps with things",
    "assists with tasks",
    "assists with things",
    "use as needed",
    "for general use",
    "helps you with various tasks",
]

_WHEN_CUE_RE = re.compile(
    r"\b(when|whenever|if you|for (use )?when|use (this|it) (for|when|to)|before|after)\b",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^##[ \t]+", re.MULTILINE)
_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:")


def _skill_too_large(skill: Skill) -> list[Draft]:
    tokens = estimate_tokens(skill.raw_text)
    if tokens <= _TOKEN_WARN_THRESHOLD:
        return []
    return [
        Draft(
            message="SKILL.md is large enough to add significant context overhead.",
            detail=f"~{tokens:,} estimated tokens (threshold: {_TOKEN_WARN_THRESHOLD:,})",
        )
    ]


def _repeated_instruction_lines(skill: Skill) -> list[Draft]:
    lines = [line.strip() for line in skill.body.splitlines()]
    candidates = [
        line for line in lines if len(line) >= _MIN_REPEATED_LINE_LEN and not line.startswith("#")
    ]
    counts = Counter(candidates)
    repeated = {line: n for line, n in counts.items() if n > 1}
    if not repeated:
        return []
    total_extra = sum(n - 1 for n in repeated.values())
    sample = next(iter(repeated))
    return [
        Draft(
            message="SKILL.md repeats instruction lines verbatim.",
            detail=f"{len(repeated)} line(s) repeated ({total_extra} extra occurrences), "
            f'e.g. "{sample[:80]}"',
        )
    ]


def _long_sections(skill: Skill) -> list[Draft]:
    offenders = []
    for heading, text in split_sections(skill.body):
        word_count = len(text.split())
        if word_count > _LONG_SECTION_WORD_THRESHOLD:
            offenders.append((heading or "(untitled)", word_count))
    if not offenders:
        return []
    detail = ", ".join(f"{h!r} (~{w} words)" for h, w in offenders)
    return [Draft(message="One or more sections are excessively long.", detail=detail)]


def _vague_description(skill: Skill) -> list[Draft]:
    normalized = " ".join(skill.description.casefold().split())
    for phrase in _VAGUE_PHRASES:
        if phrase in normalized:
            return [
                Draft(
                    message="Description may not provide enough information for reliable routing.",
                    detail=f'matched vague phrase: "{phrase}"',
                )
            ]
    return []


def _description_lacks_when_to_use(skill: Skill) -> list[Draft]:
    if not skill.description:
        return []
    if _WHEN_CUE_RE.search(skill.description):
        return []
    return [
        Draft(
            message="Description does not clearly state when the skill should be used.",
            detail="Consider phrasing like 'Use this when ...' so routing can rely on it.",
        )
    ]


def _too_many_responsibilities(skill: Skill) -> list[Draft]:
    count = len(_HEADING_RE.findall(skill.body))
    if count <= _MAX_TOP_LEVEL_SECTIONS:
        return []
    return [
        Draft(
            message="Skill covers many distinct sections, which may signal too many "
            "responsibilities.",
            detail=f"{count} top-level sections (threshold: {_MAX_TOP_LEVEL_SECTIONS})",
        )
    ]


def _dangling_file_references(skill: Skill) -> list[Draft]:
    missing = []
    for target in markdown_link_targets(skill.body):
        if _URL_SCHEME_RE.match(target) or target.startswith("#"):
            continue
        if not (skill.dir / target).exists():
            missing.append(target)
    if not missing:
        return []
    return [
        Draft(
            message="Skill references local files that don't exist in its directory.",
            detail=", ".join(missing),
        )
    ]


RULES: list[Rule] = [
    FuncRule(
        id="skill-too-large",
        category=Category.QUALITY,
        severity=Severity.WARNING,
        description="SKILL.md should stay under a reasonable size budget.",
        fn=_skill_too_large,
    ),
    FuncRule(
        id="repeated-instructions",
        category=Category.QUALITY,
        severity=Severity.WARNING,
        description="Instructions should not be repeated verbatim.",
        fn=_repeated_instruction_lines,
    ),
    FuncRule(
        id="section-too-long",
        category=Category.QUALITY,
        severity=Severity.WARNING,
        description="Individual sections should not be excessively long.",
        fn=_long_sections,
    ),
    FuncRule(
        id="description-too-vague",
        category=Category.QUALITY,
        severity=Severity.WARNING,
        description="Description should be specific, not generic boilerplate.",
        fn=_vague_description,
    ),
    FuncRule(
        id="description-missing-when-to-use",
        category=Category.QUALITY,
        severity=Severity.WARNING,
        description="Description should state when the skill applies.",
        fn=_description_lacks_when_to_use,
    ),
    FuncRule(
        id="too-many-responsibilities",
        category=Category.QUALITY,
        severity=Severity.WARNING,
        description="A skill should stay focused on one responsibility.",
        fn=_too_many_responsibilities,
    ),
    FuncRule(
        id="dangling-file-reference",
        category=Category.QUALITY,
        severity=Severity.INFO,
        description="Local file references should point at files that exist.",
        fn=_dangling_file_references,
    ),
]
