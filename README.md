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
```

(From a repo clone without installing, prefix these with `uv run`.)

All three commands accept a path to a single `SKILL.md` file, a single skill
directory, or a directory containing many skills (searched recursively).

## Commands

### `skillseal check <path>`

Runs every rule (SPECIFICATION, QUALITY, SECURITY, PORTABILITY) against each
discovered skill and prints a per-skill report with a 0-100 score.

| Flag | Default | Meaning |
|---|---|---|
| `--format terminal\|json` | `terminal` | Output format. |
| `--fail-on warning\|error` | `error` | Minimum finding severity that fails the gate. |
| `--ignore PREFIX` | none | Suppress findings whose id starts with `PREFIX`. Repeatable. |

### `skillseal test <path>`

Runs the routing test cases declared in each skill's `skillseal.yaml`
against a `RoutingEvaluator`, and reports accuracy against `should_trigger`
and `should_not_trigger` prompts. Skills without a `skillseal.yaml` are
skipped, not failed.

| Flag | Default | Meaning |
|---|---|---|
| `--threshold <float>` | `0.9`\* | Minimum accuracy per skill to pass the gate. |
| `--format terminal\|json` | `terminal` | Output format. |
| `--provider heuristic\|llm` | `heuristic` | Evaluator to use (see below). |

\* Or whatever `routing_threshold` is set to in `skillseal.toml` — see
[Configuration](#skillsealtoml-format) below.

### `skillseal conflicts <path>`

Scans every skill under `path` *together* rather than one at a time, and
flags two things `check`/`test` can't see in isolation:

- **Duplicate names** — two skills declaring the same frontmatter `name`
  (usually a copy-paste leftover).
- **Routing overlap** — two skills whose vocabulary (name + description +
  `keywords:`) is similar enough that an agent likely can't reliably tell
  them apart, using the same term-matching `HeuristicRoutingEvaluator` uses
  for routing tests, compared pairwise via Jaccard similarity.

| Flag | Default | Meaning |
|---|---|---|
| `--threshold <float>` | `0.5`\* | Minimum vocabulary similarity (Jaccard) to flag as overlap. |
| `--against <path>` | none | Check `path` against this broader corpus instead of all-pairs within `path`. |
| `--format terminal\|json` | `terminal` | Output format. |

\* Or `conflict_threshold` in `skillseal.toml` — see
[Configuration](#skillsealtoml-format) below.

Without `--against`, every skill under `path` is compared against every
other. With it, only pairs involving at least one skill from `path` are
considered — the PR-gate use case: "does the skill I just added or changed
conflict with anything in the existing repo?" without re-auditing the whole
existing corpus against itself on every run:

```bash
skillseal conflicts ./skills/my-new-skill --against ./skills
```

A skill can opt specific others out of routing-overlap comparison — useful
for deliberately similar variants — via `conflict_ignore` in its frontmatter
(matched by name or by a path substring; this only suppresses the routing-
overlap check, not duplicate-name detection, since a real name collision is
rarely something you actually want to allow):

```yaml
---
name: my-skill
description: Use this when ...
conflict_ignore:
  - legacy-skill
---
```

```
$ uv run skillseal conflicts examples/conflicting-skills

Duplicate names

✗ "alpha-reviewer" used by 2 skills:
  - examples/conflicting-skills/alpha-reviewer/SKILL.md
  - examples/conflicting-skills/alpha-reviewer-2/SKILL.md

Routing overlap

✗ "alpha-reviewer" and "beta-reviewer"
  examples/conflicting-skills/alpha-reviewer/SKILL.md
  examples/conflicting-skills/beta-reviewer/SKILL.md
  Similarity: 53% (threshold: 50%)
  Shared terms: bug, code, potential, quality, review, reviewer, skill, style
