import json
import subprocess
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
    assert payload["version"] == 2
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
    assert payload["version"] == 2


def test_routing_require_tests_fails_on_missing_config() -> None:
    # examples/conflicting-skills has SKILL.md files but no skillseal.yaml
    result = runner.invoke(app, ["test", str(EXAMPLES / "conflicting-skills"), "--require-tests"])
    assert result.exit_code == 1


def test_routing_without_require_tests_passes_vacuously() -> None:
    result = runner.invoke(app, ["test", str(EXAMPLES / "conflicting-skills")])
    assert result.exit_code == 0


def test_routing_summary_line_reports_tested_count() -> None:
    result = runner.invoke(app, ["test", str(EXAMPLES / "good-skill")])
    assert "1 skill(s), 1 with routing tests" in result.stdout


def test_routing_json_reports_skills_with_tests() -> None:
    result = runner.invoke(app, ["test", str(EXAMPLES / "conflicting-skills"), "--format", "json"])
    payload = json.loads(result.stdout)
    assert payload["skills_scanned"] == 3
    assert payload["skills_with_tests"] == 0


def test_check_min_score_fails_when_below_threshold() -> None:
    result = runner.invoke(app, ["check", str(EXAMPLES / "good-skill"), "--min-score", "101"])
    assert result.exit_code == 1


def test_check_min_score_passes_when_met() -> None:
    result = runner.invoke(app, ["check", str(EXAMPLES / "good-skill"), "--min-score", "100"])
    assert result.exit_code == 0


def test_routing_trigger_threshold_configurable_via_toml(tmp_path: Path) -> None:
    skill_dir = tmp_path / "helper"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: helper\ndescription: Use this skill when reviewing payment code.\n---\n"
    )
    prompt = "Please look at this payment thing among many unrelated other words here"
    (skill_dir / "skillseal.yaml").write_text(f'routing:\n  should_trigger:\n    - "{prompt}"\n')

    default_result = runner.invoke(app, ["test", str(skill_dir)])
    assert default_result.exit_code == 1

    (tmp_path / "skillseal.toml").write_text("[thresholds]\nrouting_trigger_threshold = 0.05\n")
    loosened_result = runner.invoke(app, ["test", str(skill_dir)])
    assert loosened_result.exit_code == 0


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


def test_diff_fail_on_new_findings_catches_a_masked_regression(tmp_path: Path) -> None:
    # net score improves (a vague description gets fixed) but a new,
    # unrelated finding (absolute-path) is introduced — plain --fail-on-new-
    # findings-less `regressed` can't see this, --fail-on-new-findings can
    old = tmp_path / "old" / "helper"
    old.mkdir(parents=True)
    (old / "SKILL.md").write_text("---\nname: helper\ndescription: Helps with tasks.\n---\n")
    new = tmp_path / "new" / "helper"
    new.mkdir(parents=True)
    (new / "SKILL.md").write_text(
        "---\nname: helper\ndescription: Use this skill when the user needs help "
        "completing a specific task.\n---\nWrite output to /Users/you/results.\n"
    )

    plain = runner.invoke(app, ["diff", str(old), str(new)])
    assert plain.exit_code == 0

    gated = runner.invoke(app, ["diff", str(old), str(new), "--fail-on-new-findings"])
    assert gated.exit_code == 1


def test_diff_improvement_exits_zero() -> None:
    result = runner.invoke(app, ["diff", str(EXAMPLES / "bad-skill"), str(EXAMPLES / "good-skill")])
    assert result.exit_code == 0


def test_diff_regression_exits_one() -> None:
    result = runner.invoke(app, ["diff", str(EXAMPLES / "good-skill"), str(EXAMPLES / "bad-skill")])
    assert result.exit_code == 1


def test_diff_json_format_is_valid_json() -> None:
    result = runner.invoke(
        app,
        ["diff", str(EXAMPLES / "bad-skill"), str(EXAMPLES / "good-skill"), "--format", "json"],
    )
    payload = json.loads(result.stdout)
    assert payload["score_delta"] == payload["new"]["score"] - payload["old"]["score"]
    assert payload["regressed"] is False


