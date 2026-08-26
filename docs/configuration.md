# Configuration

## Frontmatter extensions

Beyond the fields defined by the [agentskills.io spec](https://agentskills.io/specification)
(`name`, `description`, `license`, `compatibility`, `metadata`,
`allowed-tools`), SkillSeal recognizes two extra frontmatter keys of its own.
Both are optional and inert to any other tool — they just won't trigger the
`unknown-frontmatter-keys` finding here.

```yaml
---
name: payment-review
description: Use this skill when reviewing a payment or checkout implementation.
keywords:
  - stripe
  - checkout
  - refund
conflict_ignore:
  - legacy-payment-check
---
```

- **`keywords`** — a list of extra terms fed into the
  `HeuristicRoutingEvaluator` (see [Development](development.md)) alongside
  `name` and `description`, for `test` and `conflicts`. Useful when a skill's
  description doesn't naturally contain the exact words users are likely to
  type.
- **`conflict_ignore`** — see [`conflicts`](commands.md#skillseal-conflicts-path).

## `skillseal.yaml`

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

## `skillseal.toml`

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
conflict_threshold = 0.6        # default: 0.5 — see `conflicts` in Commands
containment_threshold = 0.9     # default: 0.8 — see `conflicts` in Commands
routing_threshold = 0.85        # default: 0.9 — see `test` in Commands
```

- Any threshold you omit keeps its default. An explicit `--threshold` on
  `test`/`conflicts` still overrides whatever `skillseal.toml` sets.
- An unrecognized key, or malformed TOML, is a usage error (exit `2`), not a
  silent no-op.
- Deliberately **not** configurable: the numeric limits that come straight
  from the agentskills.io spec (`name` ≤64 chars, `description` ≤1024,
  `compatibility` ≤500) — overriding those would mean `check` no longer
  validates spec compliance, just a private opinion.

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
