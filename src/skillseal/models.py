"""Core data models shared across parsing, rules, scoring, routing, and reporters."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_TEMPLATE_DIR_RE = re.compile(r"^templates?$", re.IGNORECASE)
_TEMPLATE_PLACEHOLDER_RE = re.compile(
    r"\bTODO\b|\[[^\]]*\b(describe|placeholder)\b[^\]]*\]", re.IGNORECASE
)


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Category(StrEnum):
    SPECIFICATION = "SPECIFICATION"
    QUALITY = "QUALITY"
    SECURITY = "SECURITY"
    PORTABILITY = "PORTABILITY"


class Finding(BaseModel):
    """A single issue raised by a rule against a skill."""

    model_config = ConfigDict(frozen=True)

    id: str
    category: Category
    severity: Severity
    message: str
    detail: str | None = None
    line: int | None = None


class Skill(BaseModel):
    """A parsed SKILL.md, ready for rule evaluation."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    description: str
    frontmatter: dict[str, Any]
    body: str
    raw_text: str
    path: Path
    dir: Path
    frontmatter_error: str | None = None
    # "missing-frontmatter" | "frontmatter-not-at-start" | "invalid-frontmatter" | None
    frontmatter_error_kind: str | None = None
    # raw YAML between the '---' fences, kept for key-line lookups (rules/base.py)
    frontmatter_text: str = ""
    # set only when frontmatter_error_kind == "invalid-frontmatter" and pyyaml gave a mark
    frontmatter_error_line: int | None = None

    @property
    def dir_name(self) -> str:
        return self.dir.name

    @property
    def is_template(self) -> bool:
        """Heuristic: explicit `template: true`, a placeholder-y description

        (literal "TODO" or a `[describe ...]`-style bracket marker), or a
        parent directory literally named template/templates.
        """
        if self.frontmatter.get("template") is True:
            return True
        if _TEMPLATE_PLACEHOLDER_RE.search(self.description):
            return True
        return any(_TEMPLATE_DIR_RE.match(part) for part in self.dir.parts)


class SkillReport(BaseModel):
    """Lint result for one skill: every finding plus computed scores."""

    skill: Skill
    findings: list[Finding] = Field(default_factory=list)
    category_scores: dict[Category, int] = Field(default_factory=dict)
    score: int = 0

    def findings_for(self, category: Category) -> list[Finding]:
        return [f for f in self.findings if f.category == category]


class RoutingConfig(BaseModel):
    """Parsed skillseal.yaml routing test cases."""

    version: int = 1
    should_trigger: list[str] = Field(default_factory=list)
    should_not_trigger: list[str] = Field(default_factory=list)


class RoutingResult(BaseModel):
    """Output of one RoutingEvaluator.evaluate() call, before scoring against expectation."""

    triggered: bool
    # None for evaluators with no calibrated confidence signal (e.g. an LLM
    # judge just returns yes/no) rather than a fabricated number.
    confidence: float | None
    reason: str


class RoutingCaseResult(BaseModel):
    prompt: str
    expected: bool
    actual: bool
    confidence: float | None
    reason: str

    @property
    def passed(self) -> bool:
        return self.expected == self.actual


class RoutingSummary(BaseModel):
    """Routing test outcome for one skill."""

    skill_name: str
    threshold: float
    results: list[RoutingCaseResult] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def should_trigger_results(self) -> list[RoutingCaseResult]:
        return [r for r in self.results if r.expected]

    @property
    def should_not_trigger_results(self) -> list[RoutingCaseResult]:
        return [r for r in self.results if not r.expected]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def accuracy(self) -> float:
        if not self.results:
            return 1.0
        return self.passed_count / self.total

    @property
    def passed(self) -> bool:
        if self.skipped:
            return True
        return self.accuracy >= self.threshold

    @property
    def failures(self) -> list[RoutingCaseResult]:
        return [r for r in self.results if not r.passed]


class DuplicateNameConflict(BaseModel):
    """Two or more skills in the same scan declare the same frontmatter `name`."""

    name: str
    paths: list[Path]


class RoutingOverlapConflict(BaseModel):
    """Two different skills whose vocabularies overlap enough to likely both

    trigger for the same prompts, based on Jaccard similarity of their
    HeuristicRoutingEvaluator term sets (see routing/evaluator.py:skill_terms).
    """

    skill_a: str
    skill_b: str
    path_a: Path
    path_b: Path
    similarity: float
    shared_terms: list[str]


class ContainmentConflict(BaseModel):
    """One skill's vocabulary is largely contained within another's even though

    Jaccard similarity is low (`|a∩b| / min(|a|,|b|)` is high) — a vague skill
    that's a near-subset/superset of a more specific one, which steals routing
    traffic without looking similar by union-based similarity.
    """

    skill_a: str
    skill_b: str
    path_a: Path
    path_b: Path
    containment: float
    jaccard: float
    shared_terms: list[str]


class NearDuplicateNameConflict(BaseModel):
    """Two skills whose frontmatter `name` values are near-identical (edit

    distance <= 1, or equal after normalizing case/separators) — not an exact
    collision, but confusing for both agents and humans.
    """

    name_a: str
    name_b: str
    path_a: Path
    path_b: Path


class ConflictReport(BaseModel):
    """Result of scanning a directory of skills for cross-skill conflicts."""

    threshold: float
    skills_scanned: int
    duplicate_names: list[DuplicateNameConflict] = Field(default_factory=list)
    near_duplicate_names: list[NearDuplicateNameConflict] = Field(default_factory=list)
    routing_overlaps: list[RoutingOverlapConflict] = Field(default_factory=list)
    containment_overlaps: list[ContainmentConflict] = Field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return bool(
            self.duplicate_names
            or self.near_duplicate_names
            or self.routing_overlaps
            or self.containment_overlaps
        )


class SkillDiff(BaseModel):
    """Score/finding delta between two versions of a skill (e.g. old path vs new path)."""

    old: SkillReport
    new: SkillReport
    added: list[Finding] = Field(default_factory=list)
    removed: list[Finding] = Field(default_factory=list)

    @property
    def score_delta(self) -> int:
        return self.new.score - self.old.score

    @property
    def regressed(self) -> bool:
        return self.score_delta < 0
