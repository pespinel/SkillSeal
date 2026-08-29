import subprocess
from pathlib import Path

from skillseal.fix import apply_fixes, plan_fixes


def _write_skill(root: Path, name: str, content: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


_CLEAN = "---\nname: helper\ndescription: Use this skill when doing the thing.\n---\nBody.\n"


def test_plan_fixes_reports_clean_skill_as_unchanged(tmp_path: Path) -> None:
    _write_skill(tmp_path, "helper", _CLEAN)
    plan = plan_fixes(tmp_path)
    assert len(plan) == 1
    assert plan[0].changed is False


def test_plan_fixes_detects_trailing_whitespace(tmp_path: Path) -> None:
    content = _CLEAN.replace("Body.\n", "Body.   \n")
    _write_skill(tmp_path, "helper", content)
    plan = plan_fixes(tmp_path)
    assert plan[0].trailing_whitespace_lines == 1
    assert plan[0].changed is True


def test_plan_fixes_detects_bom(tmp_path: Path) -> None:
    _write_skill(tmp_path, "helper", "﻿" + _CLEAN)
    plan = plan_fixes(tmp_path)
    assert plan[0].had_bom is True


def test_plan_fixes_detects_hidden_unicode(tmp_path: Path) -> None:
    content = _CLEAN.replace("Body.\n", "Bo​dy.\n")
    _write_skill(tmp_path, "helper", content)
    plan = plan_fixes(tmp_path)
    assert plan[0].hidden_unicode_chars == 1


def test_apply_fixes_writes_normalized_content(tmp_path: Path) -> None:
    content = "﻿" + _CLEAN.replace("Body.\n", "Bo​dy.   \n")
    skill_md = _write_skill(tmp_path, "helper", content)
    result = apply_fixes(tmp_path)
    assert result.fixed == [skill_md]
    assert result.skipped_dirty == []
    written = skill_md.read_text(encoding="utf-8")
    assert written == _CLEAN
    assert not written.startswith("﻿")


def test_apply_fixes_is_idempotent(tmp_path: Path) -> None:
    content = "﻿" + _CLEAN.replace("Body.\n", "Body.   \n")
    _write_skill(tmp_path, "helper", content)
    apply_fixes(tmp_path)
    second = apply_fixes(tmp_path)
    assert second.fixed == []


def test_apply_fixes_skips_dirty_file_without_force(tmp_path: Path) -> None:
    content = _CLEAN.replace("Body.\n", "Body.   \n")
    skill_md = _write_skill(tmp_path, "helper", content)
    _git("init", "-q", cwd=tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "x", cwd=tmp_path)
    skill_md.write_text(skill_md.read_text() + "uncommitted line\n")

    result = apply_fixes(tmp_path)

    assert result.fixed == []
    assert result.skipped_dirty == [skill_md]
    # untouched: the trailing-whitespace line is still there
    assert "Body.   \n" in skill_md.read_text(encoding="utf-8")


def test_apply_fixes_force_overrides_dirty_check(tmp_path: Path) -> None:
    content = _CLEAN.replace("Body.\n", "Body.   \n")
    skill_md = _write_skill(tmp_path, "helper", content)
    _git("init", "-q", cwd=tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "x", cwd=tmp_path)
    skill_md.write_text(skill_md.read_text() + "uncommitted line\n")

    result = apply_fixes(tmp_path, force=True)

    assert result.fixed == [skill_md]
    assert "Body.   \n" not in skill_md.read_text(encoding="utf-8")


def test_apply_fixes_outside_git_repo_proceeds(tmp_path: Path) -> None:
    # no git repo at all — nothing to protect, should apply normally
    content = _CLEAN.replace("Body.\n", "Body.   \n")
    skill_md = _write_skill(tmp_path, "helper", content)
    result = apply_fixes(tmp_path)
    assert result.fixed == [skill_md]
