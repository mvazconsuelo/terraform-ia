"""Grounding: the model may only mention resources, files and prices that exist in the evidence it was given.

A language model can write a plausible Terraform address, file name or price that does not exist. After the model answers,
every address, file path and dollar amount in its text is checked against the evidence; anything that cannot be verified is
replaced by a marker and reported, never published as fact.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

# A Terraform address. Matches both forms:
#   module.database.aws_rds_cluster.this["1"]      (a resource inside one or more modules)
#   aws_s3_bucket.logs                              (a resource at the top level)
_ADDRESS_RE = re.compile(
    r'(?:module\.[A-Za-z0-9_\-]+\.)+[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_\-]+(?:\[[^\]\s]+\])?'
    r'|\baws_[a-z0-9_]+\.[A-Za-z0-9_\-]+(?:\[[^\]\s]+\])?'
)
# A file path with at least one folder and a known extension: infra/web/network.tf  (a bare `network.tf` is not checked).
_FILE_RE = re.compile(r"(?<![\w./:-])((?:[\w.-]+/)+[\w.-]+\.(?:tf|tftpl|tfvars|hcl|yaml|yml|json|md))\b")
# A dollar amount: $69.72   $1,234   $ 5
_MONEY_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")

UNVERIFIED_REF = "<unverified reference>"
UNVERIFIED_FILE = "<unverified file>"
UNVERIFIED_AMOUNT = "<unverified amount>"


def allowed_amounts(costs: Dict[str, Dict[str, Any]]) -> List[float]:
    """Every number Infracost gave us, plus the absolute value of each. No other price may appear in the model's text."""
    amounts: List[float] = []
    for cost in (costs or {}).values():
        for key in ("current_monthly_cost", "proposed_monthly_cost", "monthly_delta"):
            value = cost.get(key)
            if isinstance(value, (int, float)):
                amounts += [float(value), abs(float(value))]
        for resource in list(cost.get("top_cost_drivers", [])) + list(cost.get("resources", [])):
            if isinstance(resource.get("monthly_cost"), (int, float)):
                amounts.append(float(resource["monthly_cost"]))
    return amounts


def ground_text(
    text: Optional[str],
    corpus: str,
    amounts: List[float],
    file_exists: Optional[Callable[[str], bool]] = None,
) -> Tuple[Optional[str], List[str]]:
    """Check a text from the model. Returns (the text with unverifiable parts replaced, a note for each replacement).

      * a Terraform address must appear in `corpus` (everything the model was shown);
      * a file path must appear in `corpus` or exist in the repository (`file_exists`);
      * a dollar amount must be within $1 of a number Infracost reported (`amounts`)."""
    if not text:
        return text, []
    notes: List[str] = []
    haystack = corpus.replace('\\"', '"')       # the corpus is JSON, where quotes are escaped

    def check_address(match: "re.Match[str]") -> str:
        address = match.group(0)
        if address in haystack:
            return address
        notes.append("reference `{}` is not in the provided plan or files".format(address))
        return UNVERIFIED_REF

    def check_file(match: "re.Match[str]") -> str:
        path = match.group(1)
        if path in haystack or (file_exists is not None and file_exists(path)):
            return match.group(0)
        notes.append("file `{}` does not exist in the repository or the change".format(path))
        return match.group(0).replace(path, UNVERIFIED_FILE)

    def check_amount(match: "re.Match[str]") -> str:
        value = float(match.group(1).replace(",", ""))
        if any(abs(value - known) < 1.0 for known in amounts):
            return match.group(0)
        notes.append("amount {} is not in the Infracost data".format(match.group(0).strip()))
        return UNVERIFIED_AMOUNT

    # Addresses first: they contain dots and brackets but never a slash, so the file pattern cannot match inside them.
    checked = _ADDRESS_RE.sub(check_address, text)
    checked = _FILE_RE.sub(check_file, checked)
    checked = _MONEY_RE.sub(check_amount, checked)
    return checked, notes


def evidence_corpus(evidence: Dict[str, Any]) -> str:
    """Everything the model was shown, as one string. What the model cites is checked against this."""
    parts = [item.get("path", "") + "\n" + item.get("content", "") for item in evidence["changed_files"]]
    parts += [
        json.dumps(evidence["deterministic_findings"]),
        json.dumps(evidence.get("plans") or {}),
        json.dumps(evidence.get("costs") or {}),
    ]
    return "\n".join(parts)


def file_exists(root: str) -> Callable[[str], bool]:
    """A function that says whether a path is a real file inside the repository (a path outside it never counts)."""
    base = os.path.abspath(root)

    def exists(path: str) -> bool:
        full_path = os.path.abspath(os.path.join(base, path))
        return full_path.startswith(base + os.sep) and os.path.isfile(full_path)

    return exists
