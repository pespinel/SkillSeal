"""Rule interface, registry, and small text-analysis helpers shared by rule modules."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

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

    def check(self, skill: Skill) -> list[Finding]: ...


@dataclass(frozen=True)
class Draft:
    """A finding-in-progress: a rule's fn returns these, FuncRule fills in id/category."""

    message: str
    detail: str | None = None
    severity: Severity | None = None  # override the rule's default severity


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
    fn: Callable[[Skill], list[Draft]]

    def check(self, skill: Skill) -> list[Finding]:
        return [
            Finding(
                id=self.id,
                category=self.category,
                severity=draft.severity or self.severity,
                message=draft.message,
                detail=draft.detail,
            )
            for draft in self.fn(skill)
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


# --- shared text helpers -------------------------------------------------

_FENCED_CODE_RE = re.compile(r"```.*?\n(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
_HEADING_RE = re.compile(r"^#{2,6}[ \t]+(.+)$", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:")


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token). Not exact, used only for size heuristics."""
    return len(text) // 4


def extract_code_spans(text: str) -> list[str]:
    """Return the contents of fenced code blocks and inline code spans."""
    spans = list(_FENCED_CODE_RE.findall(text))
    spans.extend(_INLINE_CODE_RE.findall(text))
    return spans


def split_sections(body: str) -> list[tuple[str, str]]:
    """Split a markdown body into (heading, section_text) pairs on level 2-6 headings."""
    headings = list(_HEADING_RE.finditer(body))
    if not headings:
        return [("", body)]
    sections = []
    for i, h in enumerate(headings):
        start = h.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        sections.append((h.group(1).strip(), body[start:end]))
    return sections


def markdown_link_targets(body: str) -> list[str]:
    return _MD_LINK_RE.findall(body)


def local_file_targets(body: str) -> list[str]:
    """Markdown link targets that point at a local file, not a URL or an in-page anchor."""
    return [
        target
        for target in markdown_link_targets(body)
        if not _URL_SCHEME_RE.match(target) and not target.startswith("#")
    ]
