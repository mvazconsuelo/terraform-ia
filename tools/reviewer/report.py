"""Markdown rendering of the PR comment.

Everything except "AI Summary" is produced by code from deterministic inputs (checks, plan, Infracost, rules): that is the
evidence. "AI Summary" is the only text from a model, a human-readable reading of that same evidence; with the AI off or
failing, the rest of the comment is exactly the same.
"""
from __future__ import annotations

from typing import Any, Dict, List

MARKER = "<!-- terra-review -->"
STATUS_LABEL = {"success": "✅ PASS", "failure": "❌ FAIL", "cancelled": "⏹️ CANCELLED", "skipped": "⏭️ SKIPPED"}
MANDATORY_TAGS = ["Environment", "Owner", "CostCenter", "Project"]
STANDARD_CATEGORIES = ("MODULE_STANDARD", "ARCHITECTURE")
SEVERITY_ROWS = [("CRITICAL", "Critical"), ("HIGH", "High"), ("MEDIUM", "Medium"), ("LOW", "Low"), ("INFO", "Informational")]
ICON = {"CRITICAL": "🛑", "HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡", "INFO": "🔵"}
MAX_LIST = 50


def _money(v: Any, signed: bool = False) -> str:
    if v is None:
        return "n/a"
    text = "${:,.2f}".format(abs(v))
    if signed:
        return ("+" if v >= 0 else "-") + text
    return ("-" if v < 0 else "") + text


def _loc(f: Dict[str, Any]) -> str:
    if not f.get("file"):
        return "no file"
    return "{}:{}".format(f["file"], f["line"]) if f.get("line") else f["file"]


def _cap(lines: List[str]) -> List[str]:
    return lines if len(lines) <= MAX_LIST else lines[:MAX_LIST] + ["... and {} more".format(len(lines) - MAX_LIST)]


# ----------------------------------------------------------------------------------------------------------------
# AI Summary: the only generated text
# ----------------------------------------------------------------------------------------------------------------
def _ai_summary(review: Dict[str, Any]) -> List[str]:
    out = ["## AI Summary", ""]
    analysis = review.get("ai_analysis")
    status = review.get("ai_status") or {}
    if not analysis:
        if status.get("requested"):
            out += ["⚠️ AI summary unavailable.", "", "The deterministic review completed successfully."]
            reason = " ".join(str(status.get("reason") or "").split())
            if reason:
                out += ["", "_{}_".format(reason)]
        else:
            out += ["ℹ️ AI summary is disabled (`ai.enabled` is false in `common.yaml`).", "", "The deterministic review completed successfully."]
        return out
    out.append(analysis["summary"])
    notes = analysis.get("grounding_notes") or []
    if notes:
        out += ["", "> ⚠️ Parts of the summary could not be verified against the plan, the files or Infracost and were removed: " + "; ".join(notes) + "."]
    return out


# ----------------------------------------------------------------------------------------------------------------
# Evidence sections
# ----------------------------------------------------------------------------------------------------------------
def _affected(affected: List[Dict[str, Any]], changed: List[Dict[str, Any]]) -> List[str]:
    if not affected:
        return ["_No Terraform configuration is affected by this change; Terraform was not run._"]
    paths = [c["path"] for c in changed]
    out: List[str] = []
    for a in affected:
        root = a["root"]
        under = [p for p in paths if p.startswith(root + "/")]
        direct = sorted(p[len(root) + 1:] for p in under)
        direct_reasons = {"{} changed".format(p) for p in under}
        indirect = [r for r in a["reasons"] if r not in direct_reasons]
        out += ["### `{}`".format(root), ""]
        if direct:
            out += ["Changed configuration:", ""] + ["- `{}`".format(f) for f in _cap(direct)] + [""]
        if indirect:
            out += ["Affected through:", ""] + ["- {}".format(r) for r in indirect[:5]] + [""]
    return out[:-1] if out and out[-1] == "" else out


