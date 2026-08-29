"""PORTABILITY rules: flag environment assumptions (tools, network, OS, paths).

Declaring a dependency is not a defect — these are mostly informational
("Requires: X") so a correctly-documented dependency doesn't cost points.
Only assumptions that actually break portability (absolute paths, OS-specific
commands) are treated as a real warning.
"""

from __future__ import annotations

import re

from skillseal.compatibility_facts import ALLOWED_TOOLS_EXPERIMENTAL, DESCRIPTION_BLOCK_SCALAR
from skillseal.config import Config
from skillseal.models import Category, Severity, Skill
from skillseal.rules.base import (
    Draft,
    FuncRule,
    Rule,
    extract_code_spans,
    frontmatter_key_line,
    offset_to_line,
)

_BLOCK_SCALAR_DESCRIPTION_RE = re.compile(r"^description:[ \t]*[|>][+\-]?\d*[ \t]*$", re.MULTILINE)

_TOOL_KEYWORDS = [
    "npm",
    "node",
    "python3",
    "python",
    "uv",
    "docker",
    "git",
    "curl",
    "wget",
    "brew",
    "cargo",
    "ruby",
    "ffmpeg",
]
_TOOL_PATTERNS = {
    tool: re.compile(rf"\b{re.escape(tool)}\b", re.IGNORECASE) for tool in _TOOL_KEYWORDS
}

_NETWORK_VERB_RE = re.compile(
    r"(\bnetwork\b|\binternet\b|\bapi (call|request)\b|\bdownloads?\b)", re.IGNORECASE
)
_URL_RE = re.compile(r"https?://", re.IGNORECASE)
# /tmp is dropped from this list: it's the standard scratch dir on every
# platform (unlike /Users, /home, /etc, /var, /opt), so mentioning it isn't
# a portability assumption the way a hardcoded /Users/... path is.
_ABS_PATH_RE = re.compile(r"(?:^|[\s`(])(/(?:Users|home|etc|var|opt)/\S+|[A-Za-z]:\\\S+)")
_OS_COMMAND_RE = re.compile(r"\b(apt-get|apt install|brew install|\.bat\b|\.ps1\b|PowerShell)\b")
_OS_MENTION_RE = re.compile(r"\b(macOS|mac os|Linux|Windows)\b")


def _text(skill: Skill) -> str:
    compatibility = skill.frontmatter.get("compatibility")
    compatibility_text = compatibility if isinstance(compatibility, str) else ""
    return f"{skill.body}\n{skill.description}\n{compatibility_text}"


def _declared_compatibility(skill: Skill, config: Config) -> list[Draft]:
    compatibility = skill.frontmatter.get("compatibility")
    if not isinstance(compatibility, str) or not compatibility.strip():
        return []
    return [
        Draft(
            message="Skill declares compatibility requirements.",
            detail=compatibility,
            line=frontmatter_key_line(skill, "compatibility"),
        )
    ]


def _requires_tools(skill: Skill, config: Config) -> list[Draft]:
    text = _text(skill)
    found = [tool for tool, pattern in _TOOL_PATTERNS.items() if pattern.search(text)]
    if not found:
        return []
    return [
        Draft(message="Skill requires external CLI tools.", detail="Requires: " + ", ".join(found))
    ]


def _requires_network(skill: Skill, config: Config) -> list[Draft]:
    if _NETWORK_VERB_RE.search(_text(skill)):
        return [Draft(message="Skill appears to require network access.")]
    # A bare https:// link in prose is usually just a doc reference, not a
    # network dependency — almost every skill has one. Only a URL actually
    # inside a code block (something the skill runs, e.g. curl/wget/fetch)
    # counts as a real signal.
    for span, offset in extract_code_spans(skill.body):
        m = _URL_RE.search(span)
        if m:
            return [
                Draft(
                    message="Skill appears to require network access.",
                    line=offset_to_line(skill, offset + m.start()),
                )
            ]
    return []


def _absolute_paths(skill: Skill, config: Config) -> list[Draft]:
    matches = list(_ABS_PATH_RE.finditer(skill.body))
    if not matches:
        return []
    sample = ", ".join(m.group(1).strip() for m in matches[:3])
    return [
        Draft(
            message="Skill assumes absolute filesystem paths, which won't exist on other machines.",
            detail=sample,
            severity=Severity.WARNING,
            line=offset_to_line(skill, matches[0].start(1)),
        )
    ]


