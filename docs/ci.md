# Using it in CI

As a reusable GitHub Action ([`action.yml`](https://github.com/pespinel/skillseal/blob/main/action.yml)) —
pin to the [latest release tag](https://github.com/pespinel/skillseal/releases/latest),
not `@main`:

```yaml
- uses: pespinel/skillseal@v0.6.0
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

This repo's own [`.github/workflows/ci.yml`](https://github.com/pespinel/skillseal/blob/main/.github/workflows/ci.yml)
does the same against `examples/`, plus lint/type-check/unit tests.

## pre-commit

Also pin `rev` to the [latest release tag](https://github.com/pespinel/skillseal/releases/latest):

```yaml
repos:
  - repo: https://github.com/pespinel/skillseal
    rev: v0.6.0
    hooks:
      - id: skillseal
```

Runs `skillseal check .` whenever a `SKILL.md` changes.
