from pathlib import Path

import pytest

from skillseal.config import DEFAULT_CONFIG, ConfigError, find_config_file, load_config


def test_no_config_file_returns_default(tmp_path: Path) -> None:
    assert load_config(tmp_path) is DEFAULT_CONFIG


def test_config_overrides_threshold(tmp_path: Path) -> None:
    (tmp_path / "skillseal.toml").write_text("[thresholds]\nmin_description_length = 42\n")
    config = load_config(tmp_path)
    assert config.min_description_length == 42
    # unset fields keep their default
    assert config.max_lines == DEFAULT_CONFIG.max_lines


def test_config_discovered_from_parent_directory(tmp_path: Path) -> None:
    (tmp_path / "skillseal.toml").write_text("[thresholds]\nmax_lines = 100\n")
    nested = tmp_path / "skills" / "my-skill"
    nested.mkdir(parents=True)

    config = load_config(nested)

    assert config.max_lines == 100


def test_find_config_file_from_a_file_path(tmp_path: Path) -> None:
    config_file = tmp_path / "skillseal.toml"
    config_file.write_text("[thresholds]\n")
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("---\nname: x\ndescription: y\n---\n")

    assert find_config_file(skill_md) == config_file


def test_malformed_toml_raises(tmp_path: Path) -> None:
    (tmp_path / "skillseal.toml").write_text("[thresholds\nbroken\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_unknown_threshold_key_raises(tmp_path: Path) -> None:
    (tmp_path / "skillseal.toml").write_text("[thresholds]\nnot_a_real_threshold = 1\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_non_table_thresholds_raises(tmp_path: Path) -> None:
    (tmp_path / "skillseal.toml").write_text("thresholds = 5\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path)
