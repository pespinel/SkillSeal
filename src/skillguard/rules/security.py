"""SECURITY rules: heuristic detection of potentially dangerous patterns.

None of these findings assert a confirmed vulnerability — they flag *potential*
risk for a human to review, since static regex matching over instructions
can't know real intent or execution context.
"""

from __future__ import annotations

import re

from skillguard.models import Category, Severity, Skill
from skillguard.rules.base import Draft, FuncRule, Rule, extract_code_spans

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


def _rm_rf(skill: Skill) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _RM_RF_RE),
        "Potential risk: recursive force-delete command found in a code block.",
    )


def _pipe_to_shell(skill: Skill) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _PIPE_SHELL_RE),
        "Potential risk: downloads remote content and pipes it directly into a shell.",
    )


def _eval_exec(skill: Skill) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _EVAL_EXEC_RE),
        "Potential risk: dynamic code execution (eval/exec) found in a code block.",
    )


def _sudo(skill: Skill) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _SUDO_RE),
        "Potential risk: elevated-privilege command (sudo) found in a code block.",
    )


def _chmod_777(skill: Skill) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _CHMOD_777_RE),
        "Potential risk: overly permissive file permissions (chmod 777) found in a code block.",
    )


def _ssh_key_access(skill: Skill) -> list[Draft]:
    return _aggregate(
        _matches_in_body(skill, _SSH_KEY_RE),
        "Potential risk: skill references the user's SSH key directory (~/.ssh).",
    )


def _env_access(skill: Skill) -> list[Draft]:
    return _aggregate(
        _matches_in_body(skill, _ENV_ACCESS_RE),
        "Potential risk: skill appears to read a .env file, which often holds secrets.",
    )


def _secret_file_read(skill: Skill) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _SECRET_FILE_RE),
        "Potential risk: skill appears to read private keys or secret material.",
    )


def _interpolated_shell_input(skill: Skill) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _INTERP_SHELL_RE),
        "Potential risk: possible unsanitized variable interpolation into a shell command.",
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
]
