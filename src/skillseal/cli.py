"""SkillSeal CLI.

Exit codes (all commands):
  0 = clean / gate passed
  1 = gate failed (--fail-on / --min-score / --threshold / --require-tests not met,
      a conflict was found, or diff regressed)
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
from skillseal.linter import lint_path
from skillseal.models import Severity
from skillseal.reporters.json_reporter import (
    check_reports_to_json,
    conflict_report_to_json,
    routing_summaries_to_json,
    skill_diff_to_json,
)
from skillseal.reporters.terminal import (
    render_check_reports,
    render_conflict_report,
    render_routing_summaries,
    render_skill_diff,
)
from skillseal.routing.evaluator import (
    HeuristicRoutingEvaluator,
    LLMRoutingEvaluator,
    OpenAICompatibleProvider,
    RoutingEvaluator,
)
from skillseal.routing.runner import RoutingConfigError, run_routing_tests_for_path

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
    format: Annotated[OutputFormat, typer.Option(help="Output format.")] = OutputFormat.TERMINAL,
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

    if format is OutputFormat.JSON:
        print(json.dumps(check_reports_to_json(reports), indent=2))
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
        evaluator = HeuristicRoutingEvaluator()

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

    report = find_conflicts(path, resolved_threshold, against)
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

    raise typer.Exit(code=1 if diff.regressed else 0)


if __name__ == "__main__":
    app()
