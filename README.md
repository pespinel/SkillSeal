# SkillSeal

[![PyPI](https://img.shields.io/pypi/v/skillseal)](https://pypi.org/project/skillseal/)
[![CI](https://github.com/pespinel/skillseal/actions/workflows/ci.yml/badge.svg)](https://github.com/pespinel/skillseal/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Test your Agent Skills before your agents do.**

`SKILL.md` files can be syntactically valid and still be bad: a vague
description that never routes correctly, an oversized file that eats context,
a `curl | sh` buried in a code block, a hardcoded `/Users/you/...` path that
only works on your machine. SkillSeal is a local-first, offline-first CLI
that lints, scores, and routing-tests `SKILL.md` files — catching what a
manual read-through misses, before an agent does.

![skillseal check output: two WARNs, a FAIL on rm-rf, a WARN on an absolute path, score 86/100](https://raw.githubusercontent.com/pespinel/SkillSeal/main/docs/assets/example-check-output.svg)

## What it catches

| Category | Catches things like |
|---|---|
| **Specification** | Invalid frontmatter, a `name` that doesn't match its directory |
| **Quality** | Vague descriptions, oversized files, dangling file references |
| **Security** | `rm -rf` / `curl \| sh` in a code block, secret-file reads |
| **Portability** | Hardcoded `/Users/you/...` paths, OS-specific commands |

**Full docs: <https://pespinel.github.io/SkillSeal/>**

## Installation

```bash
uv tool install skillseal
# or: pipx install skillseal
# or: pip install skillseal
```

One-off, no install:

```bash
uvx skillseal check ./skills
```

## Quickstart

```bash
skillseal init my-new-skill       # scaffold a skill that scores 100/100
skillseal check ./skills          # lint: spec, quality, security, portability
skillseal test ./skills           # routing tests (skillseal.yaml)
skillseal conflicts ./skills      # duplicate names / routing overlap between skills
skillseal diff old/ new/          # score delta between two versions of a skill
```

See the [full command reference](https://pespinel.github.io/SkillSeal/commands/),
[`skillseal.yaml`/`skillseal.toml` config](https://pespinel.github.io/SkillSeal/configuration/),
and [CI integration](https://pespinel.github.io/SkillSeal/ci/) (GitHub Action,
pre-commit hook) on the docs site.

## Contributing

See [AGENTS.md](AGENTS.md) for setup, quality gates, and how to add a rule.
Planned work is tracked in [Issues](https://github.com/pespinel/skillseal/issues).

## License

[MIT](LICENSE)
