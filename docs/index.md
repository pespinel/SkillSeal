# SkillSeal

**Test your Agent Skills before your agents do.**

`SKILL.md` files can be syntactically valid and still be bad: a vague
description that never routes correctly, an oversized file that eats context,
a `curl | sh` buried in a code block, a hardcoded `/Users/you/...` path that
only works on your machine. None of that shows up until an agent picks the
wrong skill, or picks the right one and runs something it shouldn't.

SkillSeal is a local-first, offline-first CLI that lints, scores, and
routing-tests `SKILL.md` files, so you catch that before an agent does. It's
deliberately scoped to what's useful today: static linting across four
categories, deterministic (LLM-optional) routing tests, and CI-friendly exit
codes and JSON output. No dashboard, no registry, no cloud.

## Installation

Requires Python 3.12+. Install from [PyPI](https://pypi.org/project/skillseal/)
with [uv](https://docs.astral.sh/uv/), pipx, or pip:

```bash
uv tool install skillseal
# or: pipx install skillseal
# or: pip install skillseal
```

No install at all, one-off run:

```bash
uvx skillseal check ./skills
```

For local development, clone the repo instead:

```bash
git clone https://github.com/pespinel/skillseal
cd skillseal
uv sync
```

## Quickstart

```bash
skillseal check examples
skillseal test examples
skillseal conflicts examples/conflicting-skills
skillseal diff old-version/ new-version/
```

(From a repo clone without installing, prefix these with `uv run`.)

All commands accept a path to a single `SKILL.md` file, a single skill
directory, or a directory containing many skills (searched recursively).

See [Commands](commands.md) for the full reference, or jump straight to
[Using it in CI](ci.md).
