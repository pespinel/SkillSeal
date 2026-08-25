"""Core data models shared across parsing, rules, scoring, routing, and reporters."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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

    @property
    def dir_name(self) -> str:
        return self.dir.name


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
    confidence: float
    reason: str


class RoutingCaseResult(BaseModel):
    prompt: str
    expected: bool
    actual: bool
    confidence: float
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


class ConflictReport(BaseModel):
    """Result of scanning a directory of skills for cross-skill conflicts."""

    threshold: float
    skills_scanned: int
    duplicate_names: list[DuplicateNameConflict] = Field(default_factory=list)
    routing_overlaps: list[RoutingOverlapConflict] = Field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return bool(self.duplicate_names or self.routing_overlaps)


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
