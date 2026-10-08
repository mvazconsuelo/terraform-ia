"""Builds the text of the PR comment (Markdown) from the result of a review.

The comment has eight sections, in this order:

  1. AI Gemini summary             the only text written by a model; with the AI off or failing, the rest is identical;
  2. Affected configurations       which Terraform root configurations the PR touches, and why;
  3. Checks                        the result of fmt, validate, TFLint, Checkov and the repository contract;
  4. Terraform plan                what the plan adds, changes, destroys and replaces;
  5. Cost                          the Infracost estimate;
  6. Versions                      the Terraform and provider versions in use, and whether newer ones exist (information only);
  7. Repository rules              what the rules of rules.yaml found (or that all passed), with the detail of each finding;
  8. Decision                      the verdict in one line, and what blocks it when it does.

The name of every check, and the plan of every root, link to the log of the job that ran it.

Every section except the first is produced by code from deterministic inputs. Each `_<name>_section` function below
returns the lines of one section; `render_pr_comment` joins them.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# A hidden marker on the first line: the workflow finds its own comment by it and edits it instead of adding a new one.
COMMENT_MARKER = "<!-- terra-review -->"

# How each CI job result is shown in the Checks table.
CHECK_RESULT_LABEL = {
    "success": "✅ PASS", "warning": "⚠️ FINDINGS", "failure": "❌ FAIL", "cancelled": "⏹️ CANCELLED", "skipped": "⏭️ SKIPPED",
}
SEVERITY_ORDER = [("CRITICAL", "Critical"), ("HIGH", "High"), ("MEDIUM", "Medium"), ("LOW", "Low"), ("INFO", "Informational")]
SEVERITY_ICON = {"CRITICAL": "🛑", "HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡", "INFO": "🔵"}
MAX_LIST_ENTRIES = 50      # long lists are cut after this many entries
MAX_COST_ROWS = 8          # rows of the cost table, for priced and for usage-based resources


# ----------------------------------------------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------------------------------------------
def _format_money(amount: Any, signed: bool = False) -> str:
    """A dollar amount with two decimals; `signed` forces a leading + or -. None (unknown) shows as n/a."""
    if amount is None:
        return "n/a"
    text = "${:,.2f}".format(abs(amount))
    if signed:
        return ("+" if amount >= 0 else "-") + text
    return ("-" if amount < 0 else "") + text


def _format_location(finding: Dict[str, Any]) -> str:
    """`file:line` of a finding."""
    if not finding.get("file"):
        return "no file"
    if finding.get("line"):
        return "{}:{}".format(finding["file"], finding["line"])
    return str(finding["file"])


def _limit_list(lines: List[str]) -> List[str]:
    """Keep the first MAX_LIST_ENTRIES lines and say how many were left out."""
    if len(lines) <= MAX_LIST_ENTRIES:
        return lines
    return lines[:MAX_LIST_ENTRIES] + ["... and {} more".format(len(lines) - MAX_LIST_ENTRIES)]


def _format_forcing_attributes(paths: List[Any]) -> str:
    """The attributes that force a replacement, e.g. `kms_key_id, engine_version`."""
    names = [".".join(str(part) for part in path) if isinstance(path, list) else str(path) for path in paths]
    return ", ".join(names)


def _job_url(jobs: List[Dict[str, Any]], name: str) -> Optional[str]:
    """The link to the log of the job called `name`, or None. A check name may carry a suffix (`Checkov (2 findings...)`)."""
    for job in jobs:
        if job["name"] == name or name.startswith(job["name"] + " ("):
            return str(job["url"])
    return None


def _link(text: str, url: Optional[str]) -> str:
    """`text` as a Markdown link when there is a url, plain otherwise."""
    return "[{}]({})".format(text, url) if url else text


def _without_trailing_blank(lines: List[str]) -> List[str]:
    """Drop the blank line most sections leave at the end, so the separators between sections are even."""
    return lines[:-1] if lines and lines[-1] == "" else lines


# ----------------------------------------------------------------------------------------------------------------
# 1. AI Gemini summary
# ----------------------------------------------------------------------------------------------------------------
def _ai_summary_section(review: Dict[str, Any]) -> List[str]:
    """The AI summary, or the reason it is missing (disabled, or it failed)."""
    lines = ["## AI Gemini summary", ""]
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
# 2. Affected configurations
# ----------------------------------------------------------------------------------------------------------------
def _affected_configurations_section(affected: List[Dict[str, Any]], changed: List[Dict[str, Any]]) -> List[str]:
    """The affected root configurations, with the files changed in each and, for the rest, why it was affected."""
    lines = ["## Affected Terraform configurations", ""]
    if not affected:
        return lines + ["_No Terraform configuration is affected by this change; Terraform was not run._"]

    changed_paths = [item["path"] for item in changed]
    for item in affected:
        root = item["root"]
        files_in_root = [path for path in changed_paths if path.startswith(root + "/")]
        names_in_root = sorted(path[len(root) + 1:] for path in files_in_root)            # shown relative to the root
        reasons_already_shown = {"{} changed".format(path) for path in files_in_root}
        other_reasons = [reason for reason in item["reasons"] if reason not in reasons_already_shown]

        lines += ["### `{}`".format(root), ""]
        if names_in_root:
            lines += ["Changed configuration:", ""] + ["- `{}`".format(name) for name in _limit_list(names_in_root)] + [""]
        if other_reasons:
            lines += ["Affected through:", ""] + ["- {}".format(reason) for reason in other_reasons[:5]] + [""]
    return _without_trailing_blank(lines)


# ----------------------------------------------------------------------------------------------------------------
# 3. Checks
# ----------------------------------------------------------------------------------------------------------------
def _checks_section(checks: Dict[str, str], jobs: List[Dict[str, Any]]) -> List[str]:
    """The table of CI job results (each name links to its job) and a one-line count: how many passed, had findings, or were skipped."""
    lines = ["## Checks", ""]
    if not checks:
        return lines + ["_No check results were provided._"]

    rows = ["| Check | Result |", "|---|---|"]
    for name, status in checks.items():
        label = CHECK_RESULT_LABEL.get(status, "❔ " + str(status).upper())
        rows.append("| {} | {} |".format(_link(name[:1].upper() + name[1:], _job_url(jobs, name)), label))

    ran = [status for status in checks.values() if status != "skipped"]
    passed = sum(1 for status in ran if status == "success")
    with_findings = sum(1 for status in ran if status == "warning")
    skipped = len(checks) - len(ran)

    summary = "**Result:** {}/{} checks passed.".format(passed, len(ran)) if ran else "**Result:** no check ran."
    if with_findings:
        summary += " {} with findings that do not block.".format(with_findings)
    if skipped:
        summary += " {} skipped.".format(skipped)
    return lines + rows + ["", summary]


# ----------------------------------------------------------------------------------------------------------------
# 4. Terraform plan
# ----------------------------------------------------------------------------------------------------------------
def _split_resources_by_action(plan: Dict[str, Any]) -> Tuple[List[str], List[str], List[str], List[Dict[str, Any]]]:
    """The resources in a plan, as (addresses to add, to change, to destroy, and the changes that replace a resource)."""
    changes = plan.get("resource_changes", [])
    to_add = [change["address"] for change in changes if change.get("actions") == ["create"]]
    to_change = [change["address"] for change in changes if change.get("actions") == ["update"]]
    to_destroy = [change["address"] for change in changes if change.get("actions") == ["delete"]]
    to_replace = [change for change in changes if change.get("replace")]
    return to_add, to_change, to_destroy, to_replace


def _describe_replacement(change: Dict[str, Any]) -> str:
    """One replaced resource and, when known, the attributes that force the replacement."""
    forcing = change.get("replace_paths") or []
    forced_by = "  (forced by: {})".format(_format_forcing_attributes(forcing)) if forcing else ""
    return "-/+ {}{}".format(change["address"], forced_by)


def _terraform_plan_section(plans: Dict[str, dict], jobs: List[Dict[str, Any]]) -> List[str]:
    """For each root: the counts, and the resources to add, change, destroy and replace (with what forces the replacement)."""
    lines = ["## Terraform plan", ""]
    if not plans:
        return lines + ["_No Terraform plan was available._"]

    several_roots = len(plans) > 1
    sub_heading = "####" if several_roots else "###"
    for root, plan in sorted(plans.items()):
        to_add, to_change, to_destroy, to_replace = _split_resources_by_action(plan)
        if several_roots:
            lines += ["### `{}`".format(root), ""]

        counts = "{} to add · {} to change · {} to destroy".format(len(to_add), len(to_change), len(to_destroy))
        if to_replace:
            counts += " · {} to replace".format(len(to_replace))
        job_url = _job_url(jobs, "plan {0} / {0}".format(root))
        lines += ["**Plan:** `{}`".format(counts) + ("  ·  {}".format(_link("job log", job_url)) if job_url else ""), ""]

        groups = (
            ("Resources to add", ["+ " + address for address in to_add]),
            ("Resources to change", ["~ " + address for address in to_change]),
            ("Resources to destroy", ["- " + address for address in to_destroy]),
            ("Resources to replace", [_describe_replacement(change) for change in to_replace]),
        )
        for title, entries in groups:
            if title == "Resources to replace" and not entries:
                continue                                  # the replace list only appears when something is replaced
            lines += ["{} {}".format(sub_heading, title), "", "```text"] + (_limit_list(entries) if entries else ["None"]) + ["```", ""]
        if to_replace:
            lines += ["A replacement destroys the resource and creates a new one; for stateful resources that means data loss or downtime.", ""]
    return _without_trailing_blank(lines)


# ----------------------------------------------------------------------------------------------------------------
# 5. Cost
# ----------------------------------------------------------------------------------------------------------------
def _cost_table(cost: Dict[str, Any], resources: List[Dict[str, Any]]) -> List[str]:
    """The resource table: the priced ones, a row for the rest, the usage-based ones, and the total.

    It is built so the rows add up to the total shown at the bottom."""
    priced = [resource for resource in resources if resource.get("monthly_cost")]
    usage_based = [resource for resource in resources if not resource.get("monthly_cost")]    # no fixed monthly price
    proposed = cost.get("proposed_monthly_cost")

    shown = priced[:MAX_COST_ROWS]
    rows = ["| Resource | Monthly cost |", "|---|---:|"]
    rows += ["| `{}` | {} |".format(resource["resource"], _format_money(resource["monthly_cost"])) for resource in shown]
    if proposed is not None:
        not_shown = proposed - sum(resource["monthly_cost"] for resource in shown)
        if not_shown > 0.005:
            rows.append("| Other priced resources | {} |".format(_format_money(not_shown)))
    rows += ["| `{}` | usage-based, not estimated |".format(resource["resource"]) for resource in usage_based[:MAX_COST_ROWS]]
    if len(usage_based) > MAX_COST_ROWS:
        rows.append("| _... and {} more usage-based_ | |".format(len(usage_based) - MAX_COST_ROWS))
    if proposed is not None:
        rows.append("| **Total (proposed)** | **{}** |".format(_format_money(proposed)))
    return rows + [""]


def _unpriced_resources_note(cost: Dict[str, Any]) -> List[str]:
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


def _cost_of_one_root(root: str, cost: Dict[str, Any], several_roots: bool) -> List[str]:
    """The cost of one root: monthly change, resource table, unpriced resources and annualized impact. Ends with a blank line."""
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
        lines += ["**Estimated monthly change{}: {}**".format(" (priced resources only)" if partial else "", _format_money(delta, True)), ""]
    current, proposed = _format_money(cost.get("current_monthly_cost")), _format_money(cost.get("proposed_monthly_cost"))
    lines += ["Current {}/month → proposed {}/month.".format(current, proposed), ""]
    if resources:
        lines += _cost_table(cost, resources)
    lines += _unpriced_resources_note(cost)
    if delta is not None:
        # Computed from the rounded monthly figure printed above, so the two numbers always agree (69.72 x 12 = 836.64).
        lines += ["**Annualized impact:** {}".format(_format_money(round(delta, 2) * 12, True)), ""]
    return lines


def _cost_section(costs: Dict[str, dict]) -> List[str]:
    """The cost estimate of each root."""
    lines = ["## Cost", ""]
    if not costs:
        return lines + ["_No cost estimate was available._"]
    for root, cost in sorted(costs.items()):
        lines += _cost_of_one_root(root, cost, several_roots=len(costs) > 1)
    return _without_trailing_blank(lines)


# ----------------------------------------------------------------------------------------------------------------
# 6. Versions
# ----------------------------------------------------------------------------------------------------------------
UPDATE_LABEL = {"patch": "⬆️ patch update", "minor": "⬆️ minor update", "major": "⚠️ major update (may include breaking changes)"}


def _versions_section(versions: List[Dict[str, Any]]) -> List[str]:
    """The Terraform and provider versions the plan used, whether newer ones exist, and where to read what changed."""
    lines = ["## Versions", ""]
    if not versions:
        return lines + ["_No version information was available._"]

    rows = ["| Component | In use | Latest | Status | What changed |", "|---|---|---|---|---|"]
    for item in versions:
        if item["latest"] is None:
            status, latest, changes = "❔ could not check", "n/a", "—"
        elif item["update"]:
            status, latest, changes = UPDATE_LABEL[item["update"]], item["latest"], "[release notes]({})".format(item["url"])
        else:
            status, latest, changes = "✅ up to date", item["latest"], "—"
        rows.append("| {} | {} | {} | {} | {} |".format(item["name"], item["in_use"], latest, status, changes))
    return lines + rows + ["", "_Information only: it does not change the decision._"]


# ----------------------------------------------------------------------------------------------------------------
# 7. Repository rules
# ----------------------------------------------------------------------------------------------------------------
def _describe_finding(finding: Dict[str, Any]) -> List[str]:
    """One finding: severity and rule, what is wrong (with where), the evidence and how to fix it."""
    rule = " `{}`".format(finding["rule_id"]) if finding.get("rule_id") else ""
    lines = ["{} **{} / {}**{} — {} (`{}`)".format(
        SEVERITY_ICON.get(finding["severity"], ""), finding["severity"], finding["category"], rule, finding["title"], _format_location(finding))]
    lines.append("  - {}".format(finding["evidence"]))
    if finding.get("expected"):
        lines.append("  - Expected: `{}`".format(finding["expected"]))
    lines.append("  - Fix: {}".format(finding["recommendation"]))
    return lines


def _repository_rules_section(findings: List[Dict[str, Any]], rules_evaluated: Any) -> List[str]:
    """What the repository's own rules found: all passed, or how many were violated, by severity, with the detail of each finding.

    Checkov and TFLint report their own findings in the Checks table; this section is only about the rules of `rules.yaml`."""
    lines = ["## Repository rules", ""]
    total = "all {}".format(rules_evaluated) if rules_evaluated else "all"
    if not findings:
        return lines + ["✅ **{} rules passed** — module standard, mandatory tags, root layout, plan and cost.".format(total.capitalize())]

    violated = len({finding["rule_id"] for finding in findings if finding.get("rule_id")})
    of_total = " of {}".format(rules_evaluated) if rules_evaluated else ""
    lines += ["⚠️ **{}{} rules violated**".format(violated, of_total), "", "| Severity | Findings |", "|---|---:|"]
    for severity, label in SEVERITY_ORDER:
        count = sum(1 for finding in findings if finding["severity"] == severity)
        if count:
            lines.append("| {} {} | {} |".format(SEVERITY_ICON.get(severity, ""), label, count))
    lines += ["", "### Details", ""]
    for finding in findings:
        lines += _describe_finding(finding)
    return lines


# ----------------------------------------------------------------------------------------------------------------
# 8. Decision
# ----------------------------------------------------------------------------------------------------------------
def _decision_section(review: Dict[str, Any]) -> List[str]:
    """The verdict in one line: why it passes, or what blocks it; plus the warnings that do not block."""
    reasons = review.get("decision_reasons") or []
    lines = ["## Decision", ""]
    if reasons:
        lines += ["**❌ REQUEST_CHANGES** — blocked by:", ""] + ["- {}".format(reason) for reason in reasons]
    else:
        lines.append("**✅ PASS** — no High or Critical rule violation and no failed check.")
    warnings = [name for name, status in (review.get("checks") or {}).items() if status == "warning"]
    if warnings:
        lines += ["", "ℹ️ Does not block: " + ", ".join(warnings) + "."]
    return lines


# ----------------------------------------------------------------------------------------------------------------
# The whole comment
# ----------------------------------------------------------------------------------------------------------------
def _header_section(review: Dict[str, Any], jobs: List[Dict[str, Any]]) -> List[str]:
    """The top of the comment: a coloured box with the decision and the risk, then where the change lands and the run.

    The box uses GitHub's alert syntax, so it is green for PASS, red for REQUEST_CHANGES at HIGH or CRITICAL risk, and yellow for
    REQUEST_CHANGES at a lower risk."""
    decision, risk = review["decision"], review["risk"]
    if decision == "PASS":
        kind, verdict = "TIP", "✅ **PASS** — no blocking issues"
    else:
        kind = "CAUTION" if risk in ("CRITICAL", "HIGH") else "WARNING"
        verdict = "❌ **REQUEST_CHANGES** — blocking issues found"
    lines = ["> [!{}]".format(kind), "> {}  ".format(verdict), "> Risk: {} **{}**".format(SEVERITY_ICON.get(risk, ""), risk), ""]

    target = review.get("target")
    if not target:
        where, account = "unknown (no target branch given)", "—"
    else:
        where = "`{}` ({})".format(target["branch"], target["environment"])
        account = "`{}`".format(target["account"]) if target.get("account") else "not configured in `common.yaml`"
    run = "[open]({})".format(jobs[0]["url"].rsplit("/job/", 1)[0]) if jobs else "—"
    commit = review.get("commit")
    reviewed = _link("`{}`".format(commit["sha"]), commit.get("url") or None) if commit else "—"
    row = "| {} | {} | {} | {} |".format(where, account, reviewed, run)
    lines += ["| Environment | AWS account | Reviewed commit | Workflow run |", "|---|---|---|---|", row, ""]
    return lines + ["*This reviewer cannot approve, merge, or apply infrastructure.*"]


def render_pr_comment(review: Dict[str, Any]) -> str:
    """Build the whole PR comment from a review result: the header, then the eight sections."""
    plans, costs, findings = review.get("plans", {}), review.get("costs", {}), review["findings"]
    jobs = review.get("jobs", [])

    sections = [
        _ai_summary_section(review),
        _affected_configurations_section(review.get("affected", []), review.get("changed_files", [])),
        _checks_section(review.get("checks", {}), jobs),
        _terraform_plan_section(plans, jobs),
        _cost_section(costs),
        _versions_section(review.get("versions", [])),
        _repository_rules_section(findings, review.get("rules_evaluated")),
        _decision_section(review),
    ]

    lines = [COMMENT_MARKER, "# Infrastructure Review", ""] + _header_section(review, jobs) + ["", "---", ""]
    for index, section in enumerate(sections):
        lines += section
        if index < len(sections) - 1:
            lines += ["", "---", ""]            # a horizontal rule between sections
    return "\n".join(lines) + "\n"
