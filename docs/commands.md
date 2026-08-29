# Commands

## `skillseal init <name>`

Scaffolds `<path>/<name>/SKILL.md` and `<path>/<name>/skillseal.yaml` — a
skill that scores 100/100 out of the box, with `[bracketed]` placeholders for
everything you still need to fill in (what it does, when it triggers, and a
starter set of `should_trigger`/`should_not_trigger` routing prompts). The
blank page is the reason nobody writes routing tests; this gives you a
non-blank one.

| Flag | Default | Meaning |
|---|---|---|
| `--path <dir>` | `.` | Directory to create `<name>/` in. |

`<name>` must be lowercase kebab-case (letters, digits, hyphens) — it becomes
both the directory name and the frontmatter `name`, which have to match (see
`name-directory-mismatch`). Fails with exit `2` if the name is invalid or the
target directory already exists.

A freshly-scaffolded skill (or any skill with a `[bracketed]` placeholder
description, a literal `TODO`, `template: true` in its frontmatter, or a
parent directory literally named `template`/`templates`) is recognized as a
template: `description-too-vague`, `description-missing-when-to-use`,
`description-too-short`, and `dangling-file-reference` are suppressed while
it looks unfinished, so `check` doesn't score it like a broken production
skill. `check` surfaces this as an INFO `detected-as-template` finding.

## `skillseal check <path>...`

Runs every rule (SPECIFICATION, QUALITY, SECURITY, PORTABILITY) against each
discovered skill and prints a per-skill report with a 0-100 score. Takes one
or more paths — files or directories, deduped by resolved `SKILL.md`
location — so `skillseal check a/SKILL.md b/SKILL.md` and `skillseal check .`
both work. Config (`skillseal.toml`) is discovered from the *first* path
given.

| Flag | Default | Meaning |
|---|---|---|
| `--format terminal\|json\|github\|sarif` | `terminal` | Output format. `github` emits `::warning`/`::error` [workflow-command annotations](https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-an-error-message), one per finding. `sarif` emits a [SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.json) report — upload it with [`github/codeql-action/upload-sarif`](https://github.com/github/codeql-action/tree/main/upload-sarif) to get findings as code-scanning alerts on the diff, not just a CI log line. |
| `--fail-on warning\|error` | `error` | Minimum finding severity that fails the gate. |
| `--min-score <int>` | none | Fail the gate if any skill's score is below this. |
| `--ignore PREFIX` | none | Suppress findings whose id starts with `PREFIX`. Repeatable. |
| `--changed` | off | Only lint skills with a file that changed between `--base-ref` and `--head-ref`. Takes exactly one path (the search root), not several. |
| `--base-ref <ref>` | none | Git ref to diff against. Required with `--changed`. |
| `--head-ref <ref>` | `HEAD` | Git ref to diff to. |

`--changed` scopes discovery to skills whose *directory* contains a changed
file — not just a changed `SKILL.md` itself, since a change to a bundled
`scripts/`/`references`/`assets` file matters too (security/portability
rules scan those). Exits `0` with "No skills changed" when the diff touches
no skill, distinct from the usage-error exit `2` for "no `SKILL.md` found at
all":

```bash
skillseal check ./skills --changed --base-ref origin/main
```

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
| `--fail-on-new-findings` | off | Fail if *any* new finding appeared, even when the net score didn't regress. A fixed vague description can offset a newly-introduced `absolute-path` WARNING score-wise; this catches that case, which the plain score-delta gate can't see. |

## `skillseal fix <path>`

Applies a deliberately narrow set of safe, deterministic fixes: trailing
whitespace, a leading UTF-8 BOM, and hidden/bidi-override Unicode characters
(the same ones `hidden-unicode-chars` flags). Nothing else — no frontmatter
reordering, no `name-directory-mismatch` rewriting, and never anything that
touches a description. Those need either a round-trip-preserving YAML writer
or a human decision this command isn't in a position to make; see the
`fix.py` module docstring for the full reasoning.

| Flag | Default | Meaning |
|---|---|---|
| `--write` | off | Apply the fixes. Without it, `fix` only reports what it *would* change. |
| `--force` | off | Apply even to a file with uncommitted git changes. Without `--force`, a dirty file is skipped and reported, never silently mutated. |

Dry-run (no `--write`) exits `1` if anything is fixable, `0` if the tree is
already clean — usable as a CI gate the same way `ruff format --check` is:

```bash
skillseal fix ./skills            # report only
skillseal fix ./skills --write    # apply
```

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
| `1` | Gate failed (`--fail-on` / `--min-score` / `--threshold` / `--require-tests` not met, a conflict was found, `diff` regressed, or `fix` found something to fix in dry-run). |
| `2` | Usage or config error — bad path, no `SKILL.md` found, malformed `skillseal.yaml`/`.toml`. |

A typo'd path can never silently report success: exit `2` is reserved for
"SkillSeal couldn't even run the check," distinct from "the check ran and
found problems" (exit `1`).

## Example output

```
$ uv run skillseal check examples/bad-skill

examples/bad-skill/SKILL.md

Specification  FAIL
Quality        WARN
Security       FAIL
Portability    WARN

Issues

FAIL  name-directory-mismatch  (line 2)
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

SkillSeal Score: 50/100

Specification   75
Quality         60
Security        40
Portability     90
```

`name-directory-mismatch` is an ERROR: in VS Code/Copilot, a name that
doesn't match its directory makes the skill silently fail to load — no
error, just absent — the highest-consequence, lowest-ambiguity defect in the
ruleset, so it caps the score at 50 like any other SPECIFICATION error
(see [Exit codes](#exit-codes-all-commands)). `--ignore name-directory-mismatch`
is the escape hatch for a rename you genuinely can't do yet.

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
