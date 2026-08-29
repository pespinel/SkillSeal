"""SkillSeal CLI.

Exit codes (all commands):
  0 = clean / gate passed
  1 = gate failed (--fail-on / --min-score / --threshold / --require-tests not met,
      a conflict was found, diff regressed, or `fix` (dry-run) found something to fix)
  2 = usage or config error (bad path, no SKILL.md found, malformed skillseal.yaml/toml)
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from skillseal import __version__
from skillseal.config import Config, ConfigError, load_config
from skillseal.conflicts import find_conflicts
from skillseal.diff import DiffTargetError, diff_skills
from skillseal.fix import apply_fixes, plan_fixes
from skillseal.linter import lint_path, lint_skill
from skillseal.models import Severity
from skillseal.parser import parse_skill
from skillseal.reporters.github import render_check_reports_github
from skillseal.reporters.json_reporter import (
    check_reports_to_json,
    conflict_report_to_json,
    routing_summaries_to_json,
    rules_to_json,
    skill_diff_to_json,
)
from skillseal.reporters.sarif import check_reports_to_sarif
from skillseal.reporters.terminal import (
    render_check_reports,
    render_conflict_report,
    render_routing_summaries,
    render_rule_explain,
    render_rules,
    render_skill_diff,
)
from skillseal.routing.evaluator import (
    HeuristicRoutingEvaluator,
    LLMRoutingEvaluator,
    OpenAICompatibleProvider,
    RoutingEvaluator,
)
from skillseal.routing.runner import RoutingConfigError, run_routing_tests_for_path
from skillseal.rules.base import build_registry
from skillseal.scaffold import ScaffoldError, scaffold_skill

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()
err_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"skillseal {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """SkillSeal: lint, score, and routing-test Agent Skills (SKILL.md)."""


class OutputFormat(StrEnum):
    TERMINAL = "terminal"
    JSON = "json"


class CheckFormat(StrEnum):
    TERMINAL = "terminal"
    JSON = "json"
    GITHUB = "github"
    SARIF = "sarif"


class FailOn(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class Provider(StrEnum):
    HEURISTIC = "heuristic"
    LLM = "llm"


_FAIL_ON_SEVERITIES = {
    FailOn.WARNING: {Severity.WARNING, Severity.ERROR},
    FailOn.ERROR: {Severity.ERROR},
}

PathArg = Annotated[Path, typer.Argument(help="Path to a SKILL.md file or a directory of skills.")]


def _load_config_or_exit(path: Path) -> Config:
    try:
        return load_config(path)
    except ConfigError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command()
def check(
    path: PathArg,
    format: Annotated[
        CheckFormat,
        typer.Option(
            help="Output format. 'github' emits workflow-command annotations, "
            "'sarif' for GitHub code scanning."
        ),
    ] = CheckFormat.TERMINAL,
    fail_on: Annotated[
        FailOn, typer.Option(help="Minimum severity that fails the gate.")
    ] = FailOn.ERROR,
    min_score: Annotated[
        int | None,
        typer.Option("--min-score", help="Fail the gate if any skill's score is below this."),
    ] = None,
    ignore: Annotated[
        list[str],
        typer.Option(
            "--ignore",
            help="Suppress findings whose id starts with PREFIX. Repeatable.",
        ),
    ] = [],  # noqa: B006 - typer reads this as the option's default, not a mutated shared list
) -> None:
    """Lint SKILL.md files: specification, quality, security, and portability."""
    if not path.exists():
        err_console.print(f"[red]Error:[/red] path not found: {path}")
        raise typer.Exit(code=2)

    config = _load_config_or_exit(path)
    reports = lint_path(path, config, ignore_prefixes=ignore)
    if not reports:
        err_console.print(f"[red]Error:[/red] no SKILL.md files found under: {path}")
        raise typer.Exit(code=2)

    if format is CheckFormat.JSON:
        print(json.dumps(check_reports_to_json(reports), indent=2))
    elif format is CheckFormat.GITHUB:
        render_check_reports_github(reports)
    elif format is CheckFormat.SARIF:
        print(json.dumps(check_reports_to_sarif(reports), indent=2))
    else:
        render_check_reports(reports, console)

    gate_severities = _FAIL_ON_SEVERITIES[fail_on]
    gate_failed = any(f.severity in gate_severities for r in reports for f in r.findings)
    gate_failed = gate_failed or (
        min_score is not None and any(r.score < min_score for r in reports)
    )
    raise typer.Exit(code=1 if gate_failed else 0)


@app.command(name="test")
def test_routing(
    path: PathArg,
    threshold: Annotated[
        float | None,
        typer.Option(help="Minimum routing accuracy to pass. Defaults to skillseal.toml, or 0.9."),
    ] = None,
    format: Annotated[OutputFormat, typer.Option(help="Output format.")] = OutputFormat.TERMINAL,
    provider: Annotated[
        Provider, typer.Option(help="Routing evaluator to use.")
    ] = Provider.HEURISTIC,
    require_tests: Annotated[
        bool,
        typer.Option(
            "--require-tests",
            help="Fail the gate if any discovered skill has no skillseal.yaml.",
        ),
    ] = False,
) -> None:
    """Run routing tests (skillseal.yaml) for each skill: does it trigger when it should?"""
    if not path.exists():
        err_console.print(f"[red]Error:[/red] path not found: {path}")
        raise typer.Exit(code=2)

    config = _load_config_or_exit(path)
    resolved_threshold = threshold if threshold is not None else config.routing_threshold

    evaluator: RoutingEvaluator
    if provider is Provider.LLM:
        try:
            evaluator = LLMRoutingEvaluator(provider=OpenAICompatibleProvider())
        except RuntimeError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=2) from exc
    else:
        evaluator = HeuristicRoutingEvaluator(threshold=config.routing_trigger_threshold)

    try:
        summaries = run_routing_tests_for_path(path, evaluator, resolved_threshold)
    except RoutingConfigError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if not summaries:
        err_console.print(f"[red]Error:[/red] no SKILL.md files found under: {path}")
        raise typer.Exit(code=2)

    if format is OutputFormat.JSON:
        print(json.dumps(routing_summaries_to_json(summaries), indent=2))
    else:
        render_routing_summaries(summaries, console)

    untested = sum(1 for _, summary in summaries if summary.skipped)
    gate_failed = any(not summary.passed for _, summary in summaries)
    gate_failed = gate_failed or (require_tests and untested > 0)
    raise typer.Exit(code=1 if gate_failed else 0)


@app.command()
def conflicts(
    path: PathArg,
    threshold: Annotated[
        float | None,
        typer.Option(
            help="Minimum vocabulary similarity (Jaccard) to flag. "
            "Defaults to skillseal.toml, or 0.5."
        ),
    ] = None,
    against: Annotated[
        Path | None,
        typer.Option(
            help="Check skills in <path> against this broader corpus instead of "
            "all-pairs within <path> (e.g. a new skill against the whole skills repo)."
        ),
    ] = None,
    containment_threshold: Annotated[
        float | None,
        typer.Option(
            help="Minimum overlap/containment coefficient to flag as a vague "
            "superset/subset, for pairs below --threshold. Defaults to skillseal.toml, or 0.8."
        ),
    ] = None,
    format: Annotated[OutputFormat, typer.Option(help="Output format.")] = OutputFormat.TERMINAL,
) -> None:
    """Find cross-skill conflicts: duplicate names and likely routing overlap."""
    if not path.exists():
        err_console.print(f"[red]Error:[/red] path not found: {path}")
        raise typer.Exit(code=2)
    if against is not None and not against.exists():
        err_console.print(f"[red]Error:[/red] --against path not found: {against}")
        raise typer.Exit(code=2)

    config = _load_config_or_exit(path)
    resolved_threshold = threshold if threshold is not None else config.conflict_threshold
    resolved_containment_threshold = (
        containment_threshold if containment_threshold is not None else config.containment_threshold
    )

    report = find_conflicts(path, resolved_threshold, against, resolved_containment_threshold)
    if report.skills_scanned == 0:
        err_console.print(f"[red]Error:[/red] no SKILL.md files found under: {path}")
        raise typer.Exit(code=2)

    if format is OutputFormat.JSON:
        print(json.dumps(conflict_report_to_json(report), indent=2))
    else:
        render_conflict_report(report, console)

    raise typer.Exit(code=1 if report.has_conflicts else 0)


@app.command(name="diff")
def diff_command(
    old: Annotated[Path, typer.Argument(help="Old version: a SKILL.md file or skill directory.")],
    new: Annotated[Path, typer.Argument(help="New version: a SKILL.md file or skill directory.")],
    format: Annotated[OutputFormat, typer.Option(help="Output format.")] = OutputFormat.TERMINAL,
    fail_on_new_findings: Annotated[
        bool,
        typer.Option(
            "--fail-on-new-findings",
            help="Fail if any new finding appeared, even when the net score didn't regress.",
        ),
    ] = False,
) -> None:
    """Compare two versions of a skill: score and finding deltas."""
    for label, path in (("old", old), ("new", new)):
        if not path.exists():
            err_console.print(f"[red]Error:[/red] {label} path not found: {path}")
            raise typer.Exit(code=2)

    config = _load_config_or_exit(new)
    try:
        diff = diff_skills(old, new, config)
    except DiffTargetError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if format is OutputFormat.JSON:
        print(json.dumps(skill_diff_to_json(diff), indent=2))
    else:
        render_skill_diff(diff, console)

    gate_failed = diff.regressed or (fail_on_new_findings and bool(diff.added))
    raise typer.Exit(code=1 if gate_failed else 0)


@app.command()
def fix(
    path: PathArg,
    write: Annotated[
        bool, typer.Option("--write", help="Apply fixes. Without this, dry-run only.")
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Apply even to files with uncommitted git changes."),
    ] = False,
) -> None:
    """Fix trailing whitespace, a leading BOM, and hidden Unicode — nothing else.

    Deterministic and narrowly scoped by design: see the module docstring in
    fix.py for what's deliberately out of scope (frontmatter reordering,
    name-directory-mismatch, anything touching a description).
    """
    if not path.exists():
        err_console.print(f"[red]Error:[/red] path not found: {path}")
        raise typer.Exit(code=2)

    if write:
        result = apply_fixes(path, force=force)
        if not result.fixed and not result.skipped_dirty:
            console.print("Nothing to fix.")
            raise typer.Exit(code=0)
        for p in result.fixed:
            console.print(f"[green]fixed[/green] {p}")
        for p in result.skipped_dirty:
            console.print(f"[yellow]skipped[/yellow] {p} (uncommitted changes, use --force)")
        raise typer.Exit(code=0)

    plan = plan_fixes(path)
    if not plan:
        err_console.print(f"[red]Error:[/red] no SKILL.md files found under: {path}")
        raise typer.Exit(code=2)
    changed = [f for f in plan if f.changed]
    if not changed:
        console.print("Nothing to fix.")
        raise typer.Exit(code=0)
    for f in changed:
        parts = []
        if f.trailing_whitespace_lines:
            parts.append(f"trailing-whitespace: {f.trailing_whitespace_lines} line(s)")
        if f.had_bom:
            parts.append("bom: present")
        if f.hidden_unicode_chars:
            parts.append(f"hidden-unicode: {f.hidden_unicode_chars} char(s)")
        console.print(f"{f.path}\n  " + "\n  ".join(parts))
    console.print(f"\n{len(changed)} file(s) would be fixed. Run with --write to apply.")
    raise typer.Exit(code=1)


@app.command()
def rules(
    format: Annotated[OutputFormat, typer.Option(help="Output format.")] = OutputFormat.TERMINAL,
) -> None:
    """List all lint rules: id, category, severity, description, and configurability."""
    registry = build_registry()
    if format is OutputFormat.JSON:
        print(json.dumps(rules_to_json(registry), indent=2))
    else:
        render_rules(registry, console)


@app.command()
def explain(
    rule_id: Annotated[str, typer.Argument(help="Rule id, e.g. rm-rf or description-too-short.")],
) -> None:
    """Show what a rule checks, its category/severity, and how to suppress it."""
    rule = next((r for r in build_registry() if r.id == rule_id), None)
    if rule is None:
        err_console.print(f"[red]Error:[/red] unknown rule id: {rule_id}")
        raise typer.Exit(code=2)
    render_rule_explain(rule, console)


@app.command()
def init(
    name: Annotated[str, typer.Argument(help="Skill name, kebab-case, e.g. pdf-form-filler.")],
    path: Annotated[Path, typer.Option(help="Directory to create the skill in.")] = Path("."),
) -> None:
    """Scaffold a new skill: a SKILL.md that scores 100/100, plus a skillseal.yaml starter."""
    dest_dir = path / name
    try:
        skill_md, skillseal_yaml = scaffold_skill(dest_dir, name)
    except ScaffoldError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    report = lint_skill(parse_skill(skill_md))
    console.print(f"[green]Created[/green] {skill_md}")
    console.print(f"[green]Created[/green] {skillseal_yaml}")
    console.print(f"\nScore: {report.score}/100")
    console.print("\nFill in the [dim][bracketed][/dim] placeholders, then run:")
    console.print(f"  skillseal check {dest_dir}")
    console.print(f"  skillseal test {dest_dir}")


if __name__ == "__main__":
    app()
