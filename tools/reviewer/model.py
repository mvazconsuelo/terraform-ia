"""Shared data structures: the Finding every check produces, and the constants around it."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

CATEGORIES = [
    "MODULE_STANDARD", "ARCHITECTURE", "SECURITY", "COST", "GOVERNANCE", "RELIABILITY",
    "LIFECYCLE", "NETWORKING", "KUBERNETES", "STYLE", "TESTING", "DOCUMENTATION",
]
SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
DECISIONS = ["PASS", "REQUEST_CHANGES"]


@dataclass
class Finding:
    severity: str
    category: str
    title: str
    evidence: str
    explanation: str
    recommendation: str
    confidence: str = "HIGH"
    type: str = "CONFIRMED"
    resource: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    rule_id: Optional[str] = None
    source: str = "deterministic"
    expected: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def severity_rank(sev: str) -> int:
    return SEVERITIES.index(sev) if sev in SEVERITIES else len(SEVERITIES)
