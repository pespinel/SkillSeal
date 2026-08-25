# Using it in CI

As a reusable GitHub Action ([`action.yml`](https://github.com/pespinel/skillseal/blob/main/action.yml)):

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

This repo's own [`.github/workflows/ci.yml`](https://github.com/pespinel/skillseal/blob/main/.github/workflows/ci.yml)
does the same against `examples/`, plus lint/type-check/unit tests.

## pre-commit

```yaml
repos:
  - repo: https://github.com/pespinel/skillseal
    rev: v0.2.1
    hooks:
      - id: skillseal
```

Runs `skillseal check .` whenever a `SKILL.md` changes.
