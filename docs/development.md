# Development

## Architecture

```
src/skillseal/
├── models.py           # pydantic models: Skill, Finding, SkillReport, routing models
├── parser.py            # discover_skills(), parse_skill() — never raises on bad YAML
├── linter.py             # ties parser + rules + scoring together
├── scoring.py             # deterministic 0-100 scoring
├── config.py               # skillseal.toml: threshold overrides
├── conflicts.py              # cross-skill: duplicate names, routing-overlap (Jaccard)
├── diff.py                     # score/finding delta between two versions of a skill
├── scaffold.py                   # `init`: scaffolds a new skill + skillseal.yaml
├── fix.py                          # `fix`: safe deterministic normalizations (whitespace, BOM, hidden Unicode)
├── rules/
│   ├── base.py             # Rule protocol, FuncRule, registry, text helpers
│   ├── metadata.py          # SPECIFICATION rules
│   ├── quality.py            # QUALITY rules
│   ├── security.py           # SECURITY rules
│   └── portability.py         # PORTABILITY rules
├── routing/
│   ├── evaluator.py           # HeuristicRoutingEvaluator, LLMRoutingEvaluator, LLMProvider
│   └── runner.py               # loads skillseal.yaml, runs cases
├── reporters/
│   ├── terminal.py             # Rich terminal output
│   ├── json_reporter.py         # stable JSON schema
│   └── github.py                 # workflow-command annotations (`--format github`)
└── cli.py                          # typer app: check, test, conflicts, diff, fix, init, rules, explain
```

A `Rule` is `id`, `category`, `severity`, `description`, and
`check(skill, config) -> list[Finding]`. Most rules are built with
`FuncRule`, which wraps a plain function so adding a check doesn't require a
new class — see [AGENTS.md](https://github.com/pespinel/skillseal/blob/main/AGENTS.md)
for the exact steps to add one.

Routing evaluation is behind a `RoutingEvaluator` protocol with two
implementations:

- **`HeuristicRoutingEvaluator`** (default): fully offline, no API key needed.
  Scores how much of a prompt's distinctive vocabulary (after stopword
  removal and light suffix stripping) is covered by the skill's own name,
  description, and `keywords:`. It's deliberately simple — not real NLP —
  which is also why it's fast, free, and explainable ("Matched terms: ...").
  Recall is measured against the prompt's own term count, floored at 4, so a
  single shared word can't reach 1.0 recall and trigger on its own — a
  one-word prompt used to do exactly that. A `keywords:` entry only
  force-triggers if it's a full multi-word phrase present in the prompt; a
  single-word keyword still counts toward ordinary recall, it just can't
  short-circuit alone (both from a real-corpus measurement — see
  [`skillseal.toml`](configuration.md#skillsealtoml) for the tunable
  thresholds).
- **`LLMRoutingEvaluator`**: delegates the trigger/no-trigger decision to an
  `LLMProvider` (`complete(prompt) -> str`). `OpenAICompatibleProvider`
  implements this against any OpenAI-compatible `/chat/completions` endpoint,
  configured via `SKILLSEAL_BASE_URL`, `SKILLSEAL_API_KEY`, and
  `SKILLSEAL_MODEL`. Use `--provider llm` to opt in — it's never required.

## Quality gates

Before committing:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

These are exactly what CI runs, plus a smoke test against `examples/`.

## Releasing

Publishing is automatic — there is no manual tagging step for a normal
release:

1. Bump `version` in `pyproject.toml` and commit it to `main` (as its own
   commit or as part of a larger one).
2. Once CI passes on that commit, [`auto-release.yml`](https://github.com/pespinel/skillseal/blob/main/.github/workflows/auto-release.yml)
   notices `pyproject.toml`'s version has no matching git tag yet, creates
   `vX.Y.Z`, and pushes it.
3. That same workflow then dispatches [`release.yml`](https://github.com/pespinel/skillseal/blob/main/.github/workflows/release.yml)
   via the API (`gh workflow run`, i.e. `workflow_dispatch`) — deliberately
   *not* by relying on the tag push to re-trigger it (a tag pushed with the
   default `GITHUB_TOKEN` doesn't trigger other workflows) and *not* via
   `workflow_call` (PyPI Trusted Publishing
   [explicitly rejects](https://docs.pypi.org/trusted-publishers/troubleshooting/#reusable-workflows-on-github)
   the OIDC exchange for reusable-workflow invocations — this broke a real
   release before landing on `workflow_dispatch` instead). `release.yml`
   then builds the sdist and wheel, signs a
   [SLSA build provenance attestation](https://slsa.dev/), publishes to PyPI
   via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC,
   no stored token), and creates the GitHub Release with notes built from the
   commit log since the previous tag — not GitHub's `--generate-notes`, which
   summarizes merged PRs and produced an empty changelog here, since this
   repo pushes straight to `main` rather than merging PRs.

Gated on CI, not run in parallel with it: `auto-release.yml` triggers on the
**CI workflow's completion**, not directly on push, so a version bump can
never publish before its own tests have actually passed.

**Manual escape hatch**, for re-running or backfilling a release:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
```

`release.yml` also listens for a direct tag push (its original trigger,
before automation was added), so this still works standalone.

To verify a release artifact was actually built by this repo's workflow
(not hand-uploaded) before installing it:

```bash
gh attestation verify dist/skillseal-*.whl --owner pespinel
```

### Why not a bigger tool like release-please?

Considered and skipped for now: [release-please](https://github.com/googleapis/release-please)
and similar tools automate versioning *and* changelog generation from
Conventional Commits, but via a "Release PR" you merge to cut a release —
a workflow shape (PR-based merges to `main`) this repo doesn't currently
use, since most changes land as direct pushes. The lighter approach above
gets the automation the maintainer actually asked for (no manual tag/release
step) without changing how the repo is worked in day to day. Worth
revisiting if the project moves to a PR-based workflow later.