```

### `skillseal diff <old> <new>`

Compares two versions of a skill (each a `SKILL.md` file or a single-skill
directory) and reports the score delta plus which findings appeared or got
resolved. Exits `1` if the score dropped — useful as a "did this edit make
the skill worse?" CI check.

| Flag | Default | Meaning |
|---|---|---|
| `--format terminal\|json` | `terminal` | Output format. |

### Exit codes (all commands)

| Code | Meaning |
|---|---|
| `0` | Clean, or the gate passed. |
| `1` | Gate failed (`--fail-on` / `--threshold` not met, a conflict was found, or `diff` regressed). |
| `2` | Usage or config error — bad path, no `SKILL.md` found, malformed `skillseal.yaml`/`.toml`. |

A typo'd path can never silently report success: exit `2` is reserved for
"SkillSeal couldn't even run the check," distinct from "the check ran and
found problems" (exit `1`).

## Example output

```
$ uv run skillseal check examples/bad-skill

examples/bad-skill/SKILL.md

Specification  WARN
Quality        WARN
Security       FAIL
Portability    WARN

Issues

WARN  name-directory-mismatch
      Frontmatter 'name' does not match the skill's directory name.
      name: 'helper', directory: 'bad-skill'

WARN  description-too-vague
      Description may not provide enough information for reliable routing.
      matched vague phrase: "helps with tasks"

FAIL  rm-rf
      Potential risk: recursive force-delete command found in a code block.
      1 occurrence(s), e.g. "rm -rf"

FAIL  pipe-to-shell
      Potential risk: downloads remote content and pipes it directly into a shell.
      1 occurrence(s), e.g. "curl https://example.com/install.sh | sh"

WARN  absolute-path
      Skill assumes absolute filesystem paths, which won't exist on other machines.
      /Users/someone/projects/output, /Users/someone/projects/output/tmp

  ... (more findings omitted for brevity — run it yourself to see the rest)

SkillSeal Score: 68/100

Specification   90
Quality         60
Security        40
Portability     90
```

```
$ uv run skillseal test examples/bad-skill

helper

Should trigger       5/5
Should NOT trigger   5/7

Accuracy             83.3%

Failures:

✗ "Help me write a poem"
  Expected: NOT TRIGGER
  Actual: TRIGGER
  Likely reason:
  Matched terms: help
```

## `skillseal.yaml` format

Place a `skillseal.yaml` next to a `SKILL.md` to define its routing tests:

```yaml
version: 1

routing:
  should_trigger:
    - "Review this payment implementation"
    - "Check whether this Stripe integration is secure"

  should_not_trigger:
    - "Write a React button"
    - "Explain Kubernetes"
```

- A missing `skillseal.yaml` means that skill is **skipped**, not failed.
- Empty `should_trigger`/`should_not_trigger` lists are skipped too (no 0/0
  false pass or divide-by-zero).
- Malformed YAML is a usage error (exit `2`), not a crash.

## `skillseal.toml` format

Optional. Overrides a curated set of thresholds repo-wide, without forking a
rule. Discovered by searching upward from the scanned path to the filesystem
root (so one file at your repo root applies everywhere):

```toml
[thresholds]
min_description_length = 20     # default: 10
token_warn_threshold = 3000     # default: 5000
max_lines = 300                 # default: 500
long_section_word_threshold = 1000  # default: 800
max_top_level_sections = 10     # default: 8
conflict_threshold = 0.6        # default: 0.5 — see `conflicts` above
routing_threshold = 0.85        # default: 0.9 — see `test` above
```

- Any threshold you omit keeps its default. An explicit `--threshold` on
  `test`/`conflicts` still overrides whatever `skillseal.toml` sets.
- An unrecognized key, or malformed TOML, is a usage error (exit `2`), not a
  silent no-op.
- Deliberately **not** configurable: the numeric limits that come straight
  from the agentskills.io spec (`name` ≤64 chars, `description` ≤1024,
  `compatibility` ≤500) — overriding those would mean `check` no longer
  validates spec compliance, just a private opinion.

## Using it in CI

As a reusable GitHub Action ([`action.yml`](action.yml)):

```yaml
- uses: pespinel/skillseal@v0.2.1
  with:
    path: ./skills
    fail-on: error
