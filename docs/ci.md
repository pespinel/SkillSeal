# Using it in CI

As a reusable GitHub Action ([`action.yml`](https://github.com/pespinel/skillseal/blob/main/action.yml)) —
pin to the [latest release tag](https://github.com/pespinel/skillseal/releases/latest),
not `@main`:

```yaml
- uses: pespinel/skillseal@v0.19.0
  with:
    path: ./skills
    fail-on: error
    min-score: 80
```

Or driven directly, e.g. to also run routing tests:

```yaml
- uses: astral-sh/setup-uv@v3

- name: Check Agent Skills
  run: uvx skillseal check ./skills --fail-on error --min-score 80

- name: Test Agent Skill Routing
  run: uvx skillseal test ./skills --require-tests
```

`--require-tests` fails the gate if any discovered skill has no `skillseal.yaml` —
without it, a repo that has never written a routing test still exits 0
("skipped", not "passed"). The action (`action.yml`) only wraps `check`; run
`skillseal test` directly, as above, to gate on routing tests in CI.

This repo's own [`.github/workflows/ci.yml`](https://github.com/pespinel/skillseal/blob/main/.github/workflows/ci.yml)
does the same against `examples/`, plus lint/type-check/unit tests.

## GitHub code scanning

`--format sarif` turns findings into code-scanning alerts on the file/line
they fired on, instead of a log line someone has to go read:

```yaml
- uses: astral-sh/setup-uv@v3

- name: Check Agent Skills (SARIF)
  run: uvx skillseal check ./skills --format sarif > skillseal.sarif
  continue-on-error: true  # let the upload step run even if check exits 1

- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: skillseal.sarif
```

Requires GitHub code scanning to be enabled for the repo (Settings → Code
security → Code scanning). SECURITY-category findings are the natural fit
here — they're the ones worth surfacing as an alert, not just a check-run
comment.

## pre-commit

Also pin `rev` to the [latest release tag](https://github.com/pespinel/skillseal/releases/latest):

```yaml
repos:
  - repo: https://github.com/pespinel/skillseal
    rev: v0.19.0
    hooks:
      - id: skillseal
```

Runs `skillseal check .` whenever a `SKILL.md` changes.
