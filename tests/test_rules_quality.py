from skillseal.rules import quality


def _run(skill) -> set[str]:
    return {f.id for rule in quality.RULES for f in rule.check(skill)}


def test_clean_skill_has_no_findings(make_skill) -> None:
    skill = make_skill(
        description="Use this skill when a user asks for a code review of payment logic.",
        body="# My Skill\n\nReview the code carefully and report issues.\n",
    )
    assert _run(skill) == set()


def test_skill_too_large(make_skill) -> None:
    skill = make_skill(body="word " * 3000)
    assert "skill-too-large" in _run(skill)


def test_repeated_instruction_lines(make_skill) -> None:
    line = "Always double check the output before returning it to the user.\n"
    skill = make_skill(body=line * 3)
    assert "repeated-instructions" in _run(skill)


def test_long_section(make_skill) -> None:
    body = "## Section\n\n" + ("word " * 900)
    skill = make_skill(body=body)
    assert "section-too-long" in _run(skill)


def test_vague_description(make_skill) -> None:
    skill = make_skill(description="Helps with tasks.")
    assert "description-too-vague" in _run(skill)


def test_description_missing_when_to_use(make_skill) -> None:
    skill = make_skill(description="Reviews payment code for correctness and security issues.")
    assert "description-missing-when-to-use" in _run(skill)


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


def test_existing_file_reference_passes(make_skill) -> None:
    skill = make_skill(body="See [the guide](./present.md) for details.\n")
    (skill.dir / "present.md").write_text("hello")
    assert "dangling-file-reference" not in _run(skill)
