"""Curated, dated cross-agent compatibility facts (#6).

Declared/documented, never tested: every fact below is a claim verifiable by
reading a vendor doc offline, not something SkillSeal observed by actually
running an agent (that's #5, a different, larger feature). `checked` is the
date the source was last read to confirm the claim still holds;
`tests/test_compatibility_facts.py` fails the build once a fact goes stale,
so an unverified claim doesn't silently rot into a false one.
"""

from __future__ import annotations

from dataclasses import dataclass

STALE_AFTER_MONTHS = 12


@dataclass(frozen=True)
class CompatibilityFact:
    claim: str
    source: str
    checked: str  # ISO date (YYYY-MM-DD) the source was last confirmed


NAME_DIRECTORY_MISMATCH = CompatibilityFact(
    claim="VS Code Copilot silently fails to load a skill whose 'name' doesn't "
    "match its parent directory — no error is shown.",
    source="https://code.visualstudio.com/docs/agent-customization/agent-skills",
    checked="2026-08-29",
)

NON_SPEC_KEYS = CompatibilityFact(
    claim="Only name/description/license/compatibility/metadata/allowed-tools are "
    "defined by the agentskills.io spec; any other frontmatter key is an "
    "agent-specific extension other agents will ignore.",
    source="https://agentskills.io/specification",
    checked="2026-08-29",
)

ALLOWED_TOOLS_EXPERIMENTAL = CompatibilityFact(
    claim="'allowed-tools' is marked Experimental by the agentskills.io spec "
    "('support for this field may vary between agent implementations'); "
    "VS Code Copilot's skill docs don't mention it at all.",
    source="https://agentskills.io/specification",
    checked="2026-08-29",
)

DESCRIPTION_BLOCK_SCALAR = CompatibilityFact(
    claim="Claude Code has a long-standing, unresolved bug where a block-scalar "
    "('description: |') description renders as a bare '|' instead of the real "
    "text, breaking model-invoked skill discovery.",
    source="https://github.com/anthropics/claude-code/issues/10589",
    checked="2026-08-29",
)
