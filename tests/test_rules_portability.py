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


def test_requires_network(make_skill) -> None:
    skill = make_skill(body="Fetch data from https://api.example.com/data before continuing.\n")
    assert "requires-network" in _run(skill)


def test_absolute_path_is_warning(make_skill) -> None:
    skill = make_skill(body="Write output to /Users/someone/output.json.\n")
    findings = [
        f for rule in portability.RULES for f in rule.check(skill) if f.id == "absolute-path"
    ]
    assert len(findings) == 1
    assert findings[0].severity.value == "WARNING"
    assert findings[0].line == 5  # single-line body


def test_os_specific_command(make_skill) -> None:
    skill = make_skill(body="On macOS, run `brew install ffmpeg` first.\n")
    assert "os-specific-command" in _run(skill)
    findings = [
        f for rule in portability.RULES for f in rule.check(skill) if f.id == "os-specific-command"
    ]
    assert findings[0].line == 5


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
