"""Markdown rendering of the PR comment.

The comment has two kinds of content:

  * the EVIDENCE: every section except the first is produced by code from deterministic inputs (the checks, the plan,
    Infracost, the rules);
  * the AI SUMMARY: the only text written by a model, a plain-language reading of that same evidence. With the AI off or
    failing, the rest of the comment is exactly the same.

Each `_section` function below returns the lines of one section; `render_markdown` joins them.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# A hidden marker on the first line: the workflow finds its own comment by it and edits it instead of adding a new one.
MARKER = "<!-- terra-review -->"

# How each CI job result is shown in the "Validation & Tests" table.
STATUS_LABEL = {
    "success": "✅ PASS", "warning": "⚠️ FINDINGS", "failure": "❌ FAIL", "cancelled": "⏹️ CANCELLED", "skipped": "⏭️ SKIPPED",
}
MANDATORY_TAGS = ["Environment", "Owner", "CostCenter", "Project"]     # checked on the planned resources
STANDARD_CATEGORIES = ("MODULE_STANDARD", "ARCHITECTURE")              # findings shown under "Module Standard"
SEVERITY_ROWS = [("CRITICAL", "Critical"), ("HIGH", "High"), ("MEDIUM", "Medium"), ("LOW", "Low"), ("INFO", "Informational")]
ICON = {"CRITICAL": "🛑", "HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡", "INFO": "🔵"}
MAX_LIST = 50          # long lists are cut after this many entries
MAX_COST_ROWS = 8      # rows of the cost table, for priced and for usage-based resources


# ----------------------------------------------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------------------------------------------
def _money(amount: Any, signed: bool = False) -> str:
    """A dollar amount with two decimals; `signed` forces a leading + or -. None (unknown) shows as n/a."""
    if amount is None:
        return "n/a"
    text = "${:,.2f}".format(abs(amount))
    if signed:
        return ("+" if amount >= 0 else "-") + text
    return ("-" if amount < 0 else "") + text


def _location(finding: Dict[str, Any]) -> str:
    """`file:line` of a finding."""
    if not finding.get("file"):
        return "no file"
    if finding.get("line"):
        return "{}:{}".format(finding["file"], finding["line"])
    return finding["file"]


def _cut(lines: List[str]) -> List[str]:
    """Keep the first MAX_LIST lines and say how many were left out."""
    if len(lines) <= MAX_LIST:
        return lines
    return lines[:MAX_LIST] + ["... and {} more".format(len(lines) - MAX_LIST)]


def _forcing_attributes(paths: List[Any]) -> str:
    """The attributes that force a replacement, e.g. `kms_key_id, engine_version`."""
    names = []
    for path in paths:
        names.append(".".join(str(part) for part in path) if isinstance(path, list) else str(path))
    return ", ".join(names)


def _without_trailing_blank(lines: List[str]) -> List[str]:
    """Drop the blank line most sections leave at the end, so the separators between sections are even."""
    return lines[:-1] if lines and lines[-1] == "" else lines


# ----------------------------------------------------------------------------------------------------------------
# AI Summary
# ----------------------------------------------------------------------------------------------------------------
def _ai_summary(review: Dict[str, Any]) -> List[str]:
    """The AI Summary section, or the reason it is missing."""
    lines = ["## AI Summary", ""]
    analysis = review.get("ai_analysis")
    status = review.get("ai_status") or {}

    if not analysis:
        if status.get("requested"):
            lines += ["⚠️ AI summary unavailable.", "", "The deterministic review completed successfully."]
            reason = " ".join(str(status.get("reason") or "").split())      # one line, whatever the API sent back
            if reason:
                lines += ["", "_{}_".format(reason)]
        else:
            lines += ["ℹ️ AI summary is disabled (`ai.enabled` is false in `common.yaml`).", "", "The deterministic review completed successfully."]
        return lines

    lines.append(analysis["summary"])
    notes = analysis.get("grounding_notes") or []
    if notes:
        lines += ["", "> ⚠️ Parts of the summary could not be verified against the plan, the files or Infracost and were removed: " + "; ".join(notes) + "."]
    return lines


# ----------------------------------------------------------------------------------------------------------------
# Evidence: what changed and what ran
# ----------------------------------------------------------------------------------------------------------------
def _affected(affected: List[Dict[str, Any]], changed: List[Dict[str, Any]]) -> List[str]:
    """The affected configurations, with the files changed in each and, for the rest, why it was affected."""
    if not affected:
        return ["_No Terraform configuration is affected by this change; Terraform was not run._"]

    changed_paths = [item["path"] for item in changed]
    lines: List[str] = []
    for item in affected:
        root = item["root"]
        files_in_root = [path for path in changed_paths if path.startswith(root + "/")]
        names_in_root = sorted(path[len(root) + 1:] for path in files_in_root)            # shown relative to the root
        reasons_already_shown = {"{} changed".format(path) for path in files_in_root}
        other_reasons = [reason for reason in item["reasons"] if reason not in reasons_already_shown]

        lines += ["### `{}`".format(root), ""]
        if names_in_root:
            lines += ["Changed configuration:", ""] + ["- `{}`".format(name) for name in _cut(names_in_root)] + [""]
        if other_reasons:
            lines += ["Affected through:", ""] + ["- {}".format(reason) for reason in other_reasons[:5]] + [""]
    return _without_trailing_blank(lines)


def _checks(checks: Dict[str, str]) -> List[str]:
    """The table of CI job results and a one-line count: how many passed, had findings, or were skipped."""
    if not checks:
        return ["_No check results were provided._"]

    rows = ["| Check | Result |", "|---|---|"]
    for name, status in checks.items():
        label = STATUS_LABEL.get(status, "❔ " + str(status).upper())
        rows.append("| {} | {} |".format(name[:1].upper() + name[1:], label))

    ran = [status for status in checks.values() if status != "skipped"]
    passed = sum(1 for status in ran if status == "success")
    with_findings = sum(1 for status in ran if status == "warning")
    skipped = len(checks) - len(ran)

    summary = "**Result:** {}/{} checks passed.".format(passed, len(ran)) if ran else "**Result:** no check ran."
    if with_findings:
        summary += " {} with findings that do not block.".format(with_findings)
    if skipped:
        summary += " {} skipped.".format(skipped)
    return rows + ["", summary]


# ----------------------------------------------------------------------------------------------------------------
# Evidence: the plan
# ----------------------------------------------------------------------------------------------------------------
def _addresses_by_action(plan: Dict[str, Any]) -> Tuple[List[str], List[str], List[str], List[str]]:
    """The addresses in a plan, grouped as (to add, to change, to destroy, to replace)."""
    changes = plan.get("resource_changes", [])
    to_add = [change["address"] for change in changes if change.get("actions") == ["create"]]
    to_change = [change["address"] for change in changes if change.get("actions") == ["update"]]
    to_destroy = [change["address"] for change in changes if change.get("actions") == ["delete"]]
    to_replace = [change["address"] for change in changes if change.get("replace")]
    return to_add, to_change, to_destroy, to_replace


def _plan(plans: Dict[str, dict]) -> List[str]:
    """For each root: the plan counts and the list of resources to add, change, destroy and replace."""
    if not plans:
        return ["_No Terraform plan was available._"]

    several_roots = len(plans) > 1
    sub_heading = "####" if several_roots else "###"
    lines: List[str] = []
    for root, plan in sorted(plans.items()):
        to_add, to_change, to_destroy, to_replace = _addresses_by_action(plan)
        if several_roots:
            lines += ["### `{}`".format(root), ""]

        counts = "{} to add · {} to change · {} to destroy".format(len(to_add), len(to_change), len(to_destroy))
        if to_replace:
            counts += " · {} to replace".format(len(to_replace))
        lines += ["**Plan:** `{}`".format(counts), ""]

        groups = (("Resources to add", "+", to_add), ("Resources to change", "~", to_change),
                  ("Resources to destroy", "-", to_destroy), ("Resources to replace", "-/+", to_replace))
        for title, sign, addresses in groups:
            if title == "Resources to replace" and not addresses:
                continue                                  # the replace list only appears when something is replaced
            body = _cut(["{} {}".format(sign, address) for address in addresses]) if addresses else ["None"]
            lines += ["{} {}".format(sub_heading, title), "", "```text"] + body + ["```", ""]
    return _without_trailing_blank(lines)


def _change_group(change: Dict[str, Any]) -> Optional[str]:
    """Which table a planned change belongs to: Added, Modified, Destroyed or Replaced (None for anything else)."""
    if change.get("replace"):
        return "Replaced"
    actions = change.get("actions") or []
    if len(actions) != 1:
        return None
    return {"create": "Added", "update": "Modified", "delete": "Destroyed"}.get(actions[0])


def _resource_changes(plans: Dict[str, dict]) -> List[str]:
    """Tables of the added, modified, destroyed and replaced resources (address and type)."""
    if not plans:
        return ["_No Terraform plan was available._"]

    several_roots = len(plans) > 1
    groups: Dict[str, List[Dict[str, str]]] = {"Added": [], "Modified": [], "Destroyed": [], "Replaced": []}
    for root, plan in sorted(plans.items()):
        for change in plan.get("resource_changes", []):
            group = _change_group(change)
            if group:
                groups[group].append({"root": root, "address": change.get("address") or "", "type": change.get("type") or ""})

    lines: List[str] = []
    for title, items in groups.items():
        if not items:
            continue
        header = "| Resource | Type | Configuration |" if several_roots else "| Resource | Type |"
        divider = "|---|---|---|" if several_roots else "|---|---|"
        lines += ["### {}".format(title), "", header, divider]
        for item in items[:MAX_LIST]:
            row = "| `{}` | `{}` |".format(item["address"], item["type"])
            lines.append(row + (" `{}` |".format(item["root"]) if several_roots else ""))
        if len(items) > MAX_LIST:
            left_out = len(items) - MAX_LIST
            lines.append("| _... and {} more_ | | |".format(left_out) if several_roots else "| _... and {} more_ | |".format(left_out))
        lines.append("")
    return _without_trailing_blank(lines) if lines else ["_The plan changes no resources._"]


def _replacements(plans: Dict[str, dict]) -> List[str]:
    """The replaced resources and the attributes that force each replacement."""
    if not plans:
        return ["_No Terraform plan was available, so replacements could not be checked._"]

    replaced: List[str] = []
    for root, plan in sorted(plans.items()):
        for change in plan.get("resource_changes", []):
            if not change.get("replace"):
                continue
            forcing = change.get("replace_paths") or []
            forced_by = " (forced by: {})".format(_forcing_attributes(forcing)) if forcing else ""
            replaced.append("⚠️ `{}` in `{}`{}".format(change.get("address"), root, forced_by))

    if not replaced:
        return ["✅ **No resource replacement detected.**", "", "`Resources requiring replacement: 0`"]
    return _cut(replaced) + [
        "", "`Resources requiring replacement: {}`".format(len(replaced)), "",
        "A replacement destroys the resource and creates a new one; for stateful resources that means data loss or downtime.",
    ]


# ----------------------------------------------------------------------------------------------------------------
# Evidence: cost
# ----------------------------------------------------------------------------------------------------------------
def _cost_table(cost: Dict[str, Any], resources: List[Dict[str, Any]]) -> List[str]:
    """The resource table: the priced ones, a row for the rest, the usage-based ones, and the total.

    It is built so the rows add up to the total shown at the bottom."""
    priced = [resource for resource in resources if resource.get("monthly_cost")]
    usage_based = [resource for resource in resources if not resource.get("monthly_cost")]    # no fixed monthly price
    proposed = cost.get("proposed_monthly_cost")

    shown = priced[:MAX_COST_ROWS]
    rows = ["| Resource | Monthly cost |", "|---|---:|"]
    rows += ["| `{}` | {} |".format(resource["resource"], _money(resource["monthly_cost"])) for resource in shown]
    if proposed is not None:
        not_shown = proposed - sum(resource["monthly_cost"] for resource in shown)
        if not_shown > 0.005:
            rows.append("| Other priced resources | {} |".format(_money(not_shown)))
    rows += ["| `{}` | usage-based, not estimated |".format(resource["resource"]) for resource in usage_based[:MAX_COST_ROWS]]
    if len(usage_based) > MAX_COST_ROWS:
        rows.append("| _... and {} more usage-based_ | |".format(len(usage_based) - MAX_COST_ROWS))
    if proposed is not None:
        rows.append("| **Total (proposed)** | **{}** |".format(_money(proposed)))
    return rows + [""]


def _unpriced_note(cost: Dict[str, Any]) -> List[str]:
    """A note listing the resource types Infracost could not price; they are not part of the total."""
    summary = cost.get("summary") or {}
    parts = []
    for key, label in (("unsupported_types", "Not supported by Infracost"), ("no_price_types", "No price (free, or not priced)")):
        types = summary.get(key) or {}
        if types:
            listed = ", ".join("`{}` ×{}".format(name, count) for name, count in sorted(types.items())[:8])
            parts.append("{}: {}".format(label, listed))
    if not parts:
        return []
    return ["> ℹ️ Resources without a price are not part of this total. " + "; ".join(parts) + ".", ""]


def _cost_for_root(root: str, cost: Dict[str, Any], several_roots: bool) -> List[str]:
    """The cost section of one root; every block ends with a blank line."""
    lines: List[str] = []
    if several_roots:
        lines += ["### `{}`".format(root), ""]

    delta = cost.get("monthly_delta")
    resources = cost.get("resources")
    if resources is None:                           # an older summary that only has the top cost drivers
        resources = [{"resource": driver["resource"], "monthly_cost": driver["monthly_cost"]} for driver in cost.get("top_cost_drivers") or []]

    # The change is "partial" when some resources could not be priced: say so in the title.
    has_unpriced = any(not resource.get("monthly_cost") for resource in cost.get("resources") or [])
    has_unsupported = bool((cost.get("summary") or {}).get("unsupported_types"))
    partial = has_unpriced or has_unsupported

    if delta is not None:
        lines += ["**Estimated monthly change{}: {}**".format(" (priced resources only)" if partial else "", _money(delta, True)), ""]
    lines += ["Current {}/month → proposed {}/month.".format(_money(cost.get("current_monthly_cost")), _money(cost.get("proposed_monthly_cost"))), ""]
    if resources:
        lines += _cost_table(cost, resources)
    lines += _unpriced_note(cost)
    if delta is not None:
        # Computed from the rounded monthly figure printed above, so the two numbers always agree (69.72 x 12 = 836.64).
        lines += ["**Annualized impact:** {}".format(_money(round(delta, 2) * 12, True)), ""]
    return lines


def _cost(costs: Dict[str, dict]) -> List[str]:
    """The cost estimate of each root: monthly change, resource table, unpriced resources and the annualized impact."""
    if not costs:
        return ["_No cost estimate was available._"]
    lines: List[str] = []
    for root, cost in sorted(costs.items()):
        lines += _cost_for_root(root, cost, several_roots=len(costs) > 1)
    return _without_trailing_blank(lines)


# ----------------------------------------------------------------------------------------------------------------
# Evidence: rules
# ----------------------------------------------------------------------------------------------------------------
def _governance(plans: Dict[str, dict], findings: List[Dict[str, Any]]) -> List[str]:
    """Mandatory-tag problems: missing tags on planned resources, and findings in the GOVERNANCE category."""
    problems: List[str] = []

    planned_with_tags = []
    for plan in plans.values():
        for change in plan.get("resource_changes", []):
            if change.get("tag_keys") is not None:         # only resources that can carry tags
                planned_with_tags.append(change)
    for tag in MANDATORY_TAGS:
        without_tag = [change["address"] for change in planned_with_tags if tag not in change["tag_keys"]]
        if without_tag:
            listed = ", ".join("`{}`".format(address) for address in without_tag[:5])
            problems.append("❌ Tag `{}` is missing on {}".format(tag, listed))

    for finding in findings:
        if finding["category"] == "GOVERNANCE":
            problems.append("❌ {} (`{}`) — {}".format(finding["title"], _location(finding), finding["evidence"]))

    if problems:
        return problems
    where = " and on the planned resources" if planned_with_tags else ""
    return ["✅ **No governance violations found.**", "", "Validated: mandatory tags on the taggable resources in the code{}.".format(where)]


def _standard(findings: List[Dict[str, Any]]) -> List[str]:
    """The module-standard findings, or a confirmation that there are none."""
    items = [finding for finding in findings if finding["category"] in STANDARD_CATEGORIES]
    if not items:
        return ["✅ **The change follows the repository module contract.**", "",
                "Validated: required module files, resource naming, typed variables, module boundaries and domain layout."]

    lines: List[str] = []
    for finding in items:
        rule = " (`{}`)".format(finding["rule_id"]) if finding.get("rule_id") else ""
        lines += ["⚠️ **{}**{}".format(finding["title"], rule), "", finding["evidence"], ""]
        if finding.get("expected"):
            lines += ["Expected:", "`{}`".format(finding["expected"]), ""]
        lines += ["Detected:", "`{}`".format(_location(finding)), ""]
    return _without_trailing_blank(lines)


def _contract(findings: List[Dict[str, Any]], rules_evaluated: Any) -> List[str]:
    """How many rules were evaluated and how many were violated."""
    violations = [finding for finding in findings if finding.get("rule_id")]
    if violations:
        plural = "" if len(violations) == 1 else "s"
        lines = ["❌ **{} contract violation{} detected.**".format(len(violations), plural), ""]
    else:
        lines = ["✅ **No contract violations detected.**", ""]
    if rules_evaluated is not None:
        lines.append("**Rules evaluated:** {}  ".format(rules_evaluated))
    lines.append("**Violations:** {}".format(len(violations)))
    return lines


def _other_findings(findings: List[Dict[str, Any]]) -> List[str]:
    """The details of the findings that are neither governance nor module standard (plan, cost, networking...)."""
    lines: List[str] = []
    for finding in findings:
        if finding["category"] in STANDARD_CATEGORIES or finding["category"] == "GOVERNANCE":
            continue
        rule = " `{}`".format(finding["rule_id"]) if finding.get("rule_id") else ""
        lines.append("{} **{} / {}**{} — {} (`{}`)".format(
            ICON.get(finding["severity"], ""), finding["severity"], finding["category"], rule, finding["title"], _location(finding)))
        lines.append("  - {}".format(finding["evidence"]))
        lines.append("  - Fix: {}".format(finding["recommendation"]))
    return lines


def _findings(findings: List[Dict[str, Any]]) -> List[str]:
    """The number of findings per severity, then the details of the ones not shown above."""
    rows = ["| Severity | Findings |", "|---|---:|"]
    for severity, label in SEVERITY_ROWS:
        count = sum(1 for finding in findings if finding["severity"] == severity)
        rows.append("| {} | {} |".format(label, count))
    details = _other_findings(findings)
    return rows + (["", "### Details", ""] + details if details else [])


def _decision(review: Dict[str, Any]) -> List[str]:
    """The verdict and, when it blocks, the reasons."""
    reasons = review.get("decision_reasons") or []
    lines = ["**{}**".format(review["decision"]), ""]
    if reasons:
        lines += ["The deterministic review found blocking issues:", ""] + ["- {}".format(reason) for reason in reasons]
    else:
        lines.append("The deterministic review found no blocking violations.")
    return lines + ["", "*This reviewer does not approve, merge, or apply infrastructure.*"]


def _target(target: Any) -> str:
    """The environment this change lands on (a line of the header); says so when the target branch is unknown (a local run)."""
    if not target:
        return "**Environment:** unknown (no target branch given)  "
    if target.get("account"):
        account = " · AWS account `{}`".format(target["account"])
    else:
        account = " · AWS account not configured in `common.yaml`"
    return "**Environment:** `{}` ({}){}  ".format(target["branch"], target["environment"], account)


# ----------------------------------------------------------------------------------------------------------------
# The whole comment
# ----------------------------------------------------------------------------------------------------------------
def render_markdown(review: Dict[str, Any]) -> str:
    """Build the whole PR comment from a review result: header, the AI summary, then the evidence sections."""
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

    lines = [
        MARKER, "# Infrastructure Review", "",
        "**Risk:** {} · **Decision:** {}  ".format(review["risk"], review["decision"]),
        _target(review.get("target")),
        "*This reviewer cannot approve, merge, or apply infrastructure.*", "", "---", "",
    ]
    for index, section in enumerate(sections):
        lines += section
        if index < len(sections) - 1:
            lines += ["", "---", ""]            # a horizontal rule between sections
    return "\n".join(lines) + "\n"
