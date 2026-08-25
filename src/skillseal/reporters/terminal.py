"""Rich-based terminal output for `skillseal check`, `test`, `conflicts`, and `diff`."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from skillseal.models import (
    Category,
    ConflictReport,
    RoutingSummary,
    Severity,
    Skill,
    SkillDiff,
    SkillReport,
)
from skillseal.scoring import category_status

_STATUS_COLOR = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}
_SEVERITY_TAG = {Severity.INFO: "INFO", Severity.WARNING: "WARN", Severity.ERROR: "FAIL"}
_SEVERITY_COLOR = {Severity.INFO: "cyan", Severity.WARNING: "yellow", Severity.ERROR: "red"}


def display_path(path: Path, root: Path | None) -> str:
    try:
        return str(path.relative_to(root or Path.cwd()))
    except ValueError:
        return str(path)


def render_check_reports(
    reports: list[SkillReport], console: Console, root: Path | None = None
) -> None:
    for i, report in enumerate(reports):
        if i > 0:
            console.print()
        _render_skill_report(report, console, root)


def _render_skill_report(report: SkillReport, console: Console, root: Path | None) -> None:
    skill = report.skill
    console.print(f"[bold]{display_path(skill.path, root)}[/bold]\n")

    for category in Category:
        status = category_status(report.findings_for(category))
        color = _STATUS_COLOR[status]
        console.print(f"{category.value.capitalize():<15}[{color}]{status}[/{color}]")

    if report.findings:
        console.print("\n[bold]Issues[/bold]\n")
        for f in report.findings:
            tag = _SEVERITY_TAG[f.severity]
            color = _SEVERITY_COLOR[f.severity]
            location = f"  (line {f.line})" if f.line else ""
            console.print(f"[{color}]{tag:<5}[/{color}] {f.id}{location}")
            console.print(f"      {f.message}")
            if f.detail:
                console.print(f"      [dim]{f.detail}[/dim]")
            console.print()

    console.print(f"[bold]SkillSeal Score: {report.score}/100[/bold]\n")
    for category in Category:
        console.print(f"{category.value.capitalize():<15}{report.category_scores[category]:>3}")


def render_routing_summaries(
    summaries: list[tuple[Skill, RoutingSummary]], console: Console
) -> None:
    tested = sum(1 for _, summary in summaries if not summary.skipped)
    console.print(f"{len(summaries)} skill(s), {tested} with routing tests\n")

    for i, (skill, summary) in enumerate(summaries):
        if i > 0:
            console.print()
        console.print(f"[bold]{skill.name or skill.dir_name}[/bold]")
        if summary.skipped:
            console.print(f"  [dim]Skipped: {summary.skip_reason}[/dim]")
            continue

        st = summary.should_trigger_results
        snt = summary.should_not_trigger_results
        st_passed = sum(1 for r in st if r.passed)
        snt_passed = sum(1 for r in snt if r.passed)
        console.print()
        console.print(f"Should trigger       {st_passed}/{len(st)}")
        console.print(f"Should NOT trigger   {snt_passed}/{len(snt)}")
        console.print()
        acc_color = "green" if summary.passed else "red"
        console.print(f"Accuracy             [{acc_color}]{summary.accuracy:.1%}[/{acc_color}]")

        if summary.failures:
            console.print("\n[bold]Failures:[/bold]\n")
            for r in summary.failures:
                expected = "TRIGGER" if r.expected else "NOT TRIGGER"
                actual = "TRIGGER" if r.actual else "NOT TRIGGER"
                console.print(f'[red]✗[/red] "{r.prompt}"')
                console.print(f"  Expected: {expected}")
                console.print(f"  Actual: {actual}")
                console.print("  Likely reason:")
                console.print(f"  {r.reason}\n")


def render_conflict_report(
    report: ConflictReport, console: Console, root: Path | None = None
) -> None:
    console.print(f"Scanned {report.skills_scanned} skill(s)\n")

    if not report.has_conflicts:
        console.print("[green]No conflicts found.[/green]")
        return

    if report.duplicate_names:
        console.print("[bold]Duplicate names[/bold]\n")
        for dup in report.duplicate_names:
            console.print(f'[red]✗[/red] "{dup.name}" used by {len(dup.paths)} skills:')
            for p in dup.paths:
                console.print(f"  - {display_path(p, root)}")
            console.print()

    if report.routing_overlaps:
        console.print("[bold]Routing overlap[/bold]\n")
        for ov in report.routing_overlaps:
            console.print(f'[red]✗[/red] "{ov.skill_a}" and "{ov.skill_b}"')
            console.print(f"  {display_path(ov.path_a, root)}")
            console.print(f"  {display_path(ov.path_b, root)}")
            console.print(f"  Similarity: {ov.similarity:.0%} (threshold: {report.threshold:.0%})")
            console.print(f"  Shared terms: {', '.join(ov.shared_terms[:8])}")
            console.print()


def render_skill_diff(diff: SkillDiff, console: Console) -> None:
    delta = diff.score_delta
    delta_str = f"+{delta}" if delta > 0 else str(delta)
    delta_color = "red" if diff.regressed else ("green" if delta > 0 else "dim")
    console.print(
        f"Score: {diff.old.score} -> {diff.new.score}  "
        f"[{delta_color}]({delta_str})[/{delta_color}]\n"
    )

    for category in Category:
        old_s = diff.old.category_scores[category]
        new_s = diff.new.category_scores[category]
        marker = "" if old_s == new_s else f"  ({old_s} -> {new_s})"
        console.print(f"{category.value.capitalize():<15}{new_s:>3}{marker}")

    if diff.added:
        console.print("\n[bold red]New findings[/bold red]\n")
        for f in diff.added:
            tag = _SEVERITY_TAG[f.severity]
            color = _SEVERITY_COLOR[f.severity]
            location = f" (line {f.line})" if f.line else ""
            console.print(f"[{color}]{tag:<5}[/{color}] {f.id}{location}  {f.message}")

    if diff.removed:
        console.print("\n[bold green]Resolved findings[/bold green]\n")
        for f in diff.removed:
            console.print(f"  {f.id}  {f.message}")

    if not diff.added and not diff.removed:
        console.print("\n[dim]No finding changes.[/dim]")
