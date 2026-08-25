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
codes and JSON output. No dashboard, no registry, no cloud — see
[Roadmap](#roadmap) for what's intentionally not here yet.

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <this-repo>
cd skillseal
uv sync
```

Run it directly with `uv run skillseal ...`, or install it as a tool:

```bash
uv tool install .
skillseal --help
```

## Quickstart

```bash
uv run skillseal check examples
uv run skillseal test examples
```

Both commands accept a path to a single `SKILL.md` file, a single skill
directory, or a directory containing many skills (searched recursively).

## Commands

### `skillseal check <path>`

Runs every rule (SPECIFICATION, QUALITY, SECURITY, PORTABILITY) against each
discovered skill and prints a per-skill report with a 0-100 score.

| Flag | Default | Meaning |
|---|---|---|
| `--format terminal\|json` | `terminal` | Output format. |
| `--fail-on warning\|error` | `error` | Minimum finding severity that fails the gate. |

### `skillseal test <path>`

Runs the routing test cases declared in each skill's `skillseal.yaml`
against a `RoutingEvaluator`, and reports accuracy against `should_trigger`
and `should_not_trigger` prompts. Skills without a `skillseal.yaml` are
skipped, not failed.

| Flag | Default | Meaning |
|---|---|---|
| `--threshold <float>` | `0.9` | Minimum accuracy per skill to pass the gate. |
| `--format terminal\|json` | `terminal` | Output format. |
| `--provider heuristic\|llm` | `heuristic` | Evaluator to use (see below). |

### Exit codes (both commands)

| Code | Meaning |
|---|---|
| `0` | Clean, or the gate passed. |
| `1` | Gate failed (`--fail-on` / `--threshold` not met). |
| `2` | Usage or config error — bad path, no `SKILL.md` found, malformed `skillseal.yaml`. |

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

## Using it in CI

```yaml
- name: Check Agent Skills
  run: uv run skillseal check ./skills --fail-on error

- name: Test Agent Skill Routing
  run: uv run skillseal test ./skills
```

This repo's own [`.github/workflows/ci.yml`](.github/workflows/ci.yml) does
the same against `examples/`, plus lint/type-check/unit tests.

## Releasing

Publishing to PyPI is automated via
[`.github/workflows/release.yml`](.github/workflows/release.yml) using
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — no
API token stored anywhere.

1. Bump `version` in `pyproject.toml`.
2. Commit, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The workflow verifies the tag matches `pyproject.toml`, builds the sdist
   and wheel, and publishes to PyPI via OIDC.

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
└── cli.py                        # typer app: check, test
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
- No compatibility testing against real agents (Claude Code, Codex, Gemini,
  etc.) — see the roadmap.

## Roadmap

Documented, not implemented, on purpose — this is an MVP:

- Real execution against Claude Code, Codex, Gemini, and other agents
- A compatibility matrix across agents/environments
- Sandboxed dynamic analysis of skill-invoked commands
- Auto-fix for common findings
- Version-to-version comparison for a skill
- A GitHub App
- A web dashboard
- A skill registry / marketplace
- A hosted/cloud service
- Telemetry
- Skill certification

## License

[MIT](LICENSE)
