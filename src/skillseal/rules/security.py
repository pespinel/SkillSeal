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
from skillseal.rules.base import (
    HIDDEN_UNICODE_RE,
    Draft,
    FuncRule,
    Rule,
    extract_code_spans,
    frontmatter_key_line,
    local_file_targets,
    offset_to_line,
)

_RM_RF_RE = re.compile(r"\brm\s+(-\w*[rR]\w*[fF]\w*|-\w*[fF]\w*[rR]\w*)\b")
_PIPE_SHELL_RE = re.compile(
    r"\b(curl|wget|iwr|invoke-webrequest)\b[^\n|]*\|\s*(sudo\s+)?"
    r"(sh|bash|zsh|python3?|node|perl|iex|invoke-expression)\b",
    re.IGNORECASE,
)
_EVAL_EXEC_RE = re.compile(r"\b(eval|exec)\s*\(")
_SUDO_RE = re.compile(r"\bsudo\b")
_CHMOD_777_RE = re.compile(r"\bchmod\s+(-R\s+)?0?777\b")
_SSH_KEY_RE = re.compile(r"~/\.ssh\b")
_CREDENTIAL_PATH_RE = re.compile(
    r"~/\.(aws/credentials|config/gh/hosts\.yml|docker/config\.json|kube/config|npmrc|netrc)\b",
    re.IGNORECASE,
)
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

# --- prompt-injection surface ----------------------------------------------
#
# SKILL.md is text loaded directly into an agent's context, not just a doc a
# human reads — these target hidden or override-style instructions embedded
# in the prose itself, distinct from the dangerous-*command* rules above.

# HIDDEN_UNICODE_RE (imported from rules.base): zero-width/joiner marks
# (U+200B-200F), bidi embedding/override controls (U+202A-202E), and a
# mid-text BOM (U+FEFF) — a leading file BOM is already stripped in
# parser.py, so any of these found here is embedded, not the file's own
# encoding artifact.
_INSTRUCTION_OVERRIDE_RE = re.compile(
    r"ignore\s+(all\s+|the\s+)?previous\s+instructions"
    r"|disregard\s+(all\s+|the\s+)?(above|previous)"
    r"|you\s+are\s+now\b"
    r"|<\s*important\s*>"
    r"|\[\s*system\s*\]"
    r"|system\s+prompt\s*:",
    re.IGNORECASE,
)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# {40,} chars of base64 alphabet, then require mixed case so a lowercase (or
# uppercase) hex hash doesn't false-positive.
_BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
_EXFIL_REACH_RE = re.compile(r"https?://|\b(curl|fetch|invoke-webrequest|iwr)\b", re.IGNORECASE)
_EXFIL_SECRET_RE = re.compile(
    r"~/\.aws\b|~/\.ssh\b|\.env\b|\$GITHUB_TOKEN\b|\bAPI_KEY\b", re.IGNORECASE
)
_EXFIL_PROXIMITY_LINES = 5

# agentskills.io: 'allowed-tools' is a space-separated string of tool grants
# (e.g. "Bash(git *) Read"). Bare "Bash" or a "Tool(*)" wildcard pre-approves
# unrestricted access - a decision a reviewer should see explicitly.
_BROAD_TOOL_GRANT_RE = re.compile(r"^(Bash|\w+\(\*\))$")


def _aggregate(matches: list[tuple[str, int]], message: str, skill: Skill) -> list[Draft]:
    if not matches:
        return []
    sample_text, sample_offset = matches[0]
    sample = sample_text.strip()[:80]
    detail = f'{len(matches)} occurrence(s), e.g. "{sample}"'
    return [Draft(message=message, detail=detail, line=offset_to_line(skill, sample_offset))]


def _matches_in_code(skill: Skill, pattern: re.Pattern[str]) -> list[tuple[str, int]]:
    return [
        (m.group(0), span_offset + m.start())
        for span, span_offset in extract_code_spans(skill.body)
        for m in pattern.finditer(span)
    ]