```

Or driven directly, e.g. to also run routing tests:

```yaml
- uses: astral-sh/setup-uv@v3

- name: Check Agent Skills
  run: uvx skillseal check ./skills --fail-on error

- name: Test Agent Skill Routing
  run: uvx skillseal test ./skills
```

This repo's own [`.github/workflows/ci.yml`](.github/workflows/ci.yml) does
the same against `examples/`, plus lint/type-check/unit tests.

### pre-commit

```yaml
repos:
  - repo: https://github.com/pespinel/skillseal
    rev: v0.2.1
    hooks:
      - id: skillseal
```

Runs `skillseal check .` whenever a `SKILL.md` changes.

## Releasing

Publishing to PyPI is automated via
[`.github/workflows/release.yml`](.github/workflows/release.yml) using
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — no
API token stored anywhere.

1. Bump `version` in `pyproject.toml`.
2. Commit, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The workflow verifies the tag matches `pyproject.toml`, builds the sdist
   and wheel, signs a [SLSA build provenance attestation](https://slsa.dev/),
   and publishes to PyPI via OIDC.

To verify a release artifact was actually built by this repo's workflow
(not hand-uploaded) before installing it:

```bash
gh attestation verify dist/skillseal-*.whl --owner pespinel
```

## The score

Deterministic, no LLM involved. Each of the four categories starts at 100 and
loses points per finding:

| Severity | Deduction |
|---|---|
| `ERROR` | -25 |
| `WARNING` | -10 |
| `INFO` | -0 |

`INFO` findings (like "requires docker") are purely descriptive — declaring a
real dependency isn't a defect, so it doesn't cost points. Rules aggregate
repeated occurrences of the *same* issue into one finding with a count, so a
long file can't rack up an artificially low score just from file size.

The total is a weighted sum of the four category scores:

| Category | Weight | Why |
|---|---|---|
| Specification | 30% | Broken/missing metadata breaks loading and routing outright. |
| Quality | 30% | Vague or bloated instructions are the main cause of routing failures. |
| Security | 25% | Real risk, weighted close behind. |
| Portability | 15% | Declared environment dependencies are often expected, not defects. |

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
│   └── json_reporter.py         # stable JSON schema
└── cli.py                        # typer app: check, test, conflicts, diff
```

A `Rule` is `id`, `category`, `severity`, `description`, and
`check(skill) -> list[Finding]`. Most rules are built with `FuncRule`, which
wraps a plain function so adding a check doesn't require a new class.

Routing evaluation is behind a `RoutingEvaluator` protocol with two
implementations:

- **`HeuristicRoutingEvaluator`** (default): fully offline, no API key needed.
  Scores how much of a prompt's distinctive vocabulary (after stopword
  removal and light suffix stripping) is covered by the skill's own name,
  description, and `keywords:`. It's deliberately simple — not real NLP —
  which is also why it's fast, free, and explainable ("Matched terms: ...").
- **`LLMRoutingEvaluator`**: delegates the trigger/no-trigger decision to an
  `LLMProvider` (`complete(prompt) -> str`). `OpenAICompatibleProvider`
  implements this against any OpenAI-compatible `/chat/completions` endpoint,
  configured via `SKILLSEAL_BASE_URL`, `SKILLSEAL_API_KEY`, and
  `SKILLSEAL_MODEL`. Use `--provider llm` to opt in — it's never required.

## Limitations

- Rules are regex/heuristic-based, not a real parser or NLP model — they will
  have false positives and false negatives. Findings are phrased as
  *potential* risk, never certainty.
- The heuristic routing evaluator uses simple tokenization and suffix
  stripping, not real stemming or embeddings; words like "secure" and
  "security" won't match each other.
- Token counts are a rough `len(text) // 4` estimate, not a real tokenizer.
- No sandboxing or dynamic execution — nothing in a skill is ever run.
- No compatibility testing against real agents (Claude Code, Codex, Gemini, etc.).

Planned work is tracked in [Issues](https://github.com/pespinel/skillseal/issues),
not here.

## License

[MIT](LICENSE)
