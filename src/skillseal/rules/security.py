"""SECURITY rules: heuristic detection of potentially dangerous patterns.

None of these findings assert a confirmed vulnerability — they flag *potential*
risk for a human to review, since static regex matching over instructions
can't know real intent or execution context.
"""

from __future__ import annotations

import re
from pathlib import Path

from skillseal.config import Config
from skillseal.models import Category, Severity, Skill
from skillseal.rules.base import Draft, FuncRule, Rule, extract_code_spans, local_file_targets

_RM_RF_RE = re.compile(r"\brm\s+(-\w*[rR]\w*[fF]\w*|-\w*[fF]\w*[rR]\w*)\b")
_PIPE_SHELL_RE = re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(sh|bash|zsh)\b", re.IGNORECASE)
_EVAL_EXEC_RE = re.compile(r"\b(eval|exec)\s*\(")
_SUDO_RE = re.compile(r"\bsudo\b")
_CHMOD_777_RE = re.compile(r"\bchmod\s+(-R\s+)?0?777\b")
_SSH_KEY_RE = re.compile(r"~/\.ssh\b")
_ENV_ACCESS_RE = re.compile(
    r"\b(cat|read|load|source|export|open|parse)\b[^\n]{0,30}\.env\b", re.IGNORECASE
)
_SECRET_FILE_RE = re.compile(
    r"\b(cat|less|more|head|tail|type|open)\b[^\n]{0,30}"
    r"(id_rsa|id_ed25519|\.pem\b|\.p12\b|_?SECRET_?(ACCESS_)?KEY)",
    re.IGNORECASE,
)
_INTERP_SHELL_RE = re.compile(
    r"\b(rm|curl|wget|ssh|cat|mv|cp|eval|exec)\b[^\n]*(\$\{[^}\n]+\}|\{\{[^}\n]+\}\}|\{[a-zA-Z_][\w.]*\})"
)


def _aggregate(matches: list[str], message: str) -> list[Draft]:
    if not matches:
        return []
    sample = matches[0].strip()[:80]
    detail = f'{len(matches)} occurrence(s), e.g. "{sample}"'
    return [Draft(message=message, detail=detail)]


def _matches_in_code(skill: Skill, pattern: re.Pattern[str]) -> list[str]:
    return [m.group(0) for span in extract_code_spans(skill.body) for m in pattern.finditer(span)]


def _matches_in_body(skill: Skill, pattern: re.Pattern[str]) -> list[str]:
    return [m.group(0) for m in pattern.finditer(skill.body)]


# --- bundled files (scripts/, references/, assets/) -----------------------
#
# SKILL.md is the documentation; scripts/ is the payload an agent actually
# runs. The agentskills.io spec explicitly sanctions scripts/ for executable
# code, so it needs the same scanning SKILL.md's own code blocks get.
# ponytail: no full binary/archive introspection, just a text-file regex
# sweep with size/count caps — upgrade to per-pattern bundled-* rule ids if
# --ignore granularity for this ever matters.

_BUNDLED_DIRS = ("scripts", "references", "assets")
_MAX_BUNDLED_FILE_BYTES = 500_000
_MAX_BUNDLED_TOTAL_BYTES = 2_000_000
_MAX_BUNDLED_FILES = 200

_BUNDLED_ERROR_PATTERNS = {"rm-rf": _RM_RF_RE, "pipe-to-shell": _PIPE_SHELL_RE}
_BUNDLED_WARNING_PATTERNS = {
    "eval-exec": _EVAL_EXEC_RE,
    "sudo-usage": _SUDO_RE,
    "chmod-777": _CHMOD_777_RE,
    "secret-file-read": _SECRET_FILE_RE,
    "interpolated-shell-input": _INTERP_SHELL_RE,
}


def _iter_bundled_files(skill: Skill) -> list[Path]:
    files: list[Path] = []
    total_bytes = 0
    for sub in _BUNDLED_DIRS:
        base = skill.dir / sub
        if not base.is_dir():
            continue
        for candidate in sorted(base.rglob("*")):
            if len(files) >= _MAX_BUNDLED_FILES or total_bytes >= _MAX_BUNDLED_TOTAL_BYTES:
                break
            if not candidate.is_file():
                continue
            try:
                size = candidate.stat().st_size
            except OSError:
                continue
            if size == 0 or size > _MAX_BUNDLED_FILE_BYTES:
                continue
            files.append(candidate)
            total_bytes += size
    return files