def _checks(checks: Dict[str, str]) -> List[str]:
    if not checks:
        return ["_No check results were provided._"]
    rows = ["| Check | Result |", "|---|---|"]
    for name, status in checks.items():
        rows.append("| {} | {} |".format(name[:1].upper() + name[1:], STATUS_LABEL.get(status, "❔ " + str(status).upper())))
    ran = [s for s in checks.values() if s != "skipped"]
    passed = sum(1 for s in ran if s == "success")
    result = "**Result:** {}/{} checks passed.".format(passed, len(ran)) if ran else "**Result:** no check ran."
    skipped = len(checks) - len(ran)
    if skipped:
        result += " {} skipped.".format(skipped)
    return rows + ["", result]


def _by_action(plan: Dict[str, Any]):
    rcs = plan.get("resource_changes", [])
    add = [rc["address"] for rc in rcs if rc.get("actions") == ["create"]]
    change = [rc["address"] for rc in rcs if rc.get("actions") == ["update"]]
    destroy = [rc["address"] for rc in rcs if rc.get("actions") == ["delete"]]
    replace = [rc["address"] for rc in rcs if rc.get("replace")]
    return add, change, destroy, replace


def _plan(plans: Dict[str, dict]) -> List[str]:
    if not plans:
        return ["_No Terraform plan was available._"]
    multi = len(plans) > 1
    h = "####" if multi else "###"
    out: List[str] = []
    for root, plan in sorted(plans.items()):
        add, change, destroy, replace = _by_action(plan)
        if multi:
            out += ["### `{}`".format(root), ""]
        line = "{} to add · {} to change · {} to destroy".format(len(add), len(change), len(destroy))
        if replace:
            line += " · {} to replace".format(len(replace))
        out += ["**Plan:** `{}`".format(line), ""]
        for title, sign, items in (("Resources to add", "+", add), ("Resources to change", "~", change),
                                   ("Resources to destroy", "-", destroy), ("Resources to replace", "-/+", replace)):
            if title.endswith("replace") and not items:
                continue
            body = _cap(["{} {}".format(sign, a) for a in items]) if items else ["None"]
            out += ["{} {}".format(h, title), "", "```text"] + body + ["```", ""]
    return out[:-1]


def _resource_changes(plans: Dict[str, dict]) -> List[str]:
    if not plans:
        return ["_No Terraform plan was available._"]
    multi = len(plans) > 1
    groups: Dict[str, List[Dict[str, str]]] = {"Added": [], "Modified": [], "Destroyed": [], "Replaced": []}
    for root, plan in sorted(plans.items()):
        for rc in plan.get("resource_changes", []):
            actions = rc.get("actions") or []
            key = "Replaced" if rc.get("replace") else {"create": "Added", "update": "Modified", "delete": "Destroyed"}.get(actions[0] if len(actions) == 1 else "")
            if key:
                groups[key].append({"root": root, "address": rc.get("address") or "", "type": rc.get("type") or ""})
    out: List[str] = []
    for title, items in groups.items():
        if not items:
            continue
        head = "| Resource | Type | Configuration |" if multi else "| Resource | Type |"
        sep = "|---|---|---|" if multi else "|---|---|"
        out += ["### {}".format(title), "", head, sep]
        for it in items[:MAX_LIST]:
            row = "| `{}` | `{}` |".format(it["address"], it["type"])
            out.append(row + (" `{}` |".format(it["root"]) if multi else ""))
        if len(items) > MAX_LIST:
            out.append("| _... and {} more_ | | |".format(len(items) - MAX_LIST) if multi else "| _... and {} more_ | |".format(len(items) - MAX_LIST))
        out.append("")
    return out[:-1] if out else ["_The plan changes no resources._"]


def _replacements(plans: Dict[str, dict]) -> List[str]:
    if not plans:
        return ["_No Terraform plan was available, so replacements could not be checked._"]
    items: List[str] = []
    for root, plan in sorted(plans.items()):
        for rc in plan.get("resource_changes", []):
            if rc.get("replace"):
                paths = rc.get("replace_paths") or []
                forced = " (forced by: {})".format(", ".join(".".join(map(str, p)) if isinstance(p, list) else str(p) for p in paths)) if paths else ""
                items.append("⚠️ `{}` in `{}`{}".format(rc.get("address"), root, forced))
    if not items:
        return ["✅ **No resource replacement detected.**", "", "`Resources requiring replacement: 0`"]
    return _cap(items) + ["", "`Resources requiring replacement: {}`".format(len(items)), "",
                          "A replacement destroys the resource and creates a new one; for stateful resources that means data loss or downtime."]


