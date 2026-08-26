# Commands

## `skillseal check <path>`

Runs every rule (SPECIFICATION, QUALITY, SECURITY, PORTABILITY) against each
discovered skill and prints a per-skill report with a 0-100 score.

| Flag | Default | Meaning |
|---|---|---|
| `--format terminal\|json\|github` | `terminal` | Output format. `github` emits `::warning`/`::error` [workflow-command annotations](https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-an-error-message), one per finding. |
| `--fail-on warning\|error` | `error` | Minimum finding severity that fails the gate. |
| `--min-score <int>` | none | Fail the gate if any skill's score is below this. |
| `--ignore PREFIX` | none | Suppress findings whose id starts with `PREFIX`. Repeatable. |

## `skillseal test <path>`

Runs the routing test cases declared in each skill's `skillseal.yaml`
against a `RoutingEvaluator`, and reports accuracy against `should_trigger`
and `should_not_trigger` prompts. Skills without a `skillseal.yaml` are
skipped, not failed — a summary line (`N skill(s), M with routing tests`)
is always printed so that gap stays visible even without `--require-tests`.

| Flag | Default | Meaning |
|---|---|---|
| `--threshold <float>` | `0.9`\* | Minimum accuracy per skill to pass the gate. |
| `--require-tests` | off | Fail the gate if any discovered skill has no `skillseal.yaml`. |
| `--format terminal\|json` | `terminal` | Output format. |
| `--provider heuristic\|llm` | `heuristic` | Evaluator to use — see [Development](development.md). |

\* Or whatever `routing_threshold` is set to in [`skillseal.toml`](configuration.md#skillsealtoml).

## `skillseal conflicts <path>`

Scans every skill under `path` *together* rather than one at a time, and
flags four things `check`/`test` can't see in isolation:

- **Duplicate names** — two skills declaring the same frontmatter `name`
  (usually a copy-paste leftover).
- **Near-duplicate names** — names one character-edit apart, or equal once
  case/`-`/`_`/whitespace are normalized (`code-review` vs `code_review`).
  Not an exact collision, but confusing for both agents and humans.
- **Routing overlap** — two skills whose vocabulary (name + description +
  `keywords:`) is similar enough that an agent likely can't reliably tell
  them apart, using the same term-matching `HeuristicRoutingEvaluator` uses
  for routing tests, compared pairwise via Jaccard similarity.
- **Containment overlap** — a pair below the Jaccard threshold but where one
  skill's vocabulary is still mostly *contained* in the other's (overlap
  coefficient `|a∩b| / min(|a|,|b|)`). Jaccard is length-sensitive, so a
  terse, vague skill whose vocabulary is a near-subset of a longer, specific
  one scores *low* similarity — even though that's the most dangerous overlap
  there is, since the vague skill can steal routing traffic from the specific
  one without ever looking similar by union-based similarity.

| Flag | Default | Meaning |
|---|---|---|
| `--threshold <float>` | `0.5`\* | Minimum vocabulary similarity (Jaccard) to flag as a routing overlap. |
| `--containment-threshold <float>` | `0.8`\*\* | Minimum containment coefficient to flag, for pairs below `--threshold`. |
| `--against <path>` | none | Check `path` against this broader corpus instead of all-pairs within `path`. |
| `--format terminal\|json` | `terminal` | Output format. |

\* Or `conflict_threshold` in [`skillseal.toml`](configuration.md#skillsealtoml).
\*\* Or `containment_threshold` in [`skillseal.toml`](configuration.md#skillsealtoml).

A pair is only ever reported once: if it clears `--threshold` it's a routing
overlap, not also a containment overlap.

Without `--against`, every skill under `path` is compared against every
other. With it, only pairs involving at least one skill from `path` are
considered — the PR-gate use case: "does the skill I just added or changed
conflict with anything in the existing repo?" without re-auditing the whole
existing corpus against itself on every run:

```bash
skillseal conflicts ./skills/my-new-skill --against ./skills
```

A skill can opt specific others out of routing/containment-overlap comparison
— useful for deliberately similar variants — via `conflict_ignore` in its
frontmatter (matched by name or by a path substring; this only suppresses the
vocabulary-overlap checks, not the two name-based checks, since a real or
near-duplicate name is rarely something you actually want to allow):

```yaml
---
name: my-skill
description: Use this when ...
conflict_ignore:
  - legacy-skill
---
```

Example:

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

## `skillseal diff <old> <new>`

Compares two versions of a skill (each a `SKILL.md` file or a single-skill
directory) and reports the score delta plus which findings appeared or got
resolved. Exits `1` if the score dropped — useful as a "did this edit make
the skill worse?" CI check.

| Flag | Default | Meaning |
|---|---|---|
| `--format terminal\|json` | `terminal` | Output format. |

## `skillseal rules`

Lists every lint rule: id, category, severity, one-line description, and
whether it's tunable via [`skillseal.toml`](configuration.md#skillsealtoml).

| Flag | Default | Meaning |
|---|---|---|
| `--format terminal\|json` | `terminal` | Output format. |

## `skillseal explain <rule-id>`

Shows one rule's category, severity, description, its `skillseal.toml`
threshold key (if configurable), and how to suppress it with `--ignore`.
Exits `2` for an unknown rule id.

```
$ uv run skillseal explain rm-rf

rm-rf  (SECURITY, ERROR)

Flags recursive force-delete commands.

Suppress: skillseal check --ignore rm-rf
```

## Exit codes (all commands)

| Code | Meaning |
|---|---|
| `0` | Clean, or the gate passed. |
| `1` | Gate failed (`--fail-on` / `--min-score` / `--threshold` / `--require-tests` not met, a conflict was found, or `diff` regressed). |
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

WARN  name-directory-mismatch  (line 2)
      Frontmatter 'name' does not match the skill's directory name.
      name: 'helper', directory: 'bad-skill'

WARN  description-too-vague  (line 3)
      Description may not provide enough information for reliable routing.
      matched vague phrase: "helps with tasks"

FAIL  rm-rf  (line 18)
      Potential risk: recursive force-delete command found in a code block.
      1 occurrence(s), e.g. "rm -rf"

FAIL  pipe-to-shell  (line 16)
      Potential risk: downloads remote content and pipes it directly into a shell.
      1 occurrence(s), e.g. "curl https://example.com/install.sh | sh"

WARN  absolute-path  (line 17)
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

1 skill(s), 1 with routing tests

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
