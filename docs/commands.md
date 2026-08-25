# Commands

## `skillseal check <path>`

Runs every rule (SPECIFICATION, QUALITY, SECURITY, PORTABILITY) against each
discovered skill and prints a per-skill report with a 0-100 score.

| Flag | Default | Meaning |
|---|---|---|
| `--format terminal\|json` | `terminal` | Output format. |
| `--fail-on warning\|error` | `error` | Minimum finding severity that fails the gate. |
| `--ignore PREFIX` | none | Suppress findings whose id starts with `PREFIX`. Repeatable. |

## `skillseal test <path>`

Runs the routing test cases declared in each skill's `skillseal.yaml`
against a `RoutingEvaluator`, and reports accuracy against `should_trigger`
and `should_not_trigger` prompts. Skills without a `skillseal.yaml` are
skipped, not failed.

| Flag | Default | Meaning |
|---|---|---|
| `--threshold <float>` | `0.9`\* | Minimum accuracy per skill to pass the gate. |
| `--format terminal\|json` | `terminal` | Output format. |
| `--provider heuristic\|llm` | `heuristic` | Evaluator to use — see [Development](development.md). |

\* Or whatever `routing_threshold` is set to in [`skillseal.toml`](configuration.md#skillsealtoml).

## `skillseal conflicts <path>`

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

\* Or `conflict_threshold` in [`skillseal.toml`](configuration.md#skillsealtoml).

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

## Exit codes (all commands)

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
