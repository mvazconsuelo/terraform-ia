"""Shared data structures: the Finding every check produces, and the severity order."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

CATEGORIES = [
    "MODULE_STANDARD", "ARCHITECTURE", "SECURITY", "COST", "GOVERNANCE", "RELIABILITY",
    "LIFECYCLE", "NETWORKING", "KUBERNETES", "STYLE", "TESTING", "DOCUMENTATION",
]
# From the worst to the mildest. The position in this list is the "rank" used to compare severities.
SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
DECISIONS = ["PASS", "REQUEST_CHANGES"]


@dataclass
class Finding:
    """One deterministic result of a check: what was found, where, why it matters and how to fix it."""
    severity: str                       # one of SEVERITIES
    category: str                       # one of CATEGORIES
    title: str                          # short name of the problem (from the rule)
    evidence: str                       # what exactly was found, in this repository
    explanation: str                    # why it matters (from the rule)
    recommendation: str                 # how to fix it (from the rule)
    confidence: str = "HIGH"
    type: str = "CONFIRMED"             # CONFIRMED findings can block a PR; INFERRED ones cannot
    resource: Optional[str] = None      # the Terraform address involved, if any
    file: Optional[str] = None          # where it was found
    line: Optional[int] = None
    rule_id: Optional[str] = None       # e.g. "MODULE-001"
    source: str = "deterministic"
    expected: Optional[str] = None      # what it should look like, when the check can say

    def to_dict(self) -> Dict[str, Any]:
        """Plain dict for the JSON output and the AI payload."""
        return asdict(self)


def severity_rank(severity: str) -> int:
    """Position of a severity (0 = CRITICAL); lower is worse. Unknown values rank last."""
    return SEVERITIES.index(severity) if severity in SEVERITIES else len(SEVERITIES)