def _os_specific_command(skill: Skill, config: Config) -> list[Draft]:
    matches = list(_OS_COMMAND_RE.finditer(skill.body))
    if not matches:
        return []
    unique = sorted({m.group(0) for m in matches})
    return [
        Draft(
            message="Skill references OS-specific tools or commands.",
            detail=", ".join(unique),
            severity=Severity.WARNING,
            line=offset_to_line(skill, matches[0].start()),
        )
    ]


def _os_mention(skill: Skill, config: Config) -> list[Draft]:
    # A bare OS *name* ("works on macOS and Linux") is documentation, not a
    # defect — unlike an actual OS-specific command, it costs nothing (INFO)
    # and is suppressed entirely once `compatibility:` already declares it,
    # since that's the machine-readable version of the same statement.
    compatibility = skill.frontmatter.get("compatibility")
    if isinstance(compatibility, str) and compatibility.strip():
        return []
    matches = list(_OS_MENTION_RE.finditer(skill.body))
    if not matches:
        return []
    unique = sorted({m.group(0) for m in matches})
    return [
        Draft(
            message="Skill mentions specific operating systems.",
            detail=", ".join(unique),
            line=offset_to_line(skill, matches[0].start()),
        )
    ]


def _description_block_scalar(skill: Skill, config: Config) -> list[Draft]:
    m = _BLOCK_SCALAR_DESCRIPTION_RE.search(skill.frontmatter_text)
    if m is None:
        return []
    return [
        Draft(
            message="'description' uses YAML block-scalar style ('|' or '>').",
            detail=f"{DESCRIPTION_BLOCK_SCALAR.claim} ({DESCRIPTION_BLOCK_SCALAR.source})",
            severity=Severity.WARNING,
            line=frontmatter_key_line(skill, "description"),
        )
    ]


def _allowed_tools_experimental(skill: Skill, config: Config) -> list[Draft]:
    if "allowed-tools" not in skill.frontmatter:
        return []
    return [
        Draft(
            message="'allowed-tools' is a Claude Code-specific, experimental field.",
            detail=f"{ALLOWED_TOOLS_EXPERIMENTAL.claim} ({ALLOWED_TOOLS_EXPERIMENTAL.source})",
            line=frontmatter_key_line(skill, "allowed-tools"),
        )
    ]


RULES: list[Rule] = [
    FuncRule(
        id="declared-compatibility",
        category=Category.PORTABILITY,
        severity=Severity.INFO,
        description="Surfaces the frontmatter 'compatibility' field, when declared.",
        fn=_declared_compatibility,
    ),
    FuncRule(
        id="requires-tools",
        category=Category.PORTABILITY,
        severity=Severity.INFO,
        description="Reports external CLI tools the skill relies on.",
        fn=_requires_tools,
    ),
    FuncRule(
        id="requires-network",
        category=Category.PORTABILITY,
        severity=Severity.INFO,
        description="Reports whether the skill needs network access.",
        fn=_requires_network,
    ),
    FuncRule(
        id="absolute-path",
        category=Category.PORTABILITY,
        severity=Severity.WARNING,
        description="Flags hardcoded absolute filesystem paths.",
        fn=_absolute_paths,
    ),
    FuncRule(
        id="os-specific-command",
        category=Category.PORTABILITY,
        severity=Severity.WARNING,
        description="Flags OS-specific commands or tooling.",
        fn=_os_specific_command,
    ),
    FuncRule(
        id="os-mention",
        category=Category.PORTABILITY,
        severity=Severity.INFO,
        description="Notes bare OS-name mentions, unless already covered by 'compatibility:'.",
        fn=_os_mention,
    ),
    FuncRule(
        id="description-block-scalar",
        category=Category.PORTABILITY,
        severity=Severity.WARNING,
        description="Flags a block-scalar 'description' — breaks skill discovery on Claude Code.",
        fn=_description_block_scalar,
    ),
    FuncRule(
        id="allowed-tools-experimental",
        category=Category.PORTABILITY,
        severity=Severity.INFO,
        description="Notes that 'allowed-tools' is an experimental, agent-specific field.",
        fn=_allowed_tools_experimental,
    ),
]
