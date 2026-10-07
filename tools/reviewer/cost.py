"""Infracost is the only source of prices. This module only reshapes its JSON."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _num(v: Any) -> Optional[float]:
    """Convert to float, or None when the value is missing or not a number."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def summarize_infracost(doc: Dict[str, Any], top: int = 10) -> Dict[str, Any]:
    """Reduce Infracost JSON to the totals, the monthly delta, every resource with its monthly cost (None = usage-
    based) and what Infracost could not price."""
    total = _num(doc.get("totalMonthlyCost"))
    past = _num(doc.get("pastTotalMonthlyCost"))
    diff = _num(doc.get("diffTotalMonthlyCost"))
    if diff is None and total is not None and past is not None:
        diff = total - past
    drivers: List[Dict[str, Any]] = []
    resources: List[Dict[str, Any]] = []
    for project in doc.get("projects", []):
        for res in (project.get("breakdown") or {}).get("resources", []):
            cost = _num(res.get("monthlyCost"))
            resources.append({"resource": res.get("name"), "monthly_cost": cost})  # None = usage-based, no fixed monthly price
            if cost:
                drivers.append({"resource": res.get("name"), "monthly_cost": cost})
    drivers.sort(key=lambda d: -d["monthly_cost"])
    resources.sort(key=lambda r: (r["monthly_cost"] is None, -(r["monthly_cost"] or 0)))
    sm = doc.get("summary") or {}
    return {
        "source": "infracost",
        "currency": doc.get("currency", "USD"),
        "current_monthly_cost": past,
        "proposed_monthly_cost": total,
        "monthly_delta": diff,
        "top_cost_drivers": drivers[:top],
        "resources": resources[:100],
        # what Infracost could NOT price: unsupported types and resources with no price (free or unpriced)
        "summary": {
            "detected": sm.get("totalDetectedResources"),
            "supported": sm.get("totalSupportedResources"),
            "unsupported": sm.get("totalUnsupportedResources"),
            "usage_based": sm.get("totalUsageBasedResources"),
            "no_price": sm.get("totalNoPriceResources"),
            "unsupported_types": sm.get("unsupportedResourceCounts") or {},
            "no_price_types": sm.get("noPriceResourceCounts") or {},
        },
    }


def load_infracost(path: str) -> Dict[str, Any]:
    """Read an Infracost JSON file and summarize it."""
    with open(path, encoding="utf-8") as fh:
        return summarize_infracost(json.load(fh))