def _matches_in_body(skill: Skill, pattern: re.Pattern[str]) -> list[tuple[str, int]]:
    return [(m.group(0), m.start()) for m in pattern.finditer(skill.body)]


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
    hits = _scan_bundled(skill, _BUNDLED_ERROR_PATTERNS)
    if not hits:
        return []
    detail = f'{len(hits)} occurrence(s), e.g. "{hits[0][:80]}"'
    return [
        Draft(
            message="Potential risk: dangerous command found in a bundled file "
            "(scripts/references/assets), not just SKILL.md itself.",
            detail=detail,
        )
    ]


def _bundled_risky_command(skill: Skill, config: Config) -> list[Draft]:
    hits = _scan_bundled(skill, _BUNDLED_WARNING_PATTERNS)
    if not hits:
        return []
    detail = f'{len(hits)} occurrence(s), e.g. "{hits[0][:80]}"'
    return [
        Draft(
            message="Potential risk: risky command found in a bundled file "
            "(scripts/references/assets), not just SKILL.md itself.",
            detail=detail,
        )
    ]


def _rm_rf(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _RM_RF_RE),
        "Potential risk: recursive force-delete command found in a code block.",
        skill,
    )


def _pipe_to_shell(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _PIPE_SHELL_RE),
        "Potential risk: downloads remote content and pipes it directly into a shell.",
        skill,
    )


def _eval_exec(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _EVAL_EXEC_RE),
        "Potential risk: dynamic code execution (eval/exec) found in a code block.",
        skill,
    )


def _sudo(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _SUDO_RE),
        "Potential risk: elevated-privilege command (sudo) found in a code block.",
        skill,
    )


def _chmod_777(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _CHMOD_777_RE),
        "Potential risk: overly permissive file permissions (chmod 777) found in a code block.",
        skill,
    )


def _ssh_key_access(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_body(skill, _SSH_KEY_RE),
        "Potential risk: skill references the user's SSH key directory (~/.ssh).",
        skill,
    )


def _credential_path_access(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_body(skill, _CREDENTIAL_PATH_RE),
        "Potential risk: skill references a credential file "
        "(AWS, GitHub CLI, Docker, kube, npm, or netrc).",
        skill,
    )


def _env_access(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_body(skill, _ENV_ACCESS_RE),
        "Potential risk: skill appears to read a .env file, which often holds secrets.",
        skill,
    )


def _secret_file_read(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _SECRET_FILE_RE),
        "Potential risk: skill appears to read private keys or secret material.",
        skill,
    )


def _interpolated_shell_input(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_code(skill, _INTERP_SHELL_RE),
        "Potential risk: possible unsanitized variable interpolation into a shell command.",
        skill,
    )


def _hidden_unicode(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_body(skill, HIDDEN_UNICODE_RE),
        "Potential risk: invisible or directional-override Unicode character found — "
        "a classic hidden-instruction vector.",
        skill,
    )


def _instruction_override_language(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_body(skill, _INSTRUCTION_OVERRIDE_RE),
        "Potential risk: language resembling an instruction override "
        '(e.g. "ignore previous instructions") found in the skill body.',
        skill,
    )


def _html_comment_in_body(skill: Skill, config: Config) -> list[Draft]:
    return _aggregate(
        _matches_in_body(skill, _HTML_COMMENT_RE),
        "SKILL.md contains an HTML comment — usually benign, but the standard place "
        "to hide instructions from a human reviewer while an agent still reads it.",
        skill,
    )


def _long_base64_blob(skill: Skill, config: Config) -> list[Draft]:
    matches = [
        (m.group(0), m.start())
        for m in _BASE64_BLOB_RE.finditer(skill.body)
        if any(c.islower() for c in m.group(0)) and any(c.isupper() for c in m.group(0))
    ]
    return _aggregate(
        matches,
        "Potential risk: long base64-like blob found, which may hide an encoded "
        "instruction or payload.",
        skill,
    )


