"""PORTABILITY rules: flag environment assumptions (tools, network, OS, paths).

Declaring a dependency is not a defect — these are mostly informational
("Requires: X") so a correctly-documented dependency doesn't cost points.
Only assumptions that actually break portability (absolute paths, OS-specific
commands) are treated as a real warning.
"""

from __future__ import annotations

import re

from skillseal.config import Config
from skillseal.models import Category, Severity, Skill
from skillseal.rules.base import Draft, FuncRule, Rule

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

_NETWORK_RE = re.compile(
    r"(https?://|\bnetwork\b|\binternet\b|\bapi (call|request)\b|\bdownloads?\b)",
    re.IGNORECASE,
)
_ABS_PATH_RE = re.compile(r"(?:^|[\s`(])(/(?:Users|home|etc|var|opt|tmp)/\S+|[A-Za-z]:\\\S+)")
_OS_SPECIFIC_RE = re.compile(
    r"\b(macOS|mac os|Linux|Windows|apt-get|apt install|brew install|\.bat\b|\.ps1\b|PowerShell)\b"
)


def _text(skill: Skill) -> str:
    compatibility = skill.frontmatter.get("compatibility")
    compatibility_text = compatibility if isinstance(compatibility, str) else ""
    return f"{skill.body}\n{skill.description}\n{compatibility_text}"


def _declared_compatibility(skill: Skill, config: Config) -> list[Draft]:
    compatibility = skill.frontmatter.get("compatibility")
    if not isinstance(compatibility, str) or not compatibility.strip():
        return []
    return [Draft(message="Skill declares compatibility requirements.", detail=compatibility)]


def _requires_tools(skill: Skill, config: Config) -> list[Draft]:
    text = _text(skill)
    found = [tool for tool, pattern in _TOOL_PATTERNS.items() if pattern.search(text)]
    if not found:
        return []
    return [
        Draft(message="Skill requires external CLI tools.", detail="Requires: " + ", ".join(found))
    ]


def _requires_network(skill: Skill, config: Config) -> list[Draft]:
    if not _NETWORK_RE.search(_text(skill)):
        return []
    return [Draft(message="Skill appears to require network access.")]


def _absolute_paths(skill: Skill, config: Config) -> list[Draft]:
    matches = _ABS_PATH_RE.findall(skill.body)
    if not matches:
        return []
    sample = ", ".join(m.strip() for m in matches[:3])
    return [
        Draft(
            message="Skill assumes absolute filesystem paths, which won't exist on other machines.",
            detail=sample,
            severity=Severity.WARNING,
        )
    ]


def _os_specific(skill: Skill, config: Config) -> list[Draft]:
    matches = {m.group(0) for m in _OS_SPECIFIC_RE.finditer(skill.body)}
    if not matches:
        return []
    return [
        Draft(
            message="Skill references OS-specific tools or commands.",
            detail=", ".join(sorted(matches)),
            severity=Severity.WARNING,
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
        fn=_os_specific,
    ),
]
