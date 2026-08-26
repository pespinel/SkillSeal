from pathlib import Path

import pytest

from skillseal.linter import lint_skill
from skillseal.parser import parse_skill
from skillseal.scaffold import ScaffoldError, scaffold_skill, valid_skill_name


def test_scaffold_skill_creates_both_files(tmp_path: Path) -> None:
    dest = tmp_path / "pdf-form-filler"
    skill_md, skillseal_yaml = scaffold_skill(dest, "pdf-form-filler")

    assert skill_md == dest / "SKILL.md"
    assert skillseal_yaml == dest / "skillseal.yaml"
    assert skill_md.exists()
    assert skillseal_yaml.exists()


def test_scaffolded_skill_scores_100(tmp_path: Path) -> None:
    dest = tmp_path / "pdf-form-filler"
    skill_md, _ = scaffold_skill(dest, "pdf-form-filler")

    report = lint_skill(parse_skill(skill_md))

    assert report.score == 100
    assert all(v == 100 for v in report.category_scores.values())


def test_scaffolded_skill_is_detected_as_template(tmp_path: Path) -> None:
    dest = tmp_path / "pdf-form-filler"
    skill_md, _ = scaffold_skill(dest, "pdf-form-filler")

    report = lint_skill(parse_skill(skill_md))

    assert {f.id for f in report.findings} == {"detected-as-template"}


def test_scaffold_rejects_invalid_name(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldError):
        scaffold_skill(tmp_path / "Bad_Name", "Bad_Name")


def test_scaffold_rejects_existing_directory(tmp_path: Path) -> None:
    dest = tmp_path / "existing"
    dest.mkdir()
    with pytest.raises(ScaffoldError):
        scaffold_skill(dest, "existing")


def test_valid_skill_name() -> None:
    assert valid_skill_name("pdf-form-filler")
    assert not valid_skill_name("Bad_Name")
    assert not valid_skill_name("has spaces")
