# Agent instructions for this repo

SkillSeal lints, scores, and routing-tests Agent Skills (`SKILL.md` files).
Don't confuse this repo's own dev workflow with the `SKILL.md`/`skillseal.yaml`
files under `examples/` — those are fixtures the tool analyzes, not
instructions for you.

## Setup

```bash
uv sync
```

## Running it

```bash
uv run skillseal check examples
uv run skillseal test examples
```

## Before committing — all of these must pass

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

These are the exact checks CI runs (`.github/workflows/ci.yml`), plus a
smoke test against `examples/good-skill` (must pass) and `examples/bad-skill`
(must fail both the lint gate and the routing threshold — it's deliberately
broken). If you change either example, re-run
`uv run skillseal check examples/bad-skill` and
`uv run skillseal test examples/bad-skill` to confirm they still fail for the
same reasons the CI step expects.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `type: summary`
(`feat`, `fix`, `docs`, `ci`, `chore`, `refactor`, `test`), English, one line,
imperative, focused on *why*. No trailing summary paragraphs.

## Architecture (see also README's Architecture section)

```
src/skillseal/
├── parser.py         discover_skills(), parse_skill() — never raises on bad YAML
├── models.py          pydantic models (Skill, Finding, SkillReport, routing types)
├── linter.py           ties parser + rules + scoring together
├── scoring.py            deterministic 0-100 scoring
├── rules/                 one module per category: metadata/quality/security/portability
├── routing/                 HeuristicRoutingEvaluator + optional LLMRoutingEvaluator
├── reporters/                 terminal.py (Rich) and json_reporter.py (stable schema)
└── cli.py                       typer app: check, test
```

## Adding a new lint rule

Add a `FuncRule` to the relevant `rules/*.py` module: a plain function
`(skill: Skill) -> list[Draft]` plus a `FuncRule(id=..., category=..., severity=...,
description=..., fn=...)` entry in that module's `RULES` list. One rule id =
one finding kind — aggregate repeated occurrences of the same issue into a
single `Draft` with a count in `detail`, don't emit one per occurrence (see
`rules/security.py` for the pattern). Add a test in the matching
`tests/test_rules_*.py`.

## Don't

- Hand-edit `uv.lock` — regenerate it with `uv lock` / `uv sync`.
- Add a new dependency for something the stdlib or an existing dependency
  already covers (see the Limitations/Roadmap sections in README — the
  scope is kept deliberately small).
- Bump `pyproject.toml`'s `version` without also tagging a matching
  `vX.Y.Z` release (see README's Releasing section) — the release workflow
  checks they match and fails otherwise.