def _read_bundled_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None  # binary; not ours to scan
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _scan_bundled(skill: Skill, patterns: dict[str, re.Pattern[str]]) -> list[str]:
    hits: list[str] = []
    for path in _iter_bundled_files(skill):
        text = _read_bundled_text(path)
        if text is None:
            continue
        rel = path.relative_to(skill.dir)
        for label, pattern in patterns.items():
            for m in pattern.finditer(text):
                hits.append(f"{rel} [{label}]: {m.group(0).strip()[:60]}")
    return hits


def _bundled_dangerous_command(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _scan_bundled(skill, _BUNDLED_ERROR_PATTERNS),
        "Potential risk: dangerous command found in a bundled file "
        "(scripts/references/assets), not just SKILL.md itself.",
    )


def _bundled_risky_command(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _scan_bundled(skill, _BUNDLED_WARNING_PATTERNS),
        "Potential risk: risky command found in a bundled file "
        "(scripts/references/assets), not just SKILL.md itself.",
    )


def _rm_rf(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _RM_RF_RE),
        "Potential risk: recursive force-delete command found in a code block.",
    )


def _pipe_to_shell(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _PIPE_SHELL_RE),
        "Potential risk: downloads remote content and pipes it directly into a shell.",
    )


def _eval_exec(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _EVAL_EXEC_RE),
        "Potential risk: dynamic code execution (eval/exec) found in a code block.",
    )


def _sudo(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _SUDO_RE),
        "Potential risk: elevated-privilege command (sudo) found in a code block.",
    )


def _chmod_777(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _CHMOD_777_RE),
        "Potential risk: overly permissive file permissions (chmod 777) found in a code block.",
    )


def _ssh_key_access(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_body(skill, _SSH_KEY_RE),
        "Potential risk: skill references the user's SSH key directory (~/.ssh).",
    )


def _env_access(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_body(skill, _ENV_ACCESS_RE),
        "Potential risk: skill appears to read a .env file, which often holds secrets.",
    )


def _secret_file_read(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _SECRET_FILE_RE),
        "Potential risk: skill appears to read private keys or secret material.",
    )


def _interpolated_shell_input(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _INTERP_SHELL_RE),
        "Potential risk: possible unsanitized variable interpolation into a shell command.",
    )


def _path_traversal(skill: Skill, config: Config) -> list[Draft]:
    skill_root = skill.dir.resolve()
    escapes = []
    for target in local_file_targets(skill.body):
        resolved = (skill.dir / target).resolve()
        try:
            resolved.relative_to(skill_root)
        except ValueError:
            escapes.append(target)
    return _aggregate(
        escapes,
        "Potential risk: file reference escapes the skill's own directory.",
    )


RULES: list[Rule] = [
    FuncRule(
        id="rm-rf",
        category=Category.SECURITY,
        severity=Severity.ERROR,
        description="Flags recursive force-delete commands.",
        fn=_rm_rf,
    ),
    FuncRule(
        id="pipe-to-shell",
        category=Category.SECURITY,
        severity=Severity.ERROR,
        description="Flags downloading and piping remote content into a shell.",
        fn=_pipe_to_shell,
    ),
    FuncRule(
        id="eval-exec",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags dynamic code execution via eval/exec.",
        fn=_eval_exec,
    ),
    FuncRule(
        id="sudo-usage",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags elevated-privilege commands via sudo.",
        fn=_sudo,
    ),
    FuncRule(
        id="chmod-777",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags overly permissive file permissions.",
        fn=_chmod_777,
    ),
    FuncRule(
        id="ssh-key-access",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags references to the user's SSH key directory.",
        fn=_ssh_key_access,
    ),
    FuncRule(
        id="env-file-access",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags reading .env files.",
        fn=_env_access,
    ),
    FuncRule(
        id="secret-file-read",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags reading private keys or secret material.",
        fn=_secret_file_read,
    ),
    FuncRule(
        id="interpolated-shell-input",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags possible unsanitized interpolation into shell commands.",
        fn=_interpolated_shell_input,
    ),
    FuncRule(
        id="path-traversal",
        category=Category.SECURITY,
        severity=Severity.ERROR,
        description="Flags file references that resolve outside the skill's own directory.",
        fn=_path_traversal,
    ),
    FuncRule(
        id="bundled-dangerous-command",
        category=Category.SECURITY,
        severity=Severity.ERROR,
        description="Flags rm -rf / pipe-to-shell patterns inside bundled files.",
        fn=_bundled_dangerous_command,
    ),
    FuncRule(
        id="bundled-risky-command",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags eval/exec/sudo/chmod-777/secret-read patterns inside bundled files.",
        fn=_bundled_risky_command,
    ),
]
