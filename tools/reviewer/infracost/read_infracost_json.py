"""Infracost is the only source of prices. This module only reshapes its JSON; it never calculates or guesses a price."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _number(value: Any) -> Optional[float]:
    """Convert to float, or None when the value is missing or not a number."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_infracost(document: Dict[str, Any], top: int = 10) -> Dict[str, Any]:
    """Reduce Infracost JSON to what the report needs.

    Returns the current and proposed monthly cost and their difference, every resource with its monthly cost (None means
    "usage-based": it has no fixed monthly price), the most expensive resources, and what Infracost could not price."""
    proposed = _number(document.get("totalMonthlyCost"))
    current = _number(document.get("pastTotalMonthlyCost"))
    delta = _number(document.get("diffTotalMonthlyCost"))
    if delta is None and proposed is not None and current is not None:
        delta = proposed - current

    resources: List[Dict[str, Any]] = []
    for project in document.get("projects", []):
        for resource in (project.get("breakdown") or {}).get("resources", []):
            monthly_cost = _number(resource.get("monthlyCost"))
            resources.append({"resource": resource.get("name"), "monthly_cost": monthly_cost})

    # Most expensive first; resources with no fixed price go last.
    resources.sort(key=lambda resource: (resource["monthly_cost"] is None, -(resource["monthly_cost"] or 0)))
    priced = [resource for resource in resources if resource["monthly_cost"]]
    top_cost_drivers = sorted(priced, key=lambda resource: -resource["monthly_cost"])[:top]

    summary = document.get("summary") or {}
    return {
        "source": "infracost",
        "currency": document.get("currency", "USD"),
        "current_monthly_cost": current,
        "proposed_monthly_cost": proposed,
        "monthly_delta": delta,
        "top_cost_drivers": top_cost_drivers,
        "resources": resources[:100],
        # What Infracost could NOT price: resource types it does not support, and resources with no price (free or unpriced).
        "summary": {
            "detected": summary.get("totalDetectedResources"),
            "supported": summary.get("totalSupportedResources"),
            "unsupported": summary.get("totalUnsupportedResources"),
            "usage_based": summary.get("totalUsageBasedResources"),
            "no_price": summary.get("totalNoPriceResources"),
            "unsupported_types": summary.get("unsupportedResourceCounts") or {},
            "no_price_types": summary.get("noPriceResourceCounts") or {},
        },
    }


def load_infracost(path: str) -> Dict[str, Any]:
    """Read an Infracost JSON file and summarize it."""
    with open(path, encoding="utf-8") as handle:
        return summarize_infracost(json.load(handle))
