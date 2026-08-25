from pathlib import Path

import pytest

from skillguard.routing.runner import RoutingConfigError, load_routing_config


def test_load_valid_config(tmp_path: Path) -> None:
    (tmp_path / "skillguard.yaml").write_text(
        "routing:\n  should_trigger:\n    - hello\n  should_not_trigger:\n    - goodbye\n"
    )
    config = load_routing_config(tmp_path)
    assert config is not None
    assert config.should_trigger == ["hello"]
    assert config.should_not_trigger == ["goodbye"]


def test_missing_config_returns_none(tmp_path: Path) -> None:
    assert load_routing_config(tmp_path) is None


def test_empty_case_lists(tmp_path: Path) -> None:
    (tmp_path / "skillguard.yaml").write_text("routing:\n  should_trigger: []\n")
    config = load_routing_config(tmp_path)
    assert config is not None
    assert config.should_trigger == []
    assert config.should_not_trigger == []


def test_malformed_yaml_raises(tmp_path: Path) -> None:
    (tmp_path / "skillguard.yaml").write_text("routing:\n  should_trigger: [unclosed\n")
    with pytest.raises(RoutingConfigError):
        load_routing_config(tmp_path)


def test_non_mapping_routing_raises(tmp_path: Path) -> None:
    (tmp_path / "skillguard.yaml").write_text("routing: not-a-mapping\n")
    with pytest.raises(RoutingConfigError):
        load_routing_config(tmp_path)