def _cost(costs: Dict[str, dict]) -> List[str]:
    if not costs:
        return ["_No cost estimate was available._"]
    multi = len(costs) > 1
    out: List[str] = []
    for root, c in sorted(costs.items()):
        delta = c.get("monthly_delta")
        if multi:
            out += ["### `{}`".format(root), ""]
        if delta is not None:
            out += ["**Estimated monthly change: {}**".format(_money(delta, True)), ""]
        out += ["Current {}/month → proposed {}/month.".format(_money(c.get("current_monthly_cost")), _money(c.get("proposed_monthly_cost"))), ""]
        resources = c.get("resources")
        if resources is None:  # an older summary without the full list
            resources = [{"resource": d["resource"], "monthly_cost": d["monthly_cost"]} for d in c.get("top_cost_drivers") or []]
        priced = [r for r in resources if r.get("monthly_cost")]
        usage = [r for r in resources if not r.get("monthly_cost")]
        proposed = c.get("proposed_monthly_cost")
        if resources:
            shown = priced[:8]
            rows = ["| Resource | Monthly cost |", "|---|---:|"] + ["| `{}` | {} |".format(r["resource"], _money(r["monthly_cost"])) for r in shown]
            if proposed is not None:
                rest = proposed - sum(r["monthly_cost"] for r in shown)
                if rest > 0.005:
                    rows.append("| Other priced resources | {} |".format(_money(rest)))
            rows += ["| `{}` | usage-based, not estimated |".format(r["resource"]) for r in usage[:8]]
            if len(usage) > 8:
                rows.append("| _... and {} more usage-based_ | |".format(len(usage) - 8))
            if proposed is not None:
                rows.append("| **Total (proposed)** | **{}** |".format(_money(proposed)))
            out += rows + [""]
        sm = c.get("summary") or {}
        notes = []
        for key, label in (("unsupported_types", "Not supported by Infracost"), ("no_price_types", "No price (free, or not priced)")):
            types = sm.get(key) or {}
            if types:
                notes.append("{}: {}".format(label, ", ".join("`{}` ×{}".format(t, n) for t, n in sorted(types.items())[:8])))
        if notes:
            out += ["> ℹ️ Resources without a price are not part of this total. " + "; ".join(notes) + ".", ""]
        if delta is not None:
            # from the rounded monthly figure shown above, so the two numbers always agree
            out += ["**Annualized impact:** {}".format(_money(round(delta, 2) * 12, True)), ""]
    return out[:-1]


def _governance(plans: Dict[str, dict], findings: List[Dict[str, Any]]) -> List[str]:
    problems: List[str] = []
    tagged = [rc for plan in plans.values() for rc in plan.get("resource_changes", []) if rc.get("tag_keys") is not None]
    for tag in MANDATORY_TAGS:
        missing = [rc["address"] for rc in tagged if tag not in rc["tag_keys"]]
        if missing:
            problems.append("❌ Tag `{}` is missing on {}".format(tag, ", ".join("`{}`".format(m) for m in missing[:5])))
    for f in (f for f in findings if f["category"] == "GOVERNANCE"):
        problems.append("❌ {} (`{}`) — {}".format(f["title"], _loc(f), f["evidence"]))
    if problems:
        return problems
    return ["✅ **No governance violations found.**", "",
            "Validated: mandatory tags on the taggable resources in the code{}.".format(" and on the planned resources" if tagged else "")]


