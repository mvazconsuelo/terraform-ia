"""One review: run the checks, compute the verdict, optionally ask the AI to summarise.

The order matters:

  1. the CHECKS produce findings (contract checks on the code, plan checks on the plan and the cost);
  2. the VERDICT (PASS or REQUEST_CHANGES) is computed from those findings and from the results of the external tools
     (terraform, TFLint, Checkov);
  3. only then, and only if enabled, the AI is asked to summarise. It is imported after the verdict is final and nothing
     it returns can change the verdict.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

# Importing a checks module registers its checks (see rules/registry.py); the names are not used otherwise.
from ..rules import code_rules as _code_rules  # noqa: F401
from ..rules import inputs_rules as _inputs_rules  # noqa: F401
from ..rules import plan_rules as _plan_rules  # noqa: F401
from ..rules import registry
from ..terraform.affected_roots import for_branch
from ..terraform.terraform_map import Repo
from .finding import Finding, severity_rank

RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.yaml"


def load_rules(path: Optional[Path] = None) -> List[dict]:
    """Read rules.yaml, the single contract that the checks implement."""
    with open(path or RULES_PATH, encoding="utf-8") as handle:
        return (yaml.safe_load(handle) or {}).get("rules", [])


# ----------------------------------------------------------------------------------------------------------------
# 1. Findings
# ----------------------------------------------------------------------------------------------------------------
def run_checks(repo: Repo, rules: List[dict], changed: Optional[List[str]] = None) -> List[Finding]:
    """Run every contract rule against the code.

    With `changed` (a list of file paths), keep only the findings that sit in a changed file or in a folder that holds a
    changed file: a PR is judged on what it touches, not on the whole repository."""
    rules_by_id = {rule["id"]: rule for rule in rules}

    findings: List[Finding] = []
    for rule in rules:
        check_name = rule.get("check", "")
        check_function = registry.REGISTRY.get(check_name)
        if check_function is not None:
            findings.extend(check_function(repo, dict(rule, _rules=rules_by_id)))
        elif check_name not in registry.PLAN_REGISTRY:
            # A rule that names a check nobody implements would be skipped without a word, and its protection would be gone.
            raise ValueError("rule {} names the check '{}', which is not implemented".format(rule.get("id"), check_name))

    if changed is not None:
        changed_folders = {os.path.dirname(path) for path in changed}
        findings = [
            finding for finding in findings
            if finding.file in changed or (finding.file and os.path.dirname(finding.file) in changed_folders)
        ]
    findings.sort(key=lambda finding: (finding.file or "", finding.line or 0, finding.rule_id or ""))
    return findings


def run_all(
    repo: Repo,
    rules: List[dict],
    changed: Optional[List[str]] = None,
    plans: Optional[Dict[str, Dict[str, Any]]] = None,
    costs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Finding]:
    """The contract checks on the code, plus the checks on the terraform plan and the cost estimate."""
    findings = run_checks(repo, rules, changed)
    findings.extend(registry.run_plan_checks(plans or {}, costs or {}, rules, repo.is_protected))
    return findings


# ----------------------------------------------------------------------------------------------------------------
# 2. The verdict
# ----------------------------------------------------------------------------------------------------------------
def max_severity(findings: List[Finding]) -> str:
    """Highest severity among the findings; INFO when there are none."""
    if not findings:
        return "INFO"
    return min((finding.severity for finding in findings), key=severity_rank)


def decide(findings: List[Finding], checks: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """PASS or REQUEST_CHANGES, from evidence produced by code only. A model never takes part in this function.

    REQUEST_CHANGES when a confirmed finding is HIGH or worse, or when any external check (terraform, TFLint, Checkov,
    the repository contract) failed. Everything else is PASS; lower severities are still listed in the comment."""
    high = severity_rank("HIGH")
    blocking_findings = [f for f in findings if f.type == "CONFIRMED" and severity_rank(f.severity) <= high]
    failed_checks = sorted(name for name, status in (checks or {}).items() if status == "failure")

    reasons: List[str] = []
    if blocking_findings:
        rule_names = sorted({finding.rule_id or finding.title for finding in blocking_findings})
        reasons.append("blocking findings: " + ", ".join(rule_names))
    if failed_checks:
        reasons.append("failed checks: " + ", ".join(failed_checks))
    return {"decision": "REQUEST_CHANGES" if reasons else "PASS", "reasons": reasons}


# ----------------------------------------------------------------------------------------------------------------
# 3. One complete review
# ----------------------------------------------------------------------------------------------------------------
def target_of(repo: Repo, branch: Optional[str], production: bool) -> Optional[Dict[str, Any]]:
    """Where this change lands: the target branch, whether that is production, and the last digits of the AWS account.

    The account comes from the environment that names the branch in `terraform.environments` (common.yaml). `main` has its own
    account; every other branch uses the develop one, exactly as the pipeline picks the keys."""
    if not branch:
        return None
    try:
        account = repo.account_of_branch("main" if branch == "main" else "develop")
    except ValueError:
        account = ""
    not_configured = not account or account.startswith("<")     # "<dev-account-id>" is the placeholder
    return {
        "branch": branch,
        "environment": "production" if production else "non-production",
        "account": None if not_configured else "****" + account[-4:],   # never show the whole id
    }


def _roots_under_review(repo: Repo, changed: List[Dict[str, str]], branch: Optional[str]) -> List[Dict[str, Any]]:
    """The roots this review is about: those the change affects, limited to what the target branch may act on.

    Without a list of changed files (a local run), every root is reviewed."""
    if changed:
        roots = repo.affected([item["path"] for item in changed])
    else:
        roots = [{"root": root, "reasons": ["whole repository reviewed"]} for root in repo.roots()]
    return for_branch(repo, roots, branch)


def _ask_ai(
    use_ai: bool, model: Optional[str], ai_client: Any, root: str, changed: List[Dict[str, str]], findings: List[Finding],
    plans: Dict[str, Any], costs: Dict[str, Any], checks: Dict[str, str], pr: Optional[Dict[str, str]],
    rules: List[dict], affected: List[Dict[str, Any]], verdict_summary: Dict[str, Any], versions: List[Dict[str, Any]],
    protected: Callable[[str], bool],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Ask the AI for the summary. Returns (summary or None, status).

    Every way this can go wrong (disabled, no key, API error, invalid answer) ends as "not executed" with the reason: the
    verdict was already decided, so a failing model never changes the result."""
    status: Dict[str, Any] = {"requested": use_ai, "executed": False, "reason": "AI review is disabled", "model": None}
    if not use_ai:
        return None, status

    # Imported here, after the verdict is final, so the decision code can never depend on the AI layer.
    from ..ai import summary as ai_summary
    from ..ai.client import AIError, client_from_env

    client = ai_client or client_from_env(model)
    if client is None:
        status["reason"] = "GEMINI_API_KEY is not set"
        return None, status
    try:
        analysis = ai_summary.review(client, root, changed, findings, plans, costs, checks, pr, rules, affected, verdict_summary, versions, protected)
    except AIError as error:
        status["reason"] = "The AI step failed and was skipped: {}".format(str(error)[:200])
        return None, status
    return analysis, {"requested": True, "executed": True, "reason": None, "model": getattr(client, "model_used", None) or getattr(client, "model", None)}


