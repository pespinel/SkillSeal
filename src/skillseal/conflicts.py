"""Cross-skill conflict detection: duplicate names and routing-heuristic overlap.

Unlike `check`/`test`, this operates across all skills found under a path at
once rather than one skill at a time — some problems (two skills registering
the same name, or two skills so similar an agent can't reliably tell them
apart) only exist in relation to other skills.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

from skillseal.models import ConflictReport, DuplicateNameConflict, RoutingOverlapConflict, Skill
from skillseal.parser import discover_skills, parse_skill
from skillseal.routing.evaluator import skill_terms

DEFAULT_THRESHOLD = 0.5


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _find_duplicate_names(skills: list[Skill]) -> list[DuplicateNameConflict]:
    by_name: dict[str, list[Path]] = {}
    for skill in skills:
        if skill.frontmatter_error is not None or not skill.name:
            continue
        by_name.setdefault(skill.name, []).append(skill.path)
    return [
        DuplicateNameConflict(name=name, paths=sorted(paths))
        for name, paths in sorted(by_name.items())
        if len(paths) > 1
    ]


def _find_routing_overlaps(skills: list[Skill], threshold: float) -> list[RoutingOverlapConflict]:
    overlaps = []
    for a, b in combinations(skills, 2):
        if a.frontmatter_error is not None or b.frontmatter_error is not None:
            continue
        terms_a, terms_b = skill_terms(a), skill_terms(b)
        similarity = _jaccard(terms_a, terms_b)
        if similarity < threshold:
            continue
        overlaps.append(
            RoutingOverlapConflict(
                skill_a=a.name or a.dir_name,
                skill_b=b.name or b.dir_name,
                path_a=a.path,
                path_b=b.path,
                similarity=round(similarity, 3),
                shared_terms=sorted(terms_a & terms_b),
            )
        )
    overlaps.sort(key=lambda o: o.similarity, reverse=True)
    return overlaps


def find_conflicts(path: Path, threshold: float = DEFAULT_THRESHOLD) -> ConflictReport:
    skills = [parse_skill(p) for p in discover_skills(path)]
    return ConflictReport(
        threshold=threshold,
        skills_scanned=len(skills),
        duplicate_names=_find_duplicate_names(skills),
        routing_overlaps=_find_routing_overlaps(skills, threshold),
    )
