"""The checks that read the terraform plan and the Infracost estimate: what will happen, and what it will cost.

Each function implements one rule of rules.yaml. They are facts about the plan, correlated with the repository's standards; a
model never decides them. Plans and costs are dicts keyed by the root path they belong to.

  PLAN-001  the plan destroys or replaces a stateful resource (database, bucket, key, cluster...)
  COST-002  Infracost reports a monthly increase above the rule's threshold
"""
from __future__ import annotations

from typing import Dict, List

from ..review.finding import Finding
from .registry import make_finding, plan_check

# --------------------------------------------------------------------------------------------------------------------
# PLAN: what terraform will do
# --------------------------------------------------------------------------------------------------------------------

@plan_check("plan_destroys_stateful_resource")
def plan_destroys_stateful_resource(plans: Dict[str, dict], costs: Dict[str, dict], rule: dict) -> List[Finding]:
    """PLAN-001: the plan destroys or replaces a stateful resource (CRITICAL in a protected root or on a plain
    destroy, HIGH for a replacement elsewhere)."""
    findings = []
    stateful_types = set(rule["stateful_types"])                       # databases, buckets, keys... (from rules.yaml)
    is_protected = rule.get("_protected", lambda root: False)

    for root, plan in sorted(plans.items()):
        for change in plan.get("resource_changes", []):
            destroys = "delete" in change.get("actions", [])           # a replacement is "delete" + "create"
            if change.get("type") not in stateful_types or not destroys:
                continue

            replaced = bool(change.get("replace"))
            # A plain destroy is always critical. A replacement is critical only in a protected root.
            severity = "CRITICAL" if (is_protected(root) or not replaced) else "HIGH"
            what = "replaced (destroyed and recreated)" if replaced else "destroyed"

            forcing = change.get("replace_paths") or []               # the attributes that force the replacement
            forcing_text = ", ".join(".".join(str(part) for part in path) if isinstance(path, list) else str(path) for path in forcing)
            why = " Forcing attributes: {}.".format(forcing_text) if forcing else ""

            findings.append(make_finding(
                rule,
                "{}: {} ({}) will be {}.{}".format(root, change.get("address"), change.get("type"), what, why),
                root, None, change.get("address"), severity=severity,
            ))
    return findings


# --------------------------------------------------------------------------------------------------------------------
# COST: what it will cost (the figure comes from Infracost)
# --------------------------------------------------------------------------------------------------------------------

@plan_check("plan_cost_increase_above_threshold")
def plan_cost_increase_above_threshold(plans: Dict[str, dict], costs: Dict[str, dict], rule: dict) -> List[Finding]:
    """COST-002: Infracost reports a monthly increase above the rule's threshold."""
    findings = []
    limit = float(rule["monthly_delta_usd"])
    for root, cost in sorted(costs.items()):
        delta = cost.get("monthly_delta")
        if delta is not None and delta > limit:
            evidence = "{}: Infracost estimates {:+,.0f} {}/month (threshold {:,.0f}); current {} -> proposed {}.".format(
                root, delta, cost.get("currency", "USD"), limit, cost.get("current_monthly_cost"), cost.get("proposed_monthly_cost"))
            findings.append(make_finding(rule, evidence, root, None, None))
    return findings
