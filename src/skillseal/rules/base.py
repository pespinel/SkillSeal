"""Rule interface, registry, and small text-analysis helpers shared by rule modules."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from skillseal.config import DEFAULT_CONFIG, Config
from skillseal.models import Category, Finding, Severity, Skill


class Rule(Protocol):
    """Read-only protocol so both mutable and frozen (e.g. FuncRule) implementations satisfy it."""

    @property
    def id(self) -> str: ...
    @property
    def category(self) -> Category: ...
    @property
    def severity(self) -> Severity: ...
    @property
    def description(self) -> str: ...

    def check(self, skill: Skill, config: Config = DEFAULT_CONFIG) -> list[Finding]: ...


@dataclass(frozen=True)
class Draft:
    """A finding-in-progress: a rule's fn returns these, FuncRule fills in id/category."""

    message: str
    detail: str | None = None
    severity: Severity | None = None  # override the rule's default severity
    line: int | None = None


@dataclass(frozen=True)
class FuncRule:
    """A Rule built from a plain check function. One rule = one finding id/kind,

    emitted zero or more times (usually 0 or 1 — occurrences of the same issue
    should be aggregated by the check function into a single Draft with a count
    in `detail`, not one Draft per occurrence).
    """

    id: str
    category: Category
    severity: Severity
    description: str
    fn: Callable[[Skill, Config], list[Draft]]

    def check(self, skill: Skill, config: Config = DEFAULT_CONFIG) -> list[Finding]:
        return [
            Finding(
                id=self.id,
                category=self.category,
                severity=draft.severity or self.severity,
                message=draft.message,
                detail=draft.detail,
                line=draft.line,
            )
            for draft in self.fn(skill, config)
        ]


def build_registry() -> list[Rule]:
    """Import each category's rule list lazily to avoid circular imports."""
    from skillseal.rules import metadata, portability, quality, security

    rules: list[Rule] = []
    rules.extend(metadata.RULES)
    rules.extend(quality.RULES)
    rules.extend(security.RULES)
    rules.extend(portability.RULES)
    ids = [r.id for r in rules]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise AssertionError(f"Duplicate rule ids: {sorted(duplicates)}")
    return rules


# Rule id -> the Config field (skillseal.toml [thresholds] key) that tunes it.
# Kept as a small hand-maintained map rather than inferred from fn source, since
# most rules ignore `config` entirely and there's no other signal to key off.
RULE_THRESHOLD_FIELD: dict[str, str] = {
    "description-too-short": "min_description_length",
    "skill-too-large": "token_warn_threshold",
    "too-many-lines": "max_lines",
    "section-too-long": "long_section_word_threshold",
    "too-many-responsibilities": "max_top_level_sections",
}


# --- shared text helpers -------------------------------------------------

# Matches ``` or ~~~ fences (CommonMark treats them as equivalent); the
# backreference requires the closing fence to be the exact same marker, so a
# stray odd-length fence can't mis-pair and swallow prose as "code".
_FENCED_CODE_RE = re.compile(r"^(```+|~~~+)[^\n]*\n(.*?)\n\1[ \t]*$", re.DOTALL | re.MULTILINE)
# 4-space/tab-indented blocks are also CommonMark code blocks.
_INDENTED_CODE_RE = re.compile(r"(?:^(?:[ ]{4,}|\t).*(?:\n|\Z))+", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
_HEADING_RE = re.compile(r"^#{2,6}[ \t]+(.+)$", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:")


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token). Not exact, used only for size heuristics."""
    return len(text) // 4


def extract_code_spans(text: str) -> list[tuple[str, int]]:
    """Return (content, start_offset) for fenced/indented code blocks and inline code spans."""
    spans = [(m.group(2), m.start(2)) for m in _FENCED_CODE_RE.finditer(text)]
    spans.extend((m.group(0), m.start()) for m in _INDENTED_CODE_RE.finditer(text))
    spans.extend((m.group(1), m.start(1)) for m in _INLINE_CODE_RE.finditer(text))
    return spans


def split_sections(body: str) -> list[tuple[str, str, int]]:
    """Split into (heading, section_text, heading_offset) on level 2-6 headings."""
    headings = list(_HEADING_RE.finditer(body))
    if not headings:
        return [("", body, 0)]
    sections = []
    for i, h in enumerate(headings):
        start = h.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        sections.append((h.group(1).strip(), body[start:end], h.start()))
    return sections


def markdown_link_targets(body: str) -> list[tuple[str, int]]:
    return [(m.group(1), m.start(1)) for m in _MD_LINK_RE.finditer(body)]


def local_file_targets(body: str) -> list[tuple[str, int]]:
    """Markdown link targets (with offset) that point at a local file, not a URL/anchor."""
    return [
        (target, offset)
        for target, offset in markdown_link_targets(body)
        if not _URL_SCHEME_RE.match(target) and not target.startswith("#")
    ]


def offset_to_line(skill: Skill, body_offset: int) -> int:
    """Character offset within skill.body -> 1-based line number in the file."""
    prefix_len = len(skill.raw_text) - len(skill.body)
    prefix_newlines = skill.raw_text[:prefix_len].count("\n")
    return prefix_newlines + skill.body.count("\n", 0, body_offset) + 1


def frontmatter_key_line(skill: Skill, key: str) -> int:
    """Line of `key:` in the frontmatter block, or line 1 if absent/there's no frontmatter."""
    if not skill.frontmatter_text:
        return 1
    m = re.search(rf"^{re.escape(key)}\s*:", skill.frontmatter_text, re.MULTILINE)
    if m is None:
        return 1
    return skill.frontmatter_text.count("\n", 0, m.start()) + 2
