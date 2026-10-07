"""terra-review: coordinates one review and decides, deterministically, PASS or REQUEST_CHANGES.

    PYTHONPATH=tools python -m reviewer.engine review --base origin/main --markdown review.md
    PYTHONPATH=tools python -m reviewer.engine check --all
    PYTHONPATH=tools python -m reviewer.engine discover --base origin/main --format matrix
    PYTHONPATH=tools python -m reviewer.engine plan-summary --plan raw.json --out summary.json

The verdict is computed from the findings of `checks.py` (contract + terraform plan + Infracost) and from the results of the
external tools (terraform, TFLint, Checkov) before the optional AI step is even considered. The AI layer is imported only
after that, and nothing it returns can change the verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from . import checks as checks_mod
from .cost import load_infracost
from .model import Finding, severity_rank
from .plan import load_plan
from .report import render_markdown
from .repo import Repo, git_changed_files, glob_match, slug

RULES_PATH = Path(__file__).resolve().parent / "rules.yaml"


# ----------------------------------------------------------------------------------------------------------------
# Rules and checks
# ----------------------------------------------------------------------------------------------------------------
def load_rules(path: Optional[Path] = None) -> List[dict]:
    """Read rules.yaml, the single contract that checks.py implements."""
    with open(path or RULES_PATH, encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("rules", [])


def run_checks(repo: Repo, rules: List[dict], changed: Optional[List[str]] = None) -> List[Finding]:
    """Run every contract rule. When `changed` is given, keep findings located in changed files or in a folder that
    contains a changed file (contract checks are module-scoped)."""
    index = {r["id"]: r for r in rules}
    findings: List[Finding] = []
    for rule in rules:
        fn = checks_mod.REGISTRY.get(rule.get("check", ""))
        if fn is not None:
            findings.extend(fn(repo, dict(rule, _rules=index)))
    if changed is not None:
        touched_dirs = {os.path.dirname(c) for c in changed}
        findings = [f for f in findings if f.file in changed or (f.file and os.path.dirname(f.file) in touched_dirs)]
    findings.sort(key=lambda f: (f.file or "", f.line or 0, f.rule_id or ""))
    return findings


def run_all(
    repo: Repo,
    rules: List[dict],
    changed: Optional[List[str]] = None,
    plans: Optional[Dict[str, Dict[str, Any]]] = None,
    costs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Finding]:
    """Contract checks on the code plus checks on the terraform plan and the cost estimate."""
    findings = run_checks(repo, rules, changed)
    findings.extend(checks_mod.run_plan_checks(plans or {}, costs or {}, rules, repo.is_protected))
    return findings


# ----------------------------------------------------------------------------------------------------------------
# The verdict
# ----------------------------------------------------------------------------------------------------------------
def max_severity(findings: List[Finding]) -> str:
    """Highest severity among the findings; INFO when there are none."""
    return min((f.severity for f in findings), key=severity_rank) if findings else "INFO"


def decide(findings: List[Finding], checks: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """PASS or REQUEST_CHANGES, from evidence produced by code only. A model never takes part in this function.

    REQUEST_CHANGES when a confirmed finding is HIGH or worse, or when any external check (terraform, TFLint, Checkov,
    the repository contract) failed. Everything else is PASS; lower severities are still listed in the comment."""
    blocking = [f for f in findings if f.type == "CONFIRMED" and severity_rank(f.severity) <= severity_rank("HIGH")]
    failed = sorted(name for name, status in (checks or {}).items() if status == "failure")
    reasons: List[str] = []
    if blocking:
        reasons.append("blocking findings: " + ", ".join(sorted({f.rule_id or f.title for f in blocking})))
    if failed:
        reasons.append("failed checks: " + ", ".join(failed))
    return {"decision": "REQUEST_CHANGES" if reasons else "PASS", "reasons": reasons}


# ----------------------------------------------------------------------------------------------------------------
# Discovery: which root configurations a change touches (the workflows run terraform only for these)
# ----------------------------------------------------------------------------------------------------------------
def for_branch(repo: Repo, found: List[Dict[str, Any]], branch: Optional[str]) -> List[Dict[str, Any]]:
    """Keep the roots that terraform.deploy in common.yaml lists for `branch` (no entry for the branch = all of them)."""
    patterns = (repo.cfg["deploy"] or {}).get(branch) if branch else None
    if patterns is None:
        return found
    return [a for a in found if any(glob_match(g, a["root"]) for g in patterns)]


def discover(repo: Repo, changed: Optional[List[str]], branch: Optional[str] = None) -> List[Dict[str, Any]]:
    """Root configurations to act on. `changed=None` means all of them. With `branch`, only the roots that branch owns
    (terraform.deploy): a PR into develop must not plan or apply the production roots. No folder name is assumed anywhere."""
    found = repo.affected(changed) if changed is not None else [{"root": r, "reasons": ["all configurations requested"]} for r in repo.roots()]
    return [{"root": a["root"], "slug": slug(a["root"]), "reasons": a["reasons"]} for a in for_branch(repo, found, branch)]


# ----------------------------------------------------------------------------------------------------------------
# One review
# ----------------------------------------------------------------------------------------------------------------
def target_of(repo: Repo, branch: Optional[str], production: bool) -> Optional[Dict[str, Any]]:
    """Where this change lands: the target branch, whether it is production and the AWS account of that branch's keys
    (terraform.accounts in common.yaml; main uses its own account, every other branch uses develop's, as the pipeline does)."""
    if not branch:
        return None
    account = str((repo.cfg["accounts"] or {}).get("main" if branch == "main" else "develop") or "")
    placeholder = account.startswith("<") or not account
    return {
        "branch": branch,
        "environment": "production" if production else "non-production",
        "account": None if placeholder else "****" + account[-4:],
    }


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
) -> Dict[str, Any]:
    """One complete review: affected roots, findings, the deterministic verdict and the optional AI summary.
    Returns the dict that the report and the JSON output are built from."""
    plans, costs, checks = plans or {}, costs or {}, checks or {}
    repo, rules = Repo(root), load_rules()
    if production:  # the PR targets the production branch: every configuration in it is protected
        repo.cfg["protected"] = ["**"]
    target = target_of(repo, branch, production)
    affected = for_branch(repo, repo.affected([c["path"] for c in changed]) if changed else [{"root": r, "reasons": ["whole repository reviewed"]} for r in repo.roots()], branch)

    # 1. the authority: findings, risk, verdict
    findings = run_all(repo, rules, [c["path"] for c in changed] if changed else None, plans, costs)
    findings.sort(key=lambda f: (severity_rank(f.severity), f.file or "", f.line or 0))
    verdict = decide(findings, checks)
    risk = max_severity(findings)

    # 2. optional AI interpretation; every failure mode degrades to "not executed", the verdict is already final
    analysis: Optional[Dict[str, Any]] = None
    status: Dict[str, Any] = {"requested": use_ai, "executed": False, "reason": "AI review is disabled", "model": None}
    if use_ai:
        from .ai import reviewer as ai_reviewer
        from .ai.client import AIError, client_from_env

        client = ai_client or client_from_env(model)
        if client is None:
            status["reason"] = "GEMINI_API_KEY is not set"
        else:
            try:
                analysis = ai_reviewer.review(client, root, changed, findings, plans, costs, checks, pr, rules, affected, {"risk": risk, "decision": verdict["decision"], "reasons": verdict["reasons"], "target": target})
                status = {"requested": True, "executed": True, "reason": None, "model": getattr(client, "model", None)}
            except AIError as e:
                status["reason"] = "The AI step failed and was skipped: {}".format(str(e)[:200])

    return {
        "risk": risk,
        "decision": verdict["decision"],
        "decision_reasons": verdict["reasons"],
        "findings": [f.to_dict() for f in findings],
        "ai_analysis": analysis,
        "ai_status": status,
        "target": target,
        "affected": affected,
        "changed_files": [{"path": c["path"], "status": c.get("status", "modified")} for c in changed],
        "rules_evaluated": len(rules),
        "plans": plans,
        "costs": costs,
        "checks": checks,
    }


