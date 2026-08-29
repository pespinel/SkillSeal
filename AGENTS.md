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

## Docs site

User-facing docs live under `docs/` (MkDocs Material), not in the README —
the README is intentionally short. Deployed automatically to
<https://pespinel.github.io/SkillSeal/> by
[`.github/workflows/docs.yml`](.github/workflows/docs.yml) on every push to
`main` that touches `docs/`, `mkdocs.yml`, or `pyproject.toml`. Preview
locally with `uv run --group docs mkdocs serve`.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `type: summary`
(`feat`, `fix`, `docs`, `ci`, `chore`, `refactor`, `test`), English, one line,
imperative, focused on *why*. No trailing summary paragraphs.

## Versioning

Standard semver, driven by the commit type: `fix` → patch, `feat` → minor,
a breaking change → major (bump the major version and call it out in the
commit body, e.g. `BREAKING CHANGE: ...`). When a release bundles several
commits, bump by the highest-impact one in the batch.

## Architecture (see also [Development](https://pespinel.github.io/SkillSeal/development/) on the docs site)

```
src/skillseal/
├── parser.py         discover_skills(), parse_skill() — never raises on bad YAML
├── models.py          pydantic models (Skill, Finding, SkillReport, routing types)
├── linter.py           ties parser + rules + scoring together
├── scoring.py            deterministic 0-100 scoring
├── config.py               skillseal.toml: threshold overrides (Rule.fn takes Config now)
├── conflicts.py              cross-skill: duplicate names, routing-overlap (Jaccard)
├── diff.py                     score/finding delta between two versions of a skill
├── scaffold.py                   `init`: scaffolds a new skill + skillseal.yaml
├── fix.py                          `fix`: safe deterministic normalizations (whitespace, BOM, hidden Unicode)
├── rules/                    one module per category: metadata/quality/security/portability
├── routing/                    HeuristicRoutingEvaluator + optional LLMRoutingEvaluator
├── reporters/                     terminal.py (Rich), json_reporter.py (stable schema),
│                                    github.py (workflow-command annotations)
└── cli.py                           typer app: check, test, conflicts, diff, fix, init, rules, explain
```

## Adding a new lint rule

Add a `FuncRule` to the relevant `rules/*.py` module: a plain function
`(skill: Skill, config: Config) -> list[Draft]` (ignore `config` if the rule
has no tunable threshold) plus a `FuncRule(id=..., category=..., severity=...,
description=..., fn=...)` entry in that module's `RULES` list. One rule id =
one finding kind — aggregate repeated occurrences of the same issue into a
single `Draft` with a count in `detail`, don't emit one per occurrence (see
`rules/security.py` for the pattern). If the rule has a numeric threshold
that's our own opinion (not a hard agentskills.io spec limit), add it to
`Config` in `config.py` so it's overridable via `skillseal.toml`. Add a test
in the matching `tests/test_rules_*.py`.

## Don't

- Hand-edit `uv.lock` — regenerate it with `uv lock` / `uv sync`.
- Add a new dependency for something the stdlib or an existing dependency
  already covers (see the [Limitations](https://pespinel.github.io/SkillSeal/limitations/)
  page — the scope is kept deliberately small; planned work lives in GitHub
  Issues, not the docs).
- Bump `pyproject.toml`'s `version` casually. Once it's on `main` and CI
  passes, [`auto-release.yml`](.github/workflows/auto-release.yml) tags it
  and publishes to PyPI **automatically** — no manual tag/release step
  anymore (see [Development § Releasing](https://pespinel.github.io/SkillSeal/development/#releasing)).
  Only bump it when you mean to actually ship a release.