def _exfiltration_shape(skill: Skill, config: Config) -> list[Draft]:
    # Only the *reach* (the actual network action) needs to be in code —
    # that's the actionable part. The secret reference is left whole-body:
    # prose legitimately points an agent at a secret ("read the key at
    # ~/.ssh/id_rsa") right before a code block does the reaching. Requiring
    # code for reach alone still catches that, but no longer catches hygiene
    # *advice* like "never hardcode the key, use env vars, fetch it securely"
    # — both sides of that sentence are prose, not a real network call (74%
    # of hits on a 1,142-skill corpus, see #28).
    reach_lines = {
        offset_to_line(skill, offset) for _, offset in _matches_in_code(skill, _EXFIL_REACH_RE)
    }
    secret_lines = {offset_to_line(skill, m.start()) for m in _EXFIL_SECRET_RE.finditer(skill.body)}
    hits = [
        (r, s) for r in reach_lines for s in secret_lines if abs(r - s) <= _EXFIL_PROXIMITY_LINES
    ]
    if not hits:
        return []
    detail = f"{len(hits)} co-located occurrence(s) within {_EXFIL_PROXIMITY_LINES} lines"
    return [
        Draft(
            message="Potential risk: a network call and a secret-ish reference appear close "
            "together — reading a secret and reaching the network are each fine alone, but "
            "co-located, they're the exfiltration shape.",
            detail=detail,
            line=min(min(pair) for pair in hits),
        )
    ]


def _tool_grant_tokens(skill: Skill) -> list[str]:
    raw = skill.frontmatter.get("allowed-tools")
    if isinstance(raw, str):
        return raw.split()
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _broad_tool_grant(skill: Skill, config: Config) -> list[Draft]:
    if skill.frontmatter_error is not None:
        return []
    matches = [t for t in _tool_grant_tokens(skill) if _BROAD_TOOL_GRANT_RE.match(t)]
    if not matches:
        return []
    return [
        Draft(
            message="'allowed-tools' pre-approves an unrestricted tool grant — a reviewer "
            "should see this decision explicitly.",
            detail=f"broad grant(s): {', '.join(sorted(set(matches)))}",
            line=frontmatter_key_line(skill, "allowed-tools"),
        )
    ]


def _path_traversal(skill: Skill, config: Config) -> list[Draft]:
    skill_root = skill.dir.resolve()
    escapes = []
    for target, offset in local_file_targets(skill.body):
        # A reference to a *sibling skill's own manifest* (../other-skill/
        # SKILL.md) is a common, benign cross-referencing convention in a
        # skills collection — not the traversal-to-sensitive-files pattern
        # this rule exists to catch (~/.ssh, .env, /etc/...). Narrow: only
        # the target's filename, not any other escape, is exempted.
        if Path(target).name == "SKILL.md":
            continue
        resolved = (skill.dir / target).resolve()
        try:
            resolved.relative_to(skill_root)
        except ValueError:
            escapes.append((target, offset))
    return _aggregate(
        escapes,
        "Potential risk: file reference escapes the skill's own directory.",
        skill,
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
        id="credential-path-access",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags references to common credential files beyond SSH keys.",
        fn=_credential_path_access,
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
    FuncRule(
        id="hidden-unicode-chars",
        category=Category.SECURITY,
        severity=Severity.ERROR,
        description="Flags invisible or directional-override Unicode characters.",
        fn=_hidden_unicode,
    ),
    FuncRule(
        id="instruction-override-language",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description='Flags language resembling an instruction override, e.g. "ignore '
        'previous instructions".',
        fn=_instruction_override_language,
    ),
    FuncRule(
        id="html-comment-in-body",
        category=Category.SECURITY,
        severity=Severity.INFO,
        description="Surfaces HTML comments in the skill body — the standard hiding place.",
        fn=_html_comment_in_body,
    ),
    FuncRule(
        id="long-base64-blob",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags long mixed-case base64-like blobs that may hide encoded content.",
        fn=_long_base64_blob,
    ),
    FuncRule(
        id="exfiltration-shape",
        category=Category.SECURITY,
        # Downgraded from ERROR after a 1,142-skill corpus measurement (#28):
        # even restricted to code, this heuristic can't tell "send your own
        # API key to the service that issued it" (a completely standard auth
        # example) from real exfiltration to an unrelated destination — that
        # needs semantic understanding of the URL's trust, not proximity.
        severity=Severity.WARNING,
        description="Flags a network call co-located with a secret-ish reference.",
        fn=_exfiltration_shape,
    ),
    FuncRule(
        id="broad-tool-grant",
        category=Category.SECURITY,
        severity=Severity.WARNING,
        description="Flags 'allowed-tools' pre-approving an unrestricted tool grant.",
        fn=_broad_tool_grant,
    ),
]
