"""Sanitisation: nothing sensitive may reach the LLM."""
from __future__ import annotations

import fnmatch
import os
import re
from typing import Any

REDACTED = "<SENSITIVE_VALUE>"

# Files that are never read into the context.
BLOCKED_GLOBS = [
    "*.tfstate", "*.tfstate.*", "*.tfvars", "*.tfvars.json", ".terraform/*", "*/.terraform/*",
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "id_rsa*", "*credentials*", "*.auto.tfvars",
]

SENSITIVE_KEY_RE = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|connection[_-]?string)")

_VALUE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
]
# `password = "x"`, `token: abc`, ... anywhere in the text (a PR description is prose, not a config file).
_ASSIGN_RE = re.compile(r'(?i)(\b[\w.-]*(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential)\w*\s*[=:]\s*)(\\?".*?\\?"|\'.*?\'|[^\s#,;]+)')


def is_blocked(path: str) -> bool:
    p = path.replace(os.sep, "/")
    base = os.path.basename(p)
    return any(fnmatch.fnmatch(p, g) or fnmatch.fnmatch(base, g) for g in BLOCKED_GLOBS)


def sanitize_text(text: str) -> str:
    for pat in _VALUE_PATTERNS:
        text = pat.sub(REDACTED, text)

    def repl(m: "re.Match[str]") -> str:
        val = m.group(2)
        # Keep references (var.x, local.x, data.x, module.x) - they are not secrets.
        if re.match(r'^"?(var|local|data|module|aws_|each|self)\b', val.strip("\"'")):
            return m.group(0)
        return m.group(1) + '"{}"'.format(REDACTED)

    return _ASSIGN_RE.sub(repl, text)


def sanitize_value(value: Any, sensitive_mask: Any = None, key: str = "") -> Any:
    """Redact a plan value using Terraform's `*_sensitive` mask plus key-name heuristics."""
    if sensitive_mask is True:
        return REDACTED
    if isinstance(value, dict):
        mask = sensitive_mask if isinstance(sensitive_mask, dict) else {}
        return {k: sanitize_value(v, mask.get(k), k) for k, v in value.items()}
    if isinstance(value, list):
        mask = sensitive_mask if isinstance(sensitive_mask, list) else []
        return [sanitize_value(v, mask[i] if i < len(mask) else None, key) for i, v in enumerate(value)]
    if isinstance(value, str):
        if key and SENSITIVE_KEY_RE.search(key):
            return REDACTED
        return sanitize_text(value)
    return value


def sanitize_tree(value: Any) -> Any:
    """Sanitize every string inside a JSON-like structure, keeping its shape (and so keeping it valid JSON)."""
    if isinstance(value, dict):
        return {k: sanitize_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_tree(v) for v in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value
