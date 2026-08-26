"""GitHub Actions workflow-command annotations for `skillseal check --format github`.

https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-an-error-message
"""

from __future__ import annotations

from pathlib import Path

from skillseal.models import Severity, SkillReport
from skillseal.reporters.terminal import display_path

_LEVEL = {Severity.INFO: "notice", Severity.WARNING: "warning", Severity.ERROR: "error"}


def _escape_property(value: str) -> str:
    return (
        value.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
        .replace(",", "%2C")
    )


def _escape_message(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def render_check_reports_github(reports: list[SkillReport], root: Path | None = None) -> None:
    for report in reports:
        file = display_path(report.skill.path, root)
        for f in report.findings:
            level = _LEVEL[f.severity]
            props = f"file={_escape_property(file)},title={_escape_property(f.id)}"
            if f.line:
                props += f",line={f.line}"
            message = f.message if not f.detail else f"{f.message} ({f.detail})"
            print(f"::{level} {props}::{_escape_message(message)}")