def test_diff_nonexistent_old_path_exits_two() -> None:
    result = runner.invoke(
        app, ["diff", str(EXAMPLES / "does-not-exist"), str(EXAMPLES / "good-skill")]
    )
    assert result.exit_code == 2


def test_diff_target_with_multiple_skills_exits_two() -> None:
    result = runner.invoke(
        app, ["diff", str(EXAMPLES / "conflicting-skills"), str(EXAMPLES / "good-skill")]
    )
    assert result.exit_code == 2


def test_fix_dry_run_exits_one_when_something_to_fix(tmp_path: Path) -> None:
    skill_dir = tmp_path / "helper"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: helper\ndescription: Use this skill when doing things.\n---\nBody.   \n"
    )
    result = runner.invoke(app, ["fix", str(tmp_path)])
    assert result.exit_code == 1
    assert "trailing-whitespace" in result.stdout


def test_fix_dry_run_exits_zero_when_clean(tmp_path: Path) -> None:
    skill_dir = tmp_path / "helper"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: helper\ndescription: Use this skill when doing things.\n---\nBody.\n"
    )
    result = runner.invoke(app, ["fix", str(tmp_path)])
    assert result.exit_code == 0


def test_fix_write_applies_and_exits_zero(tmp_path: Path) -> None:
    skill_dir = tmp_path / "helper"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: helper\ndescription: Use this skill when doing things.\n---\nBody.   \n"
    )
    result = runner.invoke(app, ["fix", str(tmp_path), "--write"])
    assert result.exit_code == 0
    assert "fixed" in result.stdout
    assert not skill_md.read_text().endswith("Body.   \n")


def test_fix_nonexistent_path_exits_two() -> None:
    result = runner.invoke(app, ["fix", str(EXAMPLES / "does-not-exist")])
    assert result.exit_code == 2


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_check_changed_only_lints_touched_skill(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    for name in ("alpha", "beta"):
        skill_dir = root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Use this skill when doing {name} things.\n---\n"
            "Body.\n"
        )
    _git("init", "-q", cwd=tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "x", cwd=tmp_path)
    _git("branch", "base", cwd=tmp_path)
    (root / "beta" / "SKILL.md").write_text((root / "beta" / "SKILL.md").read_text() + "Extra.\n")
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "y", cwd=tmp_path)

    result = runner.invoke(
        app, ["check", str(root), "--changed", "--base-ref", "base", "--format", "json"]
    )
    payload = json.loads(result.stdout)
    assert len(payload["skills"]) == 1
    assert payload["skills"][0]["name"] == "beta"


def test_check_changed_nothing_touched_exits_zero(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill_dir = root / "alpha"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: Use this skill when doing alpha things.\n---\nBody.\n"
    )
    _git("init", "-q", cwd=tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "x", cwd=tmp_path)

    result = runner.invoke(app, ["check", str(root), "--changed", "--base-ref", "HEAD"])
    assert result.exit_code == 0
    assert "No skills changed" in result.stdout


def test_check_changed_without_base_ref_exits_two() -> None:
    result = runner.invoke(app, ["check", str(EXAMPLES / "good-skill"), "--changed"])
    assert result.exit_code == 2


def test_check_changed_rejects_multiple_paths() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(EXAMPLES / "good-skill"),
            str(EXAMPLES / "bad-skill"),
            "--changed",
            "--base-ref",
            "HEAD",
        ],
    )
    assert result.exit_code == 2


def test_check_accepts_multiple_explicit_paths() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(EXAMPLES / "good-skill" / "SKILL.md"),
            str(EXAMPLES / "bad-skill" / "SKILL.md"),
            "--format",
            "json",
        ],
    )
    payload = json.loads(result.stdout)
    names = {s["name"] for s in payload["skills"]}
    assert names == {"good-skill", "helper"}


def test_check_multiple_paths_dedupes_by_resolved_path() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(EXAMPLES / "good-skill" / "SKILL.md"),
            str(EXAMPLES / "good-skill" / "SKILL.md"),
            "--format",
            "json",
        ],
    )
    payload = json.loads(result.stdout)
    assert len(payload["skills"]) == 1


