"""skillseal.toml: optional overrides for a curated set of heuristic thresholds.

Deliberately excludes the numbers that come directly from the agentskills.io
spec (name/description/compatibility max length) — overriding those would
mean the tool no longer validates spec compliance, just a private opinion.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path

CONFIG_FILENAME = "skillseal.toml"


class ConfigError(Exception):
    """Raised for a malformed skillseal.toml. Callers should treat this as a usage error."""


@dataclass(frozen=True)
class Config:
    min_description_length: int = 10
    token_warn_threshold: int = 5000
    max_lines: int = 500
    long_section_word_threshold: int = 800
    max_top_level_sections: int = 8
    conflict_threshold: float = 0.5
    containment_threshold: float = 0.8
    routing_threshold: float = 0.9


DEFAULT_CONFIG = Config()
_FIELD_NAMES = {f.name for f in fields(Config)}


def find_config_file(start: Path) -> Path | None:
    """Search `start` (or its parent, if a file) and its ancestors for skillseal.toml."""
    current = (start if start.is_dir() else start.parent).resolve()
    for candidate in (current, *current.parents):
        config_path = candidate / CONFIG_FILENAME
        if config_path.exists():
            return config_path
    return None


def load_config(path: Path) -> Config:
    config_file = find_config_file(path)
    if config_file is None:
        return DEFAULT_CONFIG

    try:
        raw = tomllib.loads(config_file.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Malformed TOML in {config_file}: {exc}") from exc

    thresholds = raw.get("thresholds", {})
    if not isinstance(thresholds, dict):
        raise ConfigError(f"{config_file}: 'thresholds' must be a table.")

    unknown = sorted(set(thresholds) - _FIELD_NAMES)
    if unknown:
        raise ConfigError(
            f"{config_file}: unknown threshold(s) {unknown}. Valid keys: {sorted(_FIELD_NAMES)}"
        )

    try:
        return replace(DEFAULT_CONFIG, **thresholds)
    except TypeError as exc:
        raise ConfigError(f"{config_file}: {exc}") from exc