def review(
    root: str,
    changed: List[Dict[str, str]],
    plans: Optional[Dict[str, Dict[str, Any]]] = None,
    costs: Optional[Dict[str, Dict[str, Any]]] = None,
    checks: Optional[Dict[str, str]] = None,
    pr: Optional[Dict[str, str]] = None,
    use_ai: bool = False,
    model: Optional[str] = None,
    ai_client: Any = None,
    production: bool = False,
    branch: Optional[str] = None,
    versions: Optional[List[Dict[str, Any]]] = None,
    jobs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """One complete review: affected roots, findings, the deterministic verdict and the optional AI summary.

    `changed` is the list of {"path", "status"} of the files the PR changes; `plans` and `costs` are keyed by root path;
    `checks` maps the name of each CI job to its result;
    `versions` says if newer Terraform or provider releases exist (information only). Returns the dict the report and the JSON output are built from."""
    plans, costs, checks = plans or {}, costs or {}, checks or {}
    repo, rules = Repo(root), load_rules()
    repo.protected_environments = [
        str(name) for rule in rules if rule.get("check") == "plan_destroys_stateful_resource" for name in rule.get("protected_environments") or []
    ]
    repo.protect_all = production      # the PR targets the production branch: every root is treated as protected

    target = target_of(repo, branch, production)
    affected = _roots_under_review(repo, changed, branch)

    # 1. Findings, risk and verdict: the authority.
    changed_paths = [item["path"] for item in changed] if changed else None
    findings = run_all(repo, rules, changed_paths, plans, costs)
    findings.sort(key=lambda finding: (severity_rank(finding.severity), finding.file or "", finding.line or 0))
    verdict = decide(findings, checks)
    risk = max_severity(findings)

    # 2. The optional AI summary, with the verdict already final.
    verdict_summary = {"risk": risk, "decision": verdict["decision"], "reasons": verdict["reasons"], "target": target}
    analysis, ai_status = _ask_ai(
        use_ai, model, ai_client, root, changed, findings, plans, costs, checks, pr, rules, affected, verdict_summary, versions or [], repo.is_protected)

    return {
        "risk": risk,
        "decision": verdict["decision"],
        "decision_reasons": verdict["reasons"],
        "findings": [finding.to_dict() for finding in findings],
        "ai_analysis": analysis,
        "ai_status": ai_status,
        "target": target,
        "affected": affected,
        "changed_files": [{"path": item["path"], "status": item.get("status", "modified")} for item in changed],
        "rules_evaluated": len(rules),
        "plans": plans,
        "costs": costs,
        "checks": checks,
        "versions": versions or [],
        "jobs": jobs or [],
    }


def ai_enabled(root: str) -> bool:
    """Is the AI summary switched on? It is `ai.enabled` in common.yaml, and the default is off."""
    path = os.path.join(root, "common.yaml")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            ai_settings = (yaml.safe_load(handle) or {}).get("ai") or {}
        return bool(ai_settings.get("enabled", False))
    return False
