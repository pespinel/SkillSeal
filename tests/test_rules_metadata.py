from skillseal.rules import metadata


def _run(skill) -> set[str]:
    return {f.id for rule in metadata.RULES for f in rule.check(skill)}


def test_clean_skill_has_no_findings(make_skill) -> None:
    skill = make_skill(dir_name="my-skill", name="my-skill")
    assert _run(skill) == set()


def test_invalid_frontmatter_short_circuits(make_skill) -> None:
    skill = make_skill(frontmatter_error="mapping values are not allowed here")
    findings = _run(skill)
    assert findings == {"invalid-frontmatter"}


def test_missing_name(make_skill) -> None:
    skill = make_skill(frontmatter={"description": "Use this when doing things."})
    assert "missing-name" in _run(skill)


def test_empty_name(make_skill) -> None:
    skill = make_skill(
        name="", frontmatter={"name": "", "description": "Use this when doing things."}
    )
    assert "empty-name" in _run(skill)


def test_invalid_name_format(make_skill) -> None:
    skill = make_skill(
        name="My Skill!",
        frontmatter={"name": "My Skill!", "description": "Use this when doing things."},
    )
    assert "invalid-name-format" in _run(skill)


def test_name_directory_mismatch(make_skill) -> None:
    skill = make_skill(
        name="other-name",
        dir_name="my-skill",
        frontmatter={"name": "other-name", "description": "Use this when doing things."},
    )
    assert "name-directory-mismatch" in _run(skill)


def test_missing_description(make_skill) -> None:
    skill = make_skill(frontmatter={"name": "my-skill"})
    assert "missing-description" in _run(skill)


def test_description_too_short(make_skill) -> None:
    skill = make_skill(
        description="short", frontmatter={"name": "my-skill", "description": "short"}
    )
    assert "description-too-short" in _run(skill)


def test_description_too_long(make_skill) -> None:
    long_desc = "word " * 300
    skill = make_skill(
        description=long_desc, frontmatter={"name": "my-skill", "description": long_desc}
    )
    assert "description-too-long" in _run(skill)


def test_reserved_word_in_name(make_skill) -> None:
    skill = make_skill(
        name="claude-helper",
        dir_name="claude-helper",
        frontmatter={"name": "claude-helper", "description": "Use this when doing things."},
    )
    assert "reserved-word-in-name" in _run(skill)


def test_reserved_word_not_flagged_when_absent(make_skill) -> None:
    skill = make_skill(dir_name="my-skill", name="my-skill")
    assert "reserved-word-in-name" not in _run(skill)


def test_unknown_frontmatter_keys(make_skill) -> None:
    skill = make_skill(
        frontmatter={
            "name": "my-skill",
            "description": "Use this when doing things.",
            "totally_unknown_key": "value",
        }
    )
    assert "unknown-frontmatter-keys" in _run(skill)


def test_compatibility_is_a_known_key(make_skill) -> None:
    # per the agentskills.io spec, unlike our own former (incorrect) allowlist
    skill = make_skill(
        frontmatter={
            "name": "my-skill",
            "description": "Use this when doing things.",
            "compatibility": "Requires Python 3.12+",
        }
    )
    assert "unknown-frontmatter-keys" not in _run(skill)


def test_top_level_version_is_not_a_known_key(make_skill) -> None:
    # the spec's own example nests custom fields under metadata:, not top-level
    skill = make_skill(
        frontmatter={
            "name": "my-skill",
            "description": "Use this when doing things.",
            "version": "1.0",
        }
    )
    assert "unknown-frontmatter-keys" in _run(skill)


def test_compatibility_too_long(make_skill) -> None:
    skill = make_skill(
        frontmatter={
            "name": "my-skill",
            "description": "Use this when doing things.",
            "compatibility": "x" * 501,
        }
    )
    assert "compatibility-too-long" in _run(skill)
