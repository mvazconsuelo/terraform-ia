"""Sanitisation: nothing sensitive may leave the repository, and nothing sensitive may reach the AI.

Three layers, from coarse to fine:
  * `blocked_reason` whole files that are never read: a fixed floor (state, keys, .env, tfvars...) plus the repository's
                     own `.geminiignore`;
  * `sanitize_text`  credentials inside any text (known key formats, and `password = "..."` style assignments);
  * `sanitize_value` a value from a plan, using Terraform's own "this is sensitive" mask plus the name of the key.
"""
from __future__ import annotations

import fnmatch
import os
import re
from typing import Any, List, Optional

REDACTED = "<SENSITIVE_VALUE>"

# The floor: files that are NEVER read into the AI's context, whatever any file says. Secrets and state live here.
BLOCKED_GLOBS = [
    "*.tfstate", "*.tfstate.*", "*.tfvars", "*.tfvars.json", ".terraform/*", "*/.terraform/*",
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "id_rsa*", "*credentials*", "*.auto.tfvars",
]

# The repository's own list, on top of the floor: what the AI does not need to read. One pattern per line (`#` starts a comment).
IGNORE_FILE = ".geminiignore"

# A key NAME that suggests a secret: the value of `db_password`, `api_key`... is hidden whatever it contains.
SENSITIVE_KEY_RE = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|connection[_-]?string)")

# Secrets recognised by their shape, wherever they appear.
_VALUE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                       # AWS access key id
    re.compile(r"ASIA[0-9A-Z]{16}"),                       # AWS temporary access key id
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),             # GitHub token
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),                # Google API key
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),           # Slack token
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),   # JSON web token
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),   # private key block
]

# An assignment of a secret-looking name, anywhere in the text (a PR description is prose, not a config file):
#     password = "hunter2"      token: abc123      api_key = 'zzz'
# group 1 = the name and the `=` or `:`; group 2 = the value (quoted, or up to the next space, comma or semicolon).
_ASSIGNMENT_RE = re.compile(
    r'(?i)(\b[\w.-]*(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential)\w*\s*[=:]\s*)'
    r'(\\?".*?\\?"|\'.*?\'|[^\s#,;]+)'
)

# A value that starts like this is a Terraform reference (var.x, module.x.y), not a secret, so it is kept.
_REFERENCE_RE = re.compile(r'^"?(var|local|data|module|aws_|each|self)\b')


def _matches(path: str, pattern: str) -> bool:
    """Whether a path matches a pattern. `docs/` blocks everything under that folder; anything else is a shell pattern
    matched against the whole path and against the file name."""
    normalized = path.replace(os.sep, "/")
    if pattern.endswith("/"):
        return normalized.startswith(pattern) or ("/" + pattern) in ("/" + normalized)
    return fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(os.path.basename(normalized), pattern)


def ignore_patterns(root: str) -> List[str]:
    """The patterns of the repository's `.geminiignore`: what the AI must not read, besides the always-blocked floor."""
    path = os.path.join(root, IGNORE_FILE)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        lines = [line.strip() for line in handle]
    return [line for line in lines if line and not line.startswith("#")]


def is_blocked(path: str) -> bool:
    """True for file types that must never leave the repository (the floor: see BLOCKED_GLOBS)."""
    return any(_matches(path, pattern) for pattern in BLOCKED_GLOBS)


def blocked_reason(path: str, root: Optional[str] = None) -> Optional[str]:
    """Why the AI must not read this file, or None when it may: a sensitive file type, or listed in `.geminiignore`."""
    if is_blocked(path):
        return "blocked: sensitive file type"
    if root is not None and any(_matches(path, pattern) for pattern in ignore_patterns(root)):
        return "ignored by {}".format(IGNORE_FILE)
    return None


def sanitize_text(text: str) -> str:
    """Redact credentials and secret-looking assignments in text. References such as var.x or module.x are kept."""
    for pattern in _VALUE_PATTERNS:
        text = pattern.sub(REDACTED, text)

    def redact_assignment(match: "re.Match[str]") -> str:
        value = match.group(2)
        if _REFERENCE_RE.match(value.strip("\"'")):
            return match.group(0)                              # `password = var.db_password`: leave it alone
        return match.group(1) + '"{}"'.format(REDACTED)

    return _ASSIGNMENT_RE.sub(redact_assignment, text)


def sanitize_value(value: Any, sensitive_mask: Any = None, key: str = "") -> Any:
    """Redact a value from a plan.

    `sensitive_mask` is Terraform's `after_sensitive`: it has the same shape as the value, with True where Terraform knows
    the value is secret. On top of that, a string stored under a secret-looking key name is hidden too."""
    if sensitive_mask is True:
        return REDACTED

    if isinstance(value, dict):
        mask = sensitive_mask if isinstance(sensitive_mask, dict) else {}
        return {name: sanitize_value(item, mask.get(name), name) for name, item in value.items()}

    if isinstance(value, list):
        mask = sensitive_mask if isinstance(sensitive_mask, list) else []
        return [sanitize_value(item, mask[index] if index < len(mask) else None, key) for index, item in enumerate(value)]

    if isinstance(value, str):
        if key and SENSITIVE_KEY_RE.search(key):
            return REDACTED
        return sanitize_text(value)
    return value


def sanitize_tree(value: Any) -> Any:
    """Sanitize every string inside a JSON-like structure, keeping its shape (so it stays valid JSON)."""
    if isinstance(value, dict):
        return {name: sanitize_tree(item) for name, item in value.items()}
    if isinstance(value, list):
        return [sanitize_tree(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value