# ----------------------------------------------------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------------------------------------------------
def parse_pairs(values: Optional[List[str]], default_key: str = "default") -> Dict[str, str]:
    """`dev=plan-dev.json` -> {"dev": "plan-dev.json"}; a bare value gets `default_key`."""
    out: Dict[str, str] = {}
    for v in values or []:
        key, sep, val = v.partition("=")
        out[key.strip() if sep else default_key] = val.strip() if sep else v
    return out


def ai_requested(args: argparse.Namespace, root: str) -> bool:
    """--no-ai wins, then --ai, then `ai.enabled` in common.yaml. The default is off."""
    if getattr(args, "no_ai", False):
        return False
    if getattr(args, "ai", False):
        return True
    path = os.path.join(root, "common.yaml")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return bool(((yaml.safe_load(fh) or {}).get("ai") or {}).get("enabled", False))
    return False


def _changed(args: argparse.Namespace) -> List[Dict[str, str]]:
    """The files to review: those changed since --base, or every Terraform file when no base is given."""
    if args.base:
        return git_changed_files(args.root, args.base)
    return [{"status": "modified", "path": p} for p in Repo(args.root).tf_files]


def main(argv: Optional[List[str]] = None) -> int:
    """Command line: check, review, discover and plan-summary."""
    ap = argparse.ArgumentParser(prog="terra-review", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="run the organisation's contract checks on the code")
    c.add_argument("--root", default=".")
    c.add_argument("--base", help="only findings in files changed since this git ref")
    c.add_argument("--all", action="store_true", help="report on the whole repository, not only changed files")
    c.add_argument("--format", choices=["text", "json"], default="text")

    r = sub.add_parser("review", help="deterministic review (the authority) plus the optional AI analysis")
    r.add_argument("--root", default=".")
    r.add_argument("--base", help="git base ref; review files changed in base...HEAD")
    r.add_argument("--plan", action="append", metavar="ROOT=FILE", help="plan summary (or raw `terraform show -json`) of a root configuration")
    r.add_argument("--infracost", action="append", metavar="ROOT=FILE", help="infracost JSON of a root configuration")
    r.add_argument("--check", action="append", metavar="NAME=STATUS", help="result of a CI check (success|failure|skipped|cancelled)")
    r.add_argument("--pr-title", help="pull request title (the author's stated intent)")
    r.add_argument("--pr-body", help="pull request description")
    g = r.add_mutually_exclusive_group()
    g.add_argument("--ai", action="store_true", help="run the optional AI analysis (needs GEMINI_API_KEY); overrides common.yaml")
    g.add_argument("--no-ai", action="store_true", help="never run the AI analysis; overrides common.yaml")
    r.add_argument("--branch", help="target branch of the PR: only the configurations terraform.deploy lists for it are reported")
    r.add_argument("--production", action="store_true", help="the PR targets the production branch: destroying stateful resources is CRITICAL everywhere")
    r.add_argument("--model", help="Gemini model (default: $GEMINI_MODEL)")
    r.add_argument("--print-ai-payload", action="store_true", help="print exactly what the AI step would be sent (sanitized) and exit")
    r.add_argument("--out", help="write the JSON review here")
    r.add_argument("--markdown", help="write the PR-comment markdown here")

    d = sub.add_parser("discover", help="list the Terraform root configurations affected by a change (what the workflows run)")
    d.add_argument("--root", default=".")
    sel = d.add_mutually_exclusive_group(required=True)
    sel.add_argument("--base", help="git ref (or SHA); configurations affected by the changes since it")
    sel.add_argument("--all", action="store_true", help="every configuration")
    d.add_argument("--format", choices=["json", "matrix", "text"], default="json", help="matrix = {\"include\": [...]} for a GitHub Actions strategy")
    d.add_argument("--branch", help="keep only the roots that terraform.deploy in common.yaml lists for this branch (no entry = all)")
    d.add_argument("--modules", action="store_true", help="list the shared modules affected (one path per line) instead of the root configurations")

    ps = sub.add_parser("plan-summary", help="reduce a raw `terraform show -json` file to a sanitized summary (safe to share)")
    ps.add_argument("--plan", required=True)
    ps.add_argument("--out", required=True)

    args = ap.parse_args(argv)

    if args.cmd == "plan-summary":
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(load_plan(args.plan), fh, indent=1)
        return 0

    root = os.path.abspath(args.root)

    if args.cmd == "discover":
        repo = Repo(root)
        if args.modules:
            mods = repo.module_dirs() if args.all else repo.affected_modules([c["path"] for c in git_changed_files(root, args.base)])
            print("\n".join(mods))
            return 0
        found = discover(repo, None if args.all else [c["path"] for c in git_changed_files(root, args.base)], args.branch)
        if args.format == "matrix":
            print(json.dumps({"include": [{k: v for k, v in a.items() if k != "reasons"} for a in found]}))
        elif args.format == "text":
            for a in found:
                print("{}  ({})".format(a["root"], "; ".join(a["reasons"][:3])))
        else:
            print(json.dumps(found, indent=2))
        return 0

    if args.cmd == "check":
        repo = Repo(root)
        changed = None if args.all or not args.base else [c["path"] for c in git_changed_files(root, args.base)]
        findings = run_checks(repo, load_rules(), changed)
        if args.format == "json":
            print(json.dumps([f.to_dict() for f in findings], indent=2))
        else:
            for f in findings:
                print("{:<8} {:<8} {}:{}  {}".format(f.severity, f.rule_id, f.file, f.line or "-", f.evidence))
            print("{} finding(s)".format(len(findings)))
        return 1 if any(f.severity in ("CRITICAL", "HIGH") for f in findings) else 0

    plans = {env: load_plan(p) for env, p in parse_pairs(args.plan, "plan").items() if os.path.isfile(p)}
    costs = {env: load_infracost(p) for env, p in parse_pairs(args.infracost, "plan").items() if os.path.isfile(p)}
    checks = parse_pairs(args.check)
    pr = {"title": args.pr_title or "", "body": args.pr_body or ""}
    changed = _changed(args)

    if args.print_ai_payload:
        from .ai import reviewer as ai_reviewer

        rules = load_rules()
        findings = run_all(Repo(root), rules, [c["path"] for c in changed], plans, costs)
        evidence = ai_reviewer.build_evidence(root, changed, findings, plans, costs, checks, pr)
        repo = Repo(root)
        affected = for_branch(repo, repo.affected([c["path"] for c in changed]), args.branch)
        verdict = decide(findings, checks)
        verdict = {"risk": max_severity(findings), "decision": verdict["decision"], "reasons": verdict["reasons"], "target": target_of(repo, args.branch, args.production)}
        print(json.dumps(ai_reviewer.build_payload(root, evidence, rules, affected, verdict), indent=2))
        return 0

    result = review(root, changed, plans, costs, checks, pr, use_ai=ai_requested(args, root), model=args.model, production=args.production, branch=args.branch)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    else:
        print(json.dumps(result, indent=2))
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(render_markdown(result))
    # The exit code is the deterministic verdict, so a workflow can choose to gate on it.
    return 1 if result["decision"] == "REQUEST_CHANGES" else 0


if __name__ == "__main__":
    sys.exit(main())
