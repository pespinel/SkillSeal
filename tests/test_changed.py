import subprocess
from pathlib import Path

import pytest

from skillseal.changed import GitDiffError, changed_files, filter_changed_skills
from skillseal.parser import discover_skills


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _write_skill(root: Path, name: str, description: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(f"---\nname: {name}\ndescription: {description}\n---\nBody.\n")
    return skill_md


def _init_two_skill_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "skills"
    alpha = _write_skill(root, "alpha", "Use this skill when doing alpha things.")
    _write_skill(root, "beta", "Use this skill when doing beta things.")
    _git("init", "-q", cwd=tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "x", cwd=tmp_path)
    _git("branch", "base", cwd=tmp_path)
    return root, alpha


def test_changed_files_returns_only_modified_paths(tmp_path: Path) -> None:
    root, alpha = _init_two_skill_repo(tmp_path)
    (root / "beta" / "SKILL.md").write_text((root / "beta" / "SKILL.md").read_text() + "Extra.\n")
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "y", cwd=tmp_path)

    diff = changed_files(root, "base", "HEAD")

    assert (root / "beta" / "SKILL.md").resolve() in diff
    assert alpha.resolve() not in diff


def test_filter_changed_skills_keeps_only_touched_skill_dirs(tmp_path: Path) -> None:
    root, alpha = _init_two_skill_repo(tmp_path)
    all_skills = discover_skills(root)
    changed = {(root / "beta" / "SKILL.md").resolve()}

    kept = filter_changed_skills(all_skills, changed)

    assert kept == [root / "beta" / "SKILL.md"]
    assert alpha not in kept


def test_filter_changed_skills_keeps_skill_when_a_sibling_file_changed(tmp_path: Path) -> None:
    root, _ = _init_two_skill_repo(tmp_path)
    (root / "beta" / "scripts").mkdir()
    changed = {(root / "beta" / "scripts" / "run.sh").resolve()}

    kept = filter_changed_skills(discover_skills(root), changed)

    assert kept == [root / "beta" / "SKILL.md"]


def test_changed_files_bad_ref_raises_git_diff_error(tmp_path: Path) -> None:
    root, _ = _init_two_skill_repo(tmp_path)
    with pytest.raises(GitDiffError):
        changed_files(root, "does-not-exist-ref")


def test_changed_files_outside_a_repo_raises_git_diff_error(tmp_path: Path) -> None:
    with pytest.raises(GitDiffError):
        changed_files(tmp_path, "main")
