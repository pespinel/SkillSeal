from skillseal.rules import portability


def _run(skill) -> set[str]:
    return {f.id for rule in portability.RULES for f in rule.check(skill)}


def test_clean_skill_has_no_findings(make_skill) -> None:
    skill = make_skill(body="# My Skill\n\nSummarize the findings in a short report.\n")
    assert _run(skill) == set()


def test_requires_tools_is_informational(make_skill) -> None:
    skill = make_skill(body="Install dependencies with docker and git before running.\n")
    findings = [
        f for rule in portability.RULES for f in rule.check(skill) if f.id == "requires-tools"
    ]
    assert len(findings) == 1
    assert findings[0].severity.value == "INFO"
    assert "docker" in (findings[0].detail or "")
    assert "git" in (findings[0].detail or "")


def test_node_as_figma_node_not_flagged(make_skill) -> None:
    # "node" collides with the common Figma/DOM/graph-tree noun — found via a
    # real corpus where 7/16 "Requires: node" hits were pure Figma-node
    # mentions with zero relation to Node.js
    skill = make_skill(body="Read the node id from the registry's Figma node column.\n")
    assert "requires-tools" not in _run(skill)


def test_node_id_url_param_in_code_span_not_flagged(make_skill) -> None:
    # a Figma URL example (`?node-id=<id>`) can itself live inside a code
    # span — restricting to code spans alone doesn't exclude this one, the
    # word-boundary match needs its own "node-id"/"node id" exclusion
    skill = make_skill(body="```\nhttps://figma.com/design/<key>?node-id=<id>\n```\n")
    assert "requires-tools" not in _run(skill)


def test_bare_figma_node_in_inline_code_not_flagged(make_skill) -> None:
    # a literal column-name reference like `Figma node` can be written in
    # inline code too, not just fenced blocks
    skill = make_skill(body="Read the `Figma node` column from the registry.\n")
    assert "requires-tools" not in _run(skill)


def test_node_command_in_fenced_code_flagged(make_skill) -> None:
    skill = make_skill(body="Run it:\n\n```bash\nnode script.mjs --check\n```\n")
    findings = [
        f for rule in portability.RULES for f in rule.check(skill) if f.id == "requires-tools"
    ]
    assert len(findings) == 1
    assert "node" in (findings[0].detail or "")


def test_node_command_in_indented_fenced_code_flagged(make_skill) -> None:
    # a fence nested inside a numbered list step is indented past column 0 —
    # found via the same real corpus (22/42 skills use this pattern)
    skill = make_skill(body="1. Run it:\n\n   ```bash\n   node script.mjs --check\n   ```\n")
    assert "requires-tools" in _run(skill)


def test_node_in_compatibility_field_flagged(make_skill) -> None:
    skill = make_skill(
        frontmatter={
            "name": "my-skill",
            "description": "Use this when doing things.",
            "compatibility": "Requires node and npm",
        }
    )
    findings = [
        f for rule in portability.RULES for f in rule.check(skill) if f.id == "requires-tools"
    ]
    assert len(findings) == 1
    assert "node" in (findings[0].detail or "")


def test_description_block_scalar_flagged(make_skill) -> None:
    # Claude Code renders 'description: |' as a bare '|' — anthropics/claude-code#10589
    skill = make_skill(
        frontmatter={"name": "my-skill", "description": "|\n  Use this skill when doing things."}
    )
    assert "description-block-scalar" in _run(skill)


def test_plain_scalar_description_not_flagged(make_skill) -> None:
    skill = make_skill(
        frontmatter={"name": "my-skill", "description": "Use this skill when doing things."}
    )
    assert "description-block-scalar" not in _run(skill)


def test_folded_scalar_description_not_flagged(make_skill) -> None:
    # anthropics/claude-code#10589 reproduces and cites '|' (literal style)
    # specifically — it makes no claim about '>' (folded style), so this
    # rule doesn't extend the claim to something the source never verified
    skill = make_skill(
        frontmatter={"name": "my-skill", "description": ">\n  Use this skill when doing things."}
    )
    assert "description-block-scalar" not in _run(skill)