def _standard(findings: List[Dict[str, Any]]) -> List[str]:
    items = [f for f in findings if f["category"] in STANDARD_CATEGORIES]
    if not items:
        return ["✅ **The change follows the repository module contract.**", "",
                "Validated: required module files, resource naming, typed variables, module boundaries and domain layout."]
    out: List[str] = []
    for f in items:
        out += ["⚠️ **{}**{}".format(f["title"], " (`{}`)".format(f["rule_id"]) if f.get("rule_id") else ""), "", f["evidence"], ""]
        if f.get("expected"):
            out += ["Expected:", "`{}`".format(f["expected"]), ""]
        out += ["Detected:", "`{}`".format(_loc(f)), ""]
    return out[:-1]


def _contract(findings: List[Dict[str, Any]], rules_evaluated: Any) -> List[str]:
    violations = [f for f in findings if f.get("rule_id")]
    out = ["✅ **No contract violations detected.**" if not violations else "❌ **{} contract violation{} detected.**".format(len(violations), "" if len(violations) == 1 else "s"), ""]
    if rules_evaluated is not None:
        out.append("**Rules evaluated:** {}  ".format(rules_evaluated))
    out.append("**Violations:** {}".format(len(violations)))
    return out


def _other(findings: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for f in (f for f in findings if f["category"] not in STANDARD_CATEGORIES and f["category"] != "GOVERNANCE"):
        rid = " `{}`".format(f["rule_id"]) if f.get("rule_id") else ""
        out.append("{} **{} / {}**{} — {} (`{}`)".format(ICON.get(f["severity"], ""), f["severity"], f["category"], rid, f["title"], _loc(f)))
        out.append("  - {}".format(f["evidence"]))
        out.append("  - Fix: {}".format(f["recommendation"]))
    return out


def _findings(findings: List[Dict[str, Any]]) -> List[str]:
    rows = ["| Severity | Findings |", "|---|---:|"]
    for key, label in SEVERITY_ROWS:
        rows.append("| {} | {} |".format(label, sum(1 for f in findings if f["severity"] == key)))
    other = _other(findings)
    return rows + (["", "### Details", ""] + other if other else [])


def _decision(review: Dict[str, Any]) -> List[str]:
    reasons = review.get("decision_reasons") or []
    out = ["**{}**".format(review["decision"]), ""]
    if reasons:
        out += ["The deterministic review found blocking issues:", ""] + ["- {}".format(r) for r in reasons]
    else:
        out.append("The deterministic review found no blocking violations.")
    return out + ["", "*This reviewer does not approve, merge, or apply infrastructure.*"]


def _target(target: Any) -> str:
    """Which environment this change lands on; empty line when the target branch is unknown (a local run)."""
    if not target:
        return "**Environment:** unknown (no target branch given)  "
    account = " · AWS account `{}`".format(target["account"]) if target.get("account") else " · AWS account not configured in `common.yaml`"
    return "**Environment:** `{}` ({}){}  ".format(target["branch"], target["environment"], account)


def render_markdown(review: Dict[str, Any]) -> str:
    plans, costs, findings = review.get("plans", {}), review.get("costs", {}), review["findings"]
    changed = review.get("changed_files", [])
    sections = [
        _ai_summary(review),
        ["## Affected Terraform configurations", ""] + _affected(review.get("affected", []), changed),
        ["## Validation & Tests", ""] + _checks(review.get("checks", {})),
        ["## Terraform Plan", ""] + _plan(plans),
        ["## Resource Changes", ""] + _resource_changes(plans),
        ["## Replacement", ""] + _replacements(plans),
        ["## Cost", ""] + _cost(costs),
        ["## Governance", ""] + _governance(plans, findings),
        ["## Module Standard", ""] + _standard(findings),
        ["## Repository Contract", ""] + _contract(findings, review.get("rules_evaluated")),
        ["## Deterministic Findings", ""] + _findings(findings),
        ["## Review Decision", ""] + _decision(review),
    ]
    lines = [MARKER, "# Infrastructure Review", "",
             "**Risk:** {} · **Decision:** {}  ".format(review["risk"], review["decision"]),
             _target(review.get("target")),
             "*This reviewer cannot approve, merge, or apply infrastructure.*", "", "---", ""]
    for i, section in enumerate(sections):
        lines += section
        if i < len(sections) - 1:
            lines += ["", "---", ""]
    return "\n".join(lines) + "\n"
