import json
from pathlib import Path

from typer.testing import CliRunner

from skillseal.cli import app

runner = CliRunner()
EXAMPLES = Path(__file__).parent.parent / "examples"


def test_check_good_skill_exits_zero() -> None:
    result = runner.invoke(app, ["check", str(EXAMPLES / "good-skill"), "--fail-on", "error"])
    assert result.exit_code == 0


def test_check_bad_skill_exits_one_on_error_gate() -> None:
    result = runner.invoke(app, ["check", str(EXAMPLES / "bad-skill"), "--fail-on", "error"])
    assert result.exit_code == 1


def test_check_bad_skill_passes_lower_gate_ignored() -> None:
    # --fail-on warning is stricter than error, bad-skill has warnings too either way
    result = runner.invoke(app, ["check", str(EXAMPLES / "bad-skill"), "--fail-on", "warning"])
    assert result.exit_code == 1


def test_check_nonexistent_path_exits_two() -> None:
    result = runner.invoke(app, ["check", str(EXAMPLES / "does-not-exist")])
    assert result.exit_code == 2


def test_check_path_with_no_skills_exits_two(tmp_path: Path) -> None:
    result = runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == 2


def test_check_ignore_prefix_suppresses_matching_findings() -> None:
    result = runner.invoke(
        app,
        ["check", str(EXAMPLES / "bad-skill"), "--format", "json", "--ignore", "rm-rf"],
    )
    payload = json.loads(result.stdout)
    ids = {f["id"] for f in payload["skills"][0]["findings"]}
    assert "rm-rf" not in ids


def test_check_json_format_is_valid_json() -> None:
    result = runner.invoke(app, ["check", str(EXAMPLES / "good-skill"), "--format", "json"])
    payload = json.loads(result.stdout)
    assert payload["version"] == 1
    assert len(payload["skills"]) == 1


def test_routing_good_skill_exits_zero() -> None:
    result = runner.invoke(app, ["test", str(EXAMPLES / "good-skill")])
    assert result.exit_code == 0


def test_routing_bad_skill_exits_one_at_default_threshold() -> None:
    result = runner.invoke(app, ["test", str(EXAMPLES / "bad-skill")])
    assert result.exit_code == 1


def test_routing_bad_skill_passes_low_threshold() -> None:
    result = runner.invoke(app, ["test", str(EXAMPLES / "bad-skill"), "--threshold", "0.5"])
    assert result.exit_code == 0


def test_routing_json_format_is_valid_json() -> None:
    result = runner.invoke(app, ["test", str(EXAMPLES / "good-skill"), "--format", "json"])
    payload = json.loads(result.stdout)
    assert payload["version"] == 1


def test_routing_llm_provider_without_config_exits_two(monkeypatch) -> None:
    monkeypatch.delenv("SKILLSEAL_BASE_URL", raising=False)
    monkeypatch.delenv("SKILLSEAL_MODEL", raising=False)
    result = runner.invoke(app, ["test", str(EXAMPLES / "good-skill"), "--provider", "llm"])
    assert result.exit_code == 2


def test_conflicts_clean_directory_exits_zero() -> None:
    result = runner.invoke(app, ["conflicts", str(EXAMPLES / "good-skill")])
    assert result.exit_code == 0


def test_conflicts_detects_both_kinds_and_exits_one() -> None:
    result = runner.invoke(app, ["conflicts", str(EXAMPLES / "conflicting-skills")])
    assert result.exit_code == 1


def test_conflicts_json_format_is_valid_json() -> None:
    result = runner.invoke(
        app, ["conflicts", str(EXAMPLES / "conflicting-skills"), "--format", "json"]
    )
    payload = json.loads(result.stdout)
    assert payload["has_conflicts"] is True
    assert len(payload["duplicate_names"]) == 1
    assert len(payload["routing_overlaps"]) == 1


def test_conflicts_nonexistent_path_exits_two() -> None:
    result = runner.invoke(app, ["conflicts", str(EXAMPLES / "does-not-exist")])
    assert result.exit_code == 2


def test_conflicts_no_skills_found_exits_two(tmp_path: Path) -> None:
    result = runner.invoke(app, ["conflicts", str(tmp_path)])
    assert result.exit_code == 2


def test_conflicts_against_nonexistent_path_exits_two(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["conflicts", str(EXAMPLES / "good-skill"), "--against", str(tmp_path / "nope")],
    )
    assert result.exit_code == 2


def test_conflicts_against_flag_scopes_to_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "SKILL.md").write_text(
        "---\nname: good-skill\ndescription: Use this skill when doing the target thing.\n---\n"
    )
    result = runner.invoke(
        app,
        [
            "conflicts",
            str(target),
            "--against",
            str(EXAMPLES / "conflicting-skills"),
            "--format",
            "json",
        ],
    )
    payload = json.loads(result.stdout)
    assert payload["skills_scanned"] == 1


def test_malformed_config_exits_two(tmp_path: Path) -> None:
    (tmp_path / "skillseal.toml").write_text("[thresholds\nbroken\n")
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: Use this skill when doing things.\n---\n"
    )
    result = runner.invoke(app, ["check", str(skill_dir)])
    assert result.exit_code == 2