def test_allowed_tools_flagged_as_experimental(make_skill) -> None:
    skill = make_skill(
        frontmatter={
            "name": "my-skill",
            "description": "Use this skill when doing things.",
            "allowed-tools": "Read Bash(git:*)",
        }
    )
    findings = [
        f
        for rule in portability.RULES
        for f in rule.check(skill)
        if f.id == "allowed-tools-experimental"
    ]
    assert len(findings) == 1
    assert findings[0].severity.value == "INFO"
    assert "agentskills.io/specification" in (findings[0].detail or "")


def test_no_allowed_tools_not_flagged(make_skill) -> None:
    skill = make_skill()
    assert "allowed-tools-experimental" not in _run(skill)


def test_requires_network_verb(make_skill) -> None:
    skill = make_skill(body="This skill needs internet access to fetch remote data.\n")
    assert "requires-network" in _run(skill)


def test_requires_network_url_in_code_span(make_skill) -> None:
    skill = make_skill(body="```bash\ncurl https://api.example.com/data\n```\n")
    findings = [
        f for rule in portability.RULES for f in rule.check(skill) if f.id == "requires-network"
    ]
    assert len(findings) == 1
    assert findings[0].line == 6


def test_plain_doc_link_does_not_imply_network(make_skill) -> None:
    # a bare https:// link in prose is a doc reference, not a dependency —
    # almost every skill has one; only a URL a skill actually runs (inside a
    # code block) or an explicit network verb should count (see #19)
    skill = make_skill(body="See https://example.com/docs for more details.\n")
    assert "requires-network" not in _run(skill)


def test_absolute_path_is_warning(make_skill) -> None:
    skill = make_skill(body="Write output to /Users/someone/output.json.\n")
    findings = [
        f for rule in portability.RULES for f in rule.check(skill) if f.id == "absolute-path"
    ]
    assert len(findings) == 1
    assert findings[0].severity.value == "WARNING"
    assert findings[0].line == 5  # single-line body


def test_tmp_path_not_flagged(make_skill) -> None:
    # /tmp is the standard scratch dir on every platform, unlike /Users/... (#19)
    skill = make_skill(body="Write intermediate output to /tmp/build-output.log.\n")
    assert "absolute-path" not in _run(skill)


def test_os_specific_command(make_skill) -> None:
    skill = make_skill(body="On macOS, run `brew install ffmpeg` first.\n")
    assert "os-specific-command" in _run(skill)
    findings = [
        f for rule in portability.RULES for f in rule.check(skill) if f.id == "os-specific-command"
    ]
    assert findings[0].line == 5


def test_bare_os_mention_is_info_not_warning(make_skill) -> None:
    # documenting supported platforms shouldn't cost a WARNING like an
    # actual OS-specific command does (#19)
    skill = make_skill(body="Works on macOS and Linux.\n")
    assert "os-specific-command" not in _run(skill)
    findings = [f for rule in portability.RULES for f in rule.check(skill) if f.id == "os-mention"]
    assert len(findings) == 1
    assert findings[0].severity.value == "INFO"


def test_os_mention_suppressed_when_compatibility_declared(make_skill) -> None:
    skill = make_skill(
        body="Works on macOS and Linux.\n",
        frontmatter={
            "name": "my-skill",
            "description": "Use this when doing things.",
            "compatibility": "macOS and Linux only",
        },
    )
    assert "os-mention" not in _run(skill)


def test_declared_compatibility_surfaced(make_skill) -> None:
    skill = make_skill(
        frontmatter={
            "name": "my-skill",
            "description": "Use this when doing things.",
            "compatibility": "Requires git, docker, jq, and access to the internet",
        }
    )
    findings = [
        f
        for rule in portability.RULES
        for f in rule.check(skill)
        if f.id == "declared-compatibility"
    ]
    assert len(findings) == 1
    assert findings[0].severity.value == "INFO"
    assert "Requires git" in (findings[0].detail or "")
    assert findings[0].line == 4  # 'compatibility:' is the 3rd frontmatter key
    # the free-text compatibility field also feeds the existing tool/network scans
    assert "requires-tools" in _run(skill)
    assert "requires-network" in _run(skill)
