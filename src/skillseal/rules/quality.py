"""QUALITY rules: heuristic checks for instruction quality and skill size/focus."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from skillseal.config import Config
from skillseal.models import Category, Severity, Skill
from skillseal.rules.base import (
    Draft,
    FuncRule,
    Rule,
    code_block_ranges,
    estimate_tokens,
    frontmatter_key_line,
    local_file_targets,
    offset_to_line,
    split_sections,
)

# Defaults for the four thresholds below come from the agentskills.io spec
# ("Instructions (<5000 tokens recommended)... Keep your main SKILL.md under 500 lines.")
# or our own judgment; all are overridable via skillseal.toml (see config.py) except
# this one, which is an internal implementation detail, not worth exposing.
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

WHEN_CUE_RE = re.compile(
    r"\b(when|whenever|if you|for (use )?when|use (this|it) (for|when|to)|before|after)\b",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^##[ \t]+", re.MULTILINE)


def _skill_too_large(skill: Skill, config: Config) -> list[Draft]:
    tokens = estimate_tokens(skill.raw_text)
    if tokens <= config.token_warn_threshold:
        return []
    return [
        Draft(
            message="SKILL.md exceeds the recommended body size (agentskills.io: <5000 tokens).",
            detail=f"~{tokens:,} estimated tokens (threshold: {config.token_warn_threshold:,})",
        )
    ]


def _too_many_lines(skill: Skill, config: Config) -> list[Draft]:
    line_count = skill.raw_text.count("\n") + 1
    if line_count <= config.max_lines:
        return []
    return [
        Draft(
            message="SKILL.md exceeds the recommended line count (agentskills.io: "
            "under 500 lines) — consider moving detail to a references/ file.",
            detail=f"{line_count} lines (threshold: {config.max_lines})",
        )
    ]


def _repeated_instruction_lines(skill: Skill, config: Config) -> list[Draft]:
    # A repeated line of *code* (e.g. "import polars as pl" in two examples)
    # isn't a repeated instruction — measured on a 1,142-skill corpus, 58% of
    # this rule's firings were exactly that (see #28).
    code_ranges = code_block_ranges(skill.body)
    counts: Counter[str] = Counter()
    first_offset: dict[str, int] = {}
    offset = 0
    for raw_line in skill.body.splitlines(keepends=True):
        in_code = any(start <= offset < end for start, end in code_ranges)
        stripped = raw_line.strip()
        # A repeated table header/separator row ("| Format | Skill |...") is
        # structure, not a duplicated instruction — 8.4% of firings on the
        # same corpus (#28).
        is_structural = stripped.startswith("#") or stripped.startswith("|")
        if not in_code and len(stripped) >= _MIN_REPEATED_LINE_LEN and not is_structural:
            counts[stripped] += 1
            first_offset.setdefault(stripped, offset)
        offset += len(raw_line)

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
            line=offset_to_line(skill, first_offset[sample]),
        )
    ]


def _long_sections(skill: Skill, config: Config) -> list[Draft]:
    offenders = []
    for heading, text, offset in split_sections(skill.body):
        word_count = len(text.split())
        if word_count > config.long_section_word_threshold:
            offenders.append((heading or "(untitled)", word_count, offset))
    if not offenders:
        return []
    detail = ", ".join(f"{h!r} (~{w} words)" for h, w, _ in offenders)
    line = offset_to_line(skill, offenders[0][2])
    return [Draft(message="One or more sections are excessively long.", detail=detail, line=line)]


def _vague_description(skill: Skill, config: Config) -> list[Draft]:
    normalized = " ".join(skill.description.casefold().split())
    for phrase in _VAGUE_PHRASES:
        if phrase in normalized:
            return [
                Draft(
                    message="Description may not provide enough information for reliable routing.",
                    detail=f'matched vague phrase: "{phrase}"',
                    line=frontmatter_key_line(skill, "description"),
                )
            ]
    # The phrase blocklist above is a cheap, essentially-never-fires backstop
    # (0/1142 real skills on a corpus scan, #28) — length is the signal that
    # actually discriminates: see config.vague_description_min_words.
    word_count = len(skill.description.split())
    if 0 < word_count < config.vague_description_min_words:
        return [
            Draft(
                message="Description may not provide enough information for reliable routing.",
                detail=f"{word_count} word(s) (recommended: {config.vague_description_min_words}+)",
                line=frontmatter_key_line(skill, "description"),
            )
        ]
    return []


def _description_lacks_when_to_use(skill: Skill, config: Config) -> list[Draft]:
    if not skill.description:
        return []
    if WHEN_CUE_RE.search(skill.description):
        return []
    return [
        Draft(
            message="Description does not clearly state when the skill should be used.",
            detail="Consider phrasing like 'Use this when ...' so routing can rely on it.",
            line=frontmatter_key_line(skill, "description"),
        )
    ]


def _too_many_responsibilities(skill: Skill, config: Config) -> list[Draft]:
    count = len(_HEADING_RE.findall(skill.body))
    if count <= config.max_top_level_sections:
        return []
    return [
        Draft(
            message="Skill covers many distinct sections, which may signal too many "
            "responsibilities.",
            detail=f"{count} top-level sections (threshold: {config.max_top_level_sections})",
        )
    ]


def _dangling_file_references(skill: Skill, config: Config) -> list[Draft]:
    missing = []
    for target, offset in local_file_targets(skill.body):
        if not (skill.dir / target).exists():
            missing.append((target, offset))
    if not missing:
        return []
    return [
        Draft(
            message="Skill references local files that don't exist in its directory.",
            detail=", ".join(target for target, _ in missing),
            line=offset_to_line(skill, missing[0][1]),
        )
    ]


def _deep_file_references(skill: Skill, config: Config) -> list[Draft]:
    """Spec: 'Keep file references one level deep from SKILL.md.'

    A `../sibling-skill/SKILL.md` reference (common in a repo bundling
    several related skills) isn't nested *within* this skill's own reference
    tree — it escapes it entirely, a different thing from `references/sub/
    foo.md`. `..` counts as escaping, not as a directory level.
    """
    deep = [
        (target, offset)
        for target, offset in local_file_targets(skill.body)
        if ".." not in Path(target).parts and len(Path(target).parent.parts) > 1
    ]
    if not deep:
        return []
    return [
        Draft(
            message="File references should stay one directory level deep from SKILL.md "
            "(e.g. references/foo.md, not references/sub/foo.md).",
            detail=", ".join(target for target, _ in deep),
            line=offset_to_line(skill, deep[0][1]),
        )
    ]


def _metadata_token_budget(skill: Skill, config: Config) -> list[Draft]:
    """name+description are loaded into every session's context whether the skill

    activates or not - a much tighter startup budget than the body's.
    """
    tokens = estimate_tokens(f"{skill.name} {skill.description}")
    if tokens <= config.metadata_token_threshold:
        return []
    return [
        Draft(
            message="name + description exceed the metadata-tier startup budget, paid by "
            "every installed skill on every session whether it activates or not.",
            detail=f"~{tokens:,} estimated tokens (threshold: {config.metadata_token_threshold:,})",
            line=frontmatter_key_line(skill, "description"),
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
        id="too-many-lines",
        category=Category.QUALITY,
        severity=Severity.WARNING,
        description="SKILL.md should stay under the recommended line count.",
        fn=_too_many_lines,
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
    FuncRule(
        id="deep-file-reference",
        category=Category.QUALITY,
        severity=Severity.WARNING,
        description="File references should stay one directory level deep from SKILL.md.",
        fn=_deep_file_references,
    ),
    FuncRule(
        id="metadata-token-budget",
        category=Category.QUALITY,
        severity=Severity.WARNING,
        description="name + description should stay under the metadata-tier token budget.",
        fn=_metadata_token_budget,
    ),
]