def test_check_one_bad_path_among_many_exits_two() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(EXAMPLES / "good-skill" / "SKILL.md"),
            str(EXAMPLES / "does-not-exist" / "SKILL.md"),
        ],
    )
    assert result.exit_code == 2


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "skillseal" in result.stdout
    assert result.stdout.strip() != "skillseal 0.1.0"  # the old hardcoded value


def test_version_matches_pyproject() -> None:
    import tomllib
    from pathlib import Path

    from skillseal import __version__

    pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    assert __version__ == pyproject["project"]["version"]


def test_rules_exits_zero_and_lists_known_id() -> None:
    result = runner.invoke(app, ["rules"])
    assert result.exit_code == 0
    assert "rm-rf" in result.stdout


def test_rules_json_format_is_valid_json() -> None:
    result = runner.invoke(app, ["rules", "--format", "json"])
    payload = json.loads(result.stdout)
    assert payload["version"] == 2
    ids = {r["id"] for r in payload["rules"]}
    assert "rm-rf" in ids
    configurable = {r["id"]: r["threshold_field"] for r in payload["rules"]}
    assert configurable["description-too-short"] == "min_description_length"
    assert configurable["rm-rf"] is None


def test_explain_known_rule_prints_detail() -> None:
    result = runner.invoke(app, ["explain", "rm-rf"])
    assert result.exit_code == 0
    assert "SECURITY" in result.stdout
    assert "--ignore rm-rf" in result.stdout


def test_explain_configurable_rule_shows_threshold() -> None:
    result = runner.invoke(app, ["explain", "description-too-short"])
    assert result.exit_code == 0
    assert "min_description_length" in result.stdout


def test_explain_unknown_rule_exits_two() -> None:
    result = runner.invoke(app, ["explain", "not-a-real-rule"])
    assert result.exit_code == 2


def test_init_creates_a_skill_that_scores_100(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "pdf-form-filler", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert (tmp_path / "pdf-form-filler" / "SKILL.md").exists()
    assert (tmp_path / "pdf-form-filler" / "skillseal.yaml").exists()
    assert "Score: 100/100" in result.stdout

    check_result = runner.invoke(
        app, ["check", str(tmp_path / "pdf-form-filler"), "--fail-on", "error"]
    )
    assert check_result.exit_code == 0


def test_init_invalid_name_exits_two(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "Bad_Name", "--path", str(tmp_path)])
    assert result.exit_code == 2


def test_init_existing_directory_exits_two(tmp_path: Path) -> None:
    (tmp_path / "my-skill").mkdir()
    result = runner.invoke(app, ["init", "my-skill", "--path", str(tmp_path)])
    assert result.exit_code == 2


def test_check_github_format_emits_workflow_commands() -> None:
    result = runner.invoke(app, ["check", str(EXAMPLES / "bad-skill"), "--format", "github"])
    assert result.exit_code == 1
    assert "::error file=" in result.stdout
    assert "title=rm-rf" in result.stdout
    assert "line=" in result.stdout


def test_check_github_format_has_no_rich_markup() -> None:
    result = runner.invoke(app, ["check", str(EXAMPLES / "bad-skill"), "--format", "github"])
    assert "[bold]" not in result.stdout
    assert "\x1b[" not in result.stdout


def test_check_sarif_format_is_valid_and_complete() -> None:
    result = runner.invoke(app, ["check", str(EXAMPLES / "bad-skill"), "--format", "sarif"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["version"] == "2.1.0"
    run = payload["runs"][0]
    assert run["tool"]["driver"]["name"] == "SkillSeal"
    # every rule that actually fired must be in the rules catalog
    fired_ids = {r["ruleId"] for r in run["results"]}
    catalog_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert fired_ids <= catalog_ids
    # GitHub code scanning requires a startLine on every result's location,
    # even for rules with no specific line (see reporters/sarif.py)
    for r in run["results"]:
        assert r["locations"][0]["physicalLocation"]["region"]["startLine"] >= 1
