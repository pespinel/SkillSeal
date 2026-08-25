"""SkillSeal: lint, score, and routing-test Agent Skills (SKILL.md)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("skillseal")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
