"""Cross-skill conflict detection: duplicate names and routing-heuristic overlap.

Unlike `check`/`test`, this operates across all skills found under a path at
once rather than one skill at a time — some problems (two skills registering
the same name, or two skills so similar an agent can't reliably tell them
apart) only exist in relation to other skills.
"""

from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path

from skillseal.config import DEFAULT_CONFIG
from skillseal.models import (
    ConflictReport,
    ContainmentConflict,
    DuplicateNameConflict,
    NearDuplicateNameConflict,
    RoutingOverlapConflict,
    Skill,
)
from skillseal.parser import discover_skills, parse_skill
from skillseal.routing.evaluator import skill_terms

_NAME_SEPARATORS_RE = re.compile(r"[-_\s]+")


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _containment(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _normalize_name(name: str) -> str:
    return _NAME_SEPARATORS_RE.sub("", name.lower())


def _edit_distance_le_1(a: str, b: str) -> bool:
    """True if `a` -> `b` needs at most one character insert/delete/substitute."""
    len_a, len_b = len(a), len(b)
    if abs(len_a - len_b) > 1:
        return False
    if len_a == len_b:
        mismatches = sum(1 for x, y in zip(a, b, strict=True) if x != y)
        return mismatches <= 1
    shorter, longer = (a, b) if len_a < len_b else (b, a)
    i = j = edits = 0
    while i < len(shorter) and j < len(longer):
        if shorter[i] == longer[j]:
            i += 1
            j += 1
        else:
            edits += 1
            j += 1
            if edits > 1:
                return False
    return True


def _is_near_duplicate_name(a: str, b: str) -> bool:
    """Same name after normalizing case/separators, or one edit apart — but not equal."""
    if a == b:
        return False
    return _normalize_name(a) == _normalize_name(b) or _edit_distance_le_1(a, b)


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


def _find_overlaps(
    skills: list[Skill],
    threshold: float,
    containment_threshold: float,
    require_one_in: set[Path] | None = None,
) -> tuple[list[RoutingOverlapConflict], list[ContainmentConflict]]:
    """One pass over all pairs, since both signals need the same skill_terms().

    A pair that clears the Jaccard threshold is reported as a routing overlap
    only — containment is naturally high whenever Jaccard already is, so
    reporting both would just be noise around the same underlying pair.
    """
    routing_overlaps: list[RoutingOverlapConflict] = []
    containment_overlaps: list[ContainmentConflict] = []
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
        jaccard = _jaccard(terms_a, terms_b)
        shared = sorted(terms_a & terms_b)
        if jaccard >= threshold:
            routing_overlaps.append(
                RoutingOverlapConflict(
                    skill_a=a.name or a.dir_name,
                    skill_b=b.name or b.dir_name,
                    path_a=a.path,
                    path_b=b.path,
                    similarity=round(jaccard, 3),
                    shared_terms=shared,
                )
            )
            continue
        containment = _containment(terms_a, terms_b)
        if containment >= containment_threshold:
            containment_overlaps.append(
                ContainmentConflict(
                    skill_a=a.name or a.dir_name,
                    skill_b=b.name or b.dir_name,
                    path_a=a.path,
                    path_b=b.path,
                    containment=round(containment, 3),
                    jaccard=round(jaccard, 3),
                    shared_terms=shared,
                )
            )
    routing_overlaps.sort(key=lambda o: o.similarity, reverse=True)
    containment_overlaps.sort(key=lambda o: o.containment, reverse=True)
    return routing_overlaps, containment_overlaps


def _find_near_duplicate_names(
    skills: list[Skill], require_one_in: set[Path] | None = None
) -> list[NearDuplicateNameConflict]:
    named = [s for s in skills if s.frontmatter_error is None and s.name]
    conflicts = []
    for a, b in combinations(named, 2):
        if require_one_in is not None and {a.path.resolve(), b.path.resolve()}.isdisjoint(
            require_one_in
        ):
            continue
        if not _is_near_duplicate_name(a.name, b.name):
            continue
        conflicts.append(
            NearDuplicateNameConflict(name_a=a.name, name_b=b.name, path_a=a.path, path_b=b.path)
        )
    conflicts.sort(key=lambda c: (c.name_a, c.name_b))
    return conflicts


def find_conflicts(
    path: Path,
    threshold: float | None = None,
    against: Path | None = None,
    containment_threshold: float | None = None,
) -> ConflictReport:
    """Find conflicts among skills under `path`.

    With `against`, only pairs involving at least one skill from `path` are
    considered (checking new/changed skills against a broader corpus, rather
    than re-auditing the whole corpus against itself every time).
    """
    if threshold is None:
        threshold = DEFAULT_CONFIG.conflict_threshold
    if containment_threshold is None:
        containment_threshold = DEFAULT_CONFIG.containment_threshold

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

    routing_overlaps, containment_overlaps = _find_overlaps(
        all_skills, threshold, containment_threshold, require_one_in
    )
    return ConflictReport(
        threshold=threshold,
        skills_scanned=len(target_skills),
        duplicate_names=_find_duplicate_names(all_skills, require_one_in),
        near_duplicate_names=_find_near_duplicate_names(all_skills, require_one_in),
        routing_overlaps=routing_overlaps,
        containment_overlaps=containment_overlaps,
    )
