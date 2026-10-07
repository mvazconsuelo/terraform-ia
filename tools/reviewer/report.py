"""Markdown rendering of the PR comment.

Everything above "AI Analysis" is produced by code from deterministic inputs (checks, plan, Infracost, rules). The AI
section is the only part that comes from a model; with the AI off, the rest of the comment is exactly the same.
"""
from __future__ import annotations

from typing import Any, Dict, List

MARKER = "<!-- terra-review -->"
ICON = {"CRITICAL": "🛑", "HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡", "INFO": "🔵"}
STATUS = {"success": "✅", "failure": "❌", "cancelled": "⏹️", "skipped": "⏭️"}
MANDATORY_TAGS = ["Environment", "Owner", "CostCenter", "Project"]
STANDARD_CATEGORIES = ("MODULE_STANDARD", "ARCHITECTURE")


def _plural(n: int, word: str) -> str:
    return "{} {}{}".format(n, word, "" if n == 1 else "s")


def _money(v: Any) -> str:
    return "n/a" if v is None else "${:,.0f}".format(v)


def _loc(f: Dict[str, Any]) -> str:
    if not f.get("file"):
        return "no file"
    return "{}:{}".format(f["file"], f["line"]) if f.get("line") else f["file"]


def _validation(checks: Dict[str, str]) -> List[str]:
    if not checks:
        return ["_No check results were provided._"]
    return ["{} {}".format(STATUS.get(status, "❔"), name) for name, status in checks.items()]


def _plan_section(plans: Dict[str, dict]) -> List[str]:
    if not plans:
        return ["_No terraform plan available (it needs the cloud credentials of the configuration)._"]
    out: List[str] = []
    for env, plan in sorted(plans.items()):
        c = plan.get("counts", {})
        add = c.get("create", 0) + c.get("replace", 0)
        change = c.get("update", 0)
        destroy = c.get("delete", 0) + c.get("replace", 0)
        out += ["**{}**".format(env), "", "🟢 {} to add".format(_plural(add, "resource")),
                "🟡 {} to change".format(_plural(change, "resource")), "🔴 {} to destroy".format(_plural(destroy, "resource")), ""]
    return out


def _replacements(plans: Dict[str, dict]) -> List[str]:
    out: List[str] = []
    for env, plan in sorted(plans.items()):
        for rc in plan.get("resource_changes", []):
            if rc.get("replace"):
                paths = rc.get("replace_paths") or []
                forced = " (forced by: {})".format(", ".join(".".join(map(str, p)) if isinstance(p, list) else str(p) for p in paths)) if paths else ""
                out.append("⚠️ `{}` in **{}**{}".format(rc.get("address"), env, forced))
    if not out:
        return ["✅ No resource is replaced."]
    return out + ["", "A replacement destroys the resource and creates a new one; for stateful resources that means data loss or downtime."]


def _cost(costs: Dict[str, dict]) -> List[str]:
    if not costs:
        return ["_No cost estimate available (Infracost was not run)._"]
    out: List[str] = []
    for env, c in sorted(costs.items()):
        delta = c.get("monthly_delta")
        out.append("**{}**: {}/month → {}/month".format(env, _money(c.get("current_monthly_cost")), _money(c.get("proposed_monthly_cost"))))
        if delta is not None:
            out.append("{} {:+,.0f}/month".format("📈" if delta > 0 else "📉" if delta < 0 else "➖", delta))
        drivers = c.get("top_cost_drivers") or []
        if drivers:
            out += ["", "Main drivers:"] + ["- {} ({}/month)".format(d["resource"], _money(d["monthly_cost"])) for d in drivers[:3]]
        out.append("")
    return out


