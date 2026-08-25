"""SkillGuard CLI.

Exit codes (both commands):
  0 = clean / gate passed
  1 = gate failed (--fail-on / --threshold not met)
  2 = usage or config error (bad path, no SKILL.md found, malformed skillguard.yaml)
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from skillguard.linter import lint_path
from skillguard.models import Severity
from skillguard.reporters.json_reporter import check_reports_to_json, routing_summaries_to_json
from skillguard.reporters.terminal import render_check_reports, render_routing_summaries
from skillguard.routing.evaluator import (
    HeuristicRoutingEvaluator,
    LLMRoutingEvaluator,
    OpenAICompatibleProvider,
    RoutingEvaluator,
)
from skillguard.routing.runner import RoutingConfigError, run_routing_tests_for_path

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()
err_console = Console(stderr=True)


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


@app.command()
def check(
    path: PathArg,
    format: Annotated[OutputFormat, typer.Option(help="Output format.")] = OutputFormat.TERMINAL,
    fail_on: Annotated[
        FailOn, typer.Option(help="Minimum severity that fails the gate.")
    ] = FailOn.ERROR,
) -> None:
    """Lint SKILL.md files: specification, quality, security, and portability."""
    if not path.exists():
        err_console.print(f"[red]Error:[/red] path not found: {path}")
        raise typer.Exit(code=2)

    reports = lint_path(path)
    if not reports:
        err_console.print(f"[red]Error:[/red] no SKILL.md files found under: {path}")
        raise typer.Exit(code=2)

    if format is OutputFormat.JSON:
        print(json.dumps(check_reports_to_json(reports), indent=2))
    else:
        render_check_reports(reports, console)

    gate_severities = _FAIL_ON_SEVERITIES[fail_on]
    gate_failed = any(f.severity in gate_severities for r in reports for f in r.findings)
    raise typer.Exit(code=1 if gate_failed else 0)


@app.command(name="test")
def test_routing(
    path: PathArg,
    threshold: Annotated[float, typer.Option(help="Minimum routing accuracy to pass.")] = 0.9,
    format: Annotated[OutputFormat, typer.Option(help="Output format.")] = OutputFormat.TERMINAL,
    provider: Annotated[
        Provider, typer.Option(help="Routing evaluator to use.")
    ] = Provider.HEURISTIC,
) -> None:
    """Run routing tests (skillguard.yaml) for each skill: does it trigger when it should?"""
    if not path.exists():
        err_console.print(f"[red]Error:[/red] path not found: {path}")
        raise typer.Exit(code=2)

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
        summaries = run_routing_tests_for_path(path, evaluator, threshold)
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

    gate_failed = any(not summary.passed for _, summary in summaries)
    raise typer.Exit(code=1 if gate_failed else 0)


if __name__ == "__main__":
    app()
