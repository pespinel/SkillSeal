from skillseal.rules import quality


def _run(skill) -> set[str]:
    return {f.id for rule in quality.RULES for f in rule.check(skill)}


def _find(skill, finding_id: str):
    return next(f for rule in quality.RULES for f in rule.check(skill) if f.id == finding_id)


def test_clean_skill_has_no_findings(make_skill) -> None:
    skill = make_skill(
        description="Use this skill when a user asks for a code review of payment logic.",
        body="# My Skill\n\nReview the code carefully and report issues.\n",
    )
    assert _run(skill) == set()


def test_skill_too_large(make_skill) -> None:
    skill = make_skill(body="word " * 6000)
    assert "skill-too-large" in _run(skill)


def test_too_many_lines(make_skill) -> None:
    skill = make_skill(body="\n".join(f"line {i}" for i in range(600)))
    assert "too-many-lines" in _run(skill)


def test_repeated_instruction_lines(make_skill) -> None:
    line = "Always double check the output before returning it to the user.\n"
    skill = make_skill(body=line * 3)
    assert "repeated-instructions" in _run(skill)
    # body starts at file line 5 (4-line frontmatter block above it); first
    # occurrence of the repeated line is body's own first line
    assert _find(skill, "repeated-instructions").line == 5


def test_repeated_code_lines_not_flagged(make_skill) -> None:
    # a repeated import/line across two examples isn't a repeated
    # *instruction* — 58% of this rule's real-world firings were exactly
    # this on a 1,142-skill corpus (#28)
    body = (
        "```python\nimport polars as pl\nprint('one')\n```\n\n"
        "```python\nimport polars as pl\nprint('two')\n```\n"
    )
    skill = make_skill(body=body)
    assert "repeated-instructions" not in _run(skill)


def test_repeated_table_rows_not_flagged(make_skill) -> None:
    # a repeated markdown table separator/header is structure, not a
    # duplicated instruction — 8.4% of real-world firings (#28)
    body = (
        "| Format | Skill | Capabilities |\n|---|---|---|\n| a | b | c |\n\n"
        "Some text in between.\n\n"
        "| Format | Skill | Capabilities |\n|---|---|---|\n| d | e | f |\n"
    )
    skill = make_skill(body=body)
    assert "repeated-instructions" not in _run(skill)


def test_long_section(make_skill) -> None:
    body = "## Section\n\n" + ("word " * 900)
    skill = make_skill(body=body)
    assert "section-too-long" in _run(skill)
    assert _find(skill, "section-too-long").line == 5  # the '## Section' heading


def test_vague_description(make_skill) -> None:
    skill = make_skill(description="Helps with tasks.")
    assert "description-too-vague" in _run(skill)
    assert _find(skill, "description-too-vague").line == 3  # 'description:' frontmatter line


def test_short_description_flagged_by_word_count(make_skill) -> None:
    # the phrase blocklist alone fired 0/1142 times on a real corpus (#28) —
    # this description matches none of those phrases but is still too short
    # to plausibly state when the skill applies
    skill = make_skill(description="Analyzes and summarizes quarterly reports.")
    assert "description-too-vague" in _run(skill)
    assert "word(s)" in (_find(skill, "description-too-vague").detail or "")


def test_ten_word_description_not_flagged_as_vague(make_skill) -> None:
    # exactly at the configured floor: shouldn't trigger
    skill = make_skill(description="Use this skill when doing the thing that needs doing.")
    assert "description-too-vague" not in _run(skill)


def test_description_missing_when_to_use(make_skill) -> None:
    skill = make_skill(description="Reviews payment code for correctness and security issues.")
    assert "description-missing-when-to-use" in _run(skill)
    assert _find(skill, "description-missing-when-to-use").line == 3


def test_description_with_when_cue_passes(make_skill) -> None:
    skill = make_skill(
        description="Use this skill when reviewing payment code for security issues."
    )
    assert "description-missing-when-to-use" not in _run(skill)


def test_too_many_responsibilities(make_skill) -> None:
    body = "\n\n".join(f"## Section {i}\n\nDo thing {i}." for i in range(10))
    skill = make_skill(body=body)
    assert "too-many-responsibilities" in _run(skill)


def test_dangling_file_reference(make_skill) -> None:
    skill = make_skill(body="See [the guide](./missing-file.md) for details.\n")
    assert "dangling-file-reference" in _run(skill)
    assert _find(skill, "dangling-file-reference").line == 5


def test_existing_file_reference_passes(make_skill) -> None:
    skill = make_skill(body="See [the guide](./present.md) for details.\n")
    (skill.dir / "present.md").write_text("hello")
    assert "dangling-file-reference" not in _run(skill)


def test_deep_file_reference(make_skill) -> None:
    skill = make_skill(body="See [the guide](./references/sub/deep.md) for details.\n")
    assert "deep-file-reference" in _run(skill)


def test_one_level_file_reference_passes(make_skill) -> None:
    skill = make_skill(body="See [the guide](./references/shallow.md) for details.\n")
    assert "deep-file-reference" not in _run(skill)


def test_bare_file_reference_passes(make_skill) -> None:
    skill = make_skill(body="See [the guide](./shallow.md) for details.\n")
    assert "deep-file-reference" not in _run(skill)


def test_metadata_token_budget_exceeded(make_skill) -> None:
    skill = make_skill(description="word " * 200)
    assert "metadata-token-budget" in _run(skill)


def test_metadata_token_budget_within_limit_not_flagged(make_skill) -> None:
    skill = make_skill(description="Use this skill when doing the thing that needs doing.")
    assert "metadata-token-budget" not in _run(skill)