def _governance(plans: Dict[str, dict], findings: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    tagged = [rc for plan in plans.values() for rc in plan.get("resource_changes", []) if rc.get("tag_keys") is not None]
    if tagged:
        for tag in MANDATORY_TAGS:
            missing = [rc["address"] for rc in tagged if tag not in rc["tag_keys"]]
            out.append("✅ {}".format(tag) if not missing else "❌ {} missing on {}".format(tag, ", ".join("`{}`".format(m) for m in missing[:5])))
    gov = [f for f in findings if f["category"] == "GOVERNANCE"]
    for f in gov:
        out.append("❌ {} (`{}`) — {}".format(f["title"], _loc(f), f["evidence"]))
    if not tagged and not gov:
        out.append("✅ No governance violations found in the code.")
    return out


def _standard(findings: List[Dict[str, Any]]) -> List[str]:
    items = [f for f in findings if f["category"] in STANDARD_CATEGORIES]
    if not items:
        return ["✅ The change follows the repository module contract."]
    out: List[str] = []
    for f in items:
        out += ["⚠️ **{}**{}".format(f["title"], " (`{}`)".format(f["rule_id"]) if f.get("rule_id") else ""), "", f["evidence"], ""]
        if f.get("expected"):
            out += ["Expected:", "`{}`".format(f["expected"]), ""]
        out += ["Detected:", "`{}`".format(_loc(f)), ""]
    return out


def _other(findings: List[Dict[str, Any]]) -> List[str]:
    items = [f for f in findings if f["category"] not in STANDARD_CATEGORIES and f["category"] != "GOVERNANCE"]
    out: List[str] = []
    for f in items:
        rid = " `{}`".format(f["rule_id"]) if f.get("rule_id") else ""
        out.append("{} **{} / {}**{} — {} (`{}`){}".format(
            ICON.get(f["severity"], ""), f["severity"], f["category"], rid, f["title"], _loc(f),
            "" if f["source"].startswith("deterministic") else " _[AI, {} evidence]_".format(f["type"].lower())))
        out.append("  - {}".format(f["evidence"]))
        out.append("  - Fix: {}".format(f["recommendation"]))
    return out


INTENT = {"match": "✅ The plan matches the stated intent", "mismatch": "⚠️ The plan does not match the stated intent", "unclear": "❔ Intent versus plan is unclear"}
IMPACT = {"none": "⚪ none", "low": "🟡 low", "medium": "🟠 medium", "high": "🔴 high", "critical": "🛑 critical"}


def _ai(review: Dict[str, Any]) -> List[str]:
    out = ["---", "", "### AI Analysis", ""]
    a = review.get("ai_analysis")
    if not a:
        out.append("`AI review was not executed.`")
        reason = (review.get("ai_status") or {}).get("reason")
        if reason:
            out += ["", "_{}_".format(reason)]
        return out
    intent, impact = a["intent_vs_infrastructure"], a["architecture_impact"]
    out += ["#### Intent vs Infrastructure", "", "**{}**".format(INTENT.get(intent["status"], intent["status"])), "", intent["explanation"], "",
            "#### Architecture Impact", "", "**Severity: {}**".format(IMPACT.get(impact["severity"], impact["severity"])), "", impact["explanation"], "",
            "#### Reviewer Summary", "", a["reviewer_summary"]]
    notes = a.get("grounding_notes") or []
    if notes:
        out += ["", "> ⚠️ Parts of the AI text could not be verified against the plan, the files or Infracost and were removed: " + "; ".join(notes) + "."]
    return out


def _affected(affected: List[Dict[str, Any]]) -> List[str]:
    if not affected:
        return ["_No Terraform configuration is affected by this change; terraform was not run._"]
    out: List[str] = []
    for a in affected:
        out.append("- `{}` — {}".format(a["root"], "; ".join(a["reasons"][:3]) + (" …" if len(a["reasons"]) > 3 else "")))
    return out


def render_markdown(review: Dict[str, Any]) -> str:
    plans, costs, findings = review.get("plans", {}), review.get("costs", {}), review["findings"]
    lines = [MARKER, "## Infrastructure Review", "",
             "**Risk:** {}  ·  **Decision:** {}{} _(this reviewer cannot approve or merge)_".format(review["risk"], review["decision"], " — " + "; ".join(review["decision_reasons"]) if review.get("decision_reasons") else ""), "",
             "### Affected Terraform configurations", ""] + _affected(review.get("affected", []))
    lines += ["", "### Tests", ""] + _validation(review.get("checks", {}))
    lines += ["", "### Terraform Plan", ""] + _plan_section(plans)
    lines += ["### Replacement", ""] + _replacements(plans)
    lines += ["", "### Cost", ""] + _cost(costs)
    lines += ["### Governance", ""] + _governance(plans, findings)
    lines += ["", "### Module Standard", ""] + _standard(findings)
    other = _other(findings)
    if other:
        lines += ["", "### Other findings", ""] + other
    lines += [""] + _ai(review)
    lines += ["", "<sub>Advisory only. Deterministic results are authoritative; the AI section only interprets them.</sub>"]
    return "\n".join(lines) + "\n"
