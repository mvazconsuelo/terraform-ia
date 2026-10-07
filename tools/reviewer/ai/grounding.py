"""Grounding: the model may only mention resources, files and prices that exist in the evidence it was given.

Anything that cannot be verified is replaced by a marker and reported, never published as fact.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

_ADDRESS_RE = re.compile(
    r'(?:module\.[A-Za-z0-9_\-]+\.)+[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_\-]+(?:\[[^\]\s]+\])?'
    r'|\baws_[a-z0-9_]+\.[A-Za-z0-9_\-]+(?:\[[^\]\s]+\])?'
)
_FILE_RE = re.compile(r"(?<![\w./:-])((?:[\w.-]+/)+[\w.-]+\.(?:tf|tftpl|tfvars|hcl|yaml|yml|json|md))\b")
_MONEY_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")

UNVERIFIED_REF = "<unverified reference>"
UNVERIFIED_FILE = "<unverified file>"
UNVERIFIED_AMOUNT = "<unverified amount>"


def allowed_amounts(costs: Dict[str, Dict[str, Any]]) -> List[float]:
    """Every number Infracost gave us (and absolute deltas); nothing else may appear as a price in the model's text."""
    nums: List[float] = []
    for c in (costs or {}).values():
        for key in ("current_monthly_cost", "proposed_monthly_cost", "monthly_delta"):
            v = c.get(key)
            if isinstance(v, (int, float)):
                nums += [float(v), abs(float(v))]
        for d in c.get("top_cost_drivers", []):
            if isinstance(d.get("monthly_cost"), (int, float)):
                nums.append(float(d["monthly_cost"]))
    return nums


def ground_text(
    text: Optional[str],
    corpus: str,
    amounts: List[float],
    file_exists: Optional[Callable[[str], bool]] = None,
) -> Tuple[Optional[str], List[str]]:
    """Replace Terraform addresses not in the corpus, files that do not exist, and dollar amounts Infracost did not report."""
    if not text:
        return text, []
    notes: List[str] = []
    haystack = corpus.replace('\\"', '"')

    def ref(m: "re.Match[str]") -> str:
        found = m.group(0)
        if found in haystack:
            return found
        notes.append("reference `{}` is not in the provided plan or files".format(found))
        return UNVERIFIED_REF

    def file(m: "re.Match[str]") -> str:
        path = m.group(1)
        if path in haystack or (file_exists is not None and file_exists(path)):
            return m.group(0)
        notes.append("file `{}` does not exist in the repository or the change".format(path))
        return m.group(0).replace(path, UNVERIFIED_FILE)

    def money(m: "re.Match[str]") -> str:
        value = float(m.group(1).replace(",", ""))
        if any(abs(value - a) < 1.0 for a in amounts):
            return m.group(0)
        notes.append("amount {} is not in the Infracost data".format(m.group(0).strip()))
        return UNVERIFIED_AMOUNT

    # addresses first: they contain dots and brackets but never a slash, so the file pattern cannot match inside them
    out = _ADDRESS_RE.sub(ref, text)
    out = _FILE_RE.sub(file, out)
    out = _MONEY_RE.sub(money, out)
    return out, notes


def evidence_corpus(evidence: Dict[str, Any]) -> str:
    """Everything the model was shown, as one string: what it cites is checked against this."""
    parts = [f.get("path", "") + "\n" + f.get("content", "") for f in evidence["changed_files"]]
    parts += [json.dumps(evidence["deterministic_findings"]), json.dumps(evidence.get("plans") or {}), json.dumps(evidence.get("costs") or {})]
    return "\n".join(parts)


def file_exists(root: str) -> Callable[[str], bool]:
    """A predicate for 'this path is a real file inside the repository' (never outside it)."""
    base = os.path.abspath(root)

    def exists(path: str) -> bool:
        full = os.path.abspath(os.path.join(base, path))
        return full.startswith(base + os.sep) and os.path.isfile(full)

    return exists
