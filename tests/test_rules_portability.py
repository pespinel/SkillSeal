from skillguard.rules import portability


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


def test_os_specific_command(make_skill) -> None:
    skill = make_skill(body="On macOS, run `brew install ffmpeg` first.\n")
    assert "os-specific-command" in _run(skill)
