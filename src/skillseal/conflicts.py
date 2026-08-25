"""Cross-skill conflict detection: duplicate names and routing-heuristic overlap.

Unlike `check`/`test`, this operates across all skills found under a path at
once rather than one skill at a time — some problems (two skills registering
the same name, or two skills so similar an agent can't reliably tell them
apart) only exist in relation to other skills.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

from skillseal.config import DEFAULT_CONFIG
from skillseal.models import ConflictReport, DuplicateNameConflict, RoutingOverlapConflict, Skill
from skillseal.parser import discover_skills, parse_skill
from skillseal.routing.evaluator import skill_terms


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _conflict_ignore_list(skill: Skill) -> list[str]:
    """Frontmatter `conflict_ignore:` — names/paths this skill shouldn't be compared against."""
    raw = skill.frontmatter.get("conflict_ignore")
    if not isinstance(raw, list):
        return []
    return [str(entry) for entry in raw]


def _ignores(skill: Skill, other: Skill) -> bool:
    """Exact match only — a substring match here would silently over-suppress

    real conflicts (e.g. `conflict_ignore: ["e"]` matching almost anything).
    """
    ignore_list = _conflict_ignore_list(skill)
    if not ignore_list:
        return False
    return any(entry in (other.name, other.dir_name) for entry in ignore_list)


def _find_duplicate_names(
    skills: list[Skill], require_one_in: set[Path] | None = None
) -> list[DuplicateNameConflict]:
    by_name: dict[str, list[Path]] = {}
    for skill in skills:
        if skill.frontmatter_error is not None or not skill.name:
            continue
        by_name.setdefault(skill.name, []).append(skill.path)
    return [
        DuplicateNameConflict(name=name, paths=sorted(paths))
        for name, paths in sorted(by_name.items())
        if len(paths) > 1
        and (require_one_in is None or any(p.resolve() in require_one_in for p in paths))
    ]


def _find_routing_overlaps(
    skills: list[Skill], threshold: float, require_one_in: set[Path] | None = None
) -> list[RoutingOverlapConflict]:
    overlaps = []
    for a, b in combinations(skills, 2):
        if require_one_in is not None and {a.path.resolve(), b.path.resolve()}.isdisjoint(
            require_one_in
        ):
            continue
        if a.frontmatter_error is not None or b.frontmatter_error is not None:
            continue
        if _ignores(a, b) or _ignores(b, a):
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


def find_conflicts(
    path: Path, threshold: float | None = None, against: Path | None = None
) -> ConflictReport:
    """Find conflicts among skills under `path`.

    With `against`, only pairs involving at least one skill from `path` are
    considered (checking new/changed skills against a broader corpus, rather
    than re-auditing the whole corpus against itself every time).
    """
    if threshold is None:
        threshold = DEFAULT_CONFIG.conflict_threshold

    target_skills = [parse_skill(p) for p in discover_skills(path)]
    target_paths = {s.path.resolve() for s in target_skills}

    if against is None:
        all_skills = target_skills
        require_one_in = None
    else:
        corpus_skills = [parse_skill(p) for p in discover_skills(against)]
        extra = [s for s in corpus_skills if s.path.resolve() not in target_paths]
        all_skills = target_skills + extra
        require_one_in = target_paths

    return ConflictReport(
        threshold=threshold,
        skills_scanned=len(target_skills),
        duplicate_names=_find_duplicate_names(all_skills, require_one_in),
        routing_overlaps=_find_routing_overlaps(all_skills, threshold, require_one_in),
    )
