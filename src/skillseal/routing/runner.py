"""Loads skillseal.yaml and runs routing test cases against an evaluator."""

from __future__ import annotations

from pathlib import Path

import yaml

from skillseal.models import RoutingCaseResult, RoutingConfig, RoutingSummary, Skill
from skillseal.parser import discover_skills, parse_skill
from skillseal.routing.evaluator import RoutingEvaluator

CONFIG_FILENAME = "skillseal.yaml"


class RoutingConfigError(Exception):
    """Raised for a malformed skillseal.yaml. Callers should treat this as a usage error."""


def load_routing_config(skill_dir: Path) -> RoutingConfig | None:
    config_path = skill_dir / CONFIG_FILENAME
    if not config_path.exists():
        return None

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RoutingConfigError(f"Malformed YAML in {config_path}: {exc}") from exc

    raw = raw or {}
    if not isinstance(raw, dict):
        raise RoutingConfigError(f"{config_path} must be a YAML mapping.")

    routing = raw.get("routing", {}) or {}
    if not isinstance(routing, dict):
        raise RoutingConfigError(f"{config_path}: 'routing' must be a mapping.")

    return RoutingConfig(
        version=int(raw.get("version", 1)),
        should_trigger=list(routing.get("should_trigger", []) or []),
        should_not_trigger=list(routing.get("should_not_trigger", []) or []),
    )


def run_routing_tests(
    skill: Skill, config: RoutingConfig, evaluator: RoutingEvaluator, threshold: float
) -> RoutingSummary:
    cases: list[tuple[str, bool]] = [(p, True) for p in config.should_trigger]
    cases += [(p, False) for p in config.should_not_trigger]

    if not cases:
        return RoutingSummary(
            skill_name=skill.name,
            threshold=threshold,
            skipped=True,
            skip_reason="No routing test cases defined in skillseal.yaml.",
        )

    results = []
    for prompt, expected in cases:
        outcome = evaluator.evaluate(skill, prompt)
        results.append(
            RoutingCaseResult(
                prompt=prompt,
                expected=expected,
                actual=outcome.triggered,
                confidence=outcome.confidence,
                reason=outcome.reason,
            )
        )
    return RoutingSummary(skill_name=skill.name, threshold=threshold, results=results)


def run_routing_tests_for_path(
    path: Path, evaluator: RoutingEvaluator, threshold: float
) -> list[tuple[Skill, RoutingSummary]]:
    """Discover skills under `path` and run routing tests, skipping those with no config."""
    summaries = []
    for skill_path in discover_skills(path):
        skill = parse_skill(skill_path)
        config = load_routing_config(skill.dir)
        if config is None:
            summary = RoutingSummary(
                skill_name=skill.name or skill.dir_name,
                threshold=threshold,
                skipped=True,
                skip_reason=f"No {CONFIG_FILENAME} found next to SKILL.md.",
            )
        else:
            summary = run_routing_tests(skill, config, evaluator, threshold)
        summaries.append((skill, summary))
    return summaries
