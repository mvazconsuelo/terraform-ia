"""Run a full review from your own machine, without GitHub: the same review the PR gets, with the plan, cost and checks you give it."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

from .git_diff import git_changed_files
from ..infracost.read_infracost_json import load_infracost
from ..review.markdown_report import render_markdown
from ..review.run_review import ai_requested, decide, load_rules, max_severity, review, run_all, target_of
from ..terraform.affected_roots import for_branch
from ..terraform.read_plan_json import load_plan
from ..terraform.terraform_map import Repo


def _parse_pairs(values: Optional[List[str]], default_key: str = "default") -> Dict[str, str]:
    """`environments/dev=plan.json` -> {"environments/dev": "plan.json"}; a bare value gets `default_key`."""
    pairs: Dict[str, str] = {}
    for value in values or []:
        key, separator, item = value.partition("=")
        pairs[key.strip() if separator else default_key] = item.strip() if separator else value
    return pairs


def _files_to_review(root: str, base: Optional[str]) -> List[Dict[str, str]]:
    """The files to review: those changed since `base`, or every Terraform file when no base is given."""
    if base:
        return git_changed_files(root, base)
    return [{"status": "modified", "path": path} for path in Repo(root).tf_files]


def _print_ai_payload(root: str, args: argparse.Namespace, changed, plans, costs, checks, pr) -> None:
    """Print exactly what the AI step would be sent (sanitized). Nothing is sent anywhere."""
    from ..ai import summary as ai_summary

    rules = load_rules()
    repo = Repo(root)
    changed_paths = [change["path"] for change in changed]
    findings = run_all(repo, rules, changed_paths, plans, costs)
    evidence = ai_summary.build_evidence(root, changed, findings, plans, costs, checks, pr)
    affected = for_branch(repo, repo.affected(changed_paths), args.branch)

    verdict = decide(findings, checks)
    verdict_summary = {
        "risk": max_severity(findings), "decision": verdict["decision"], "reasons": verdict["reasons"],
        "target": target_of(repo, args.branch, args.production),
    }
    print(json.dumps(ai_summary.build_payload(root, evidence, rules, affected, verdict_summary), indent=2))


def local_review(root: str, args: argparse.Namespace) -> int:
    """Review a change. Returns 1 when the verdict is REQUEST_CHANGES, so a script can gate on it."""
    plans = {name: load_plan(path) for name, path in _parse_pairs(args.plan, "plan").items() if os.path.isfile(path)}
    costs = {name: load_infracost(path) for name, path in _parse_pairs(args.infracost, "plan").items() if os.path.isfile(path)}
    checks = _parse_pairs(args.check)
    pr = {"title": args.pr_title or "", "body": args.pr_body or ""}
    changed = _files_to_review(root, args.base)

    if args.print_ai_payload:
        _print_ai_payload(root, args, changed, plans, costs, checks, pr)
        return 0

    result = review(
        root, changed, plans, costs, checks, pr,
        use_ai=ai_requested(args, root), model=args.model, production=args.production, branch=args.branch,
    )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
    else:
        print(json.dumps(result, indent=2))
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as handle:
            handle.write(render_markdown(result))
    return 1 if result["decision"] == "REQUEST_CHANGES" else 0


def main(argv: Optional[List[str]] = None) -> int:
    """`python -m reviewer.ci.local_review --base origin/develop --branch develop --no-ai --markdown review.md`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--base", help="git base ref; review the files changed in base...HEAD")
    parser.add_argument("--plan", action="append", metavar="ROOT=FILE", help="plan (a raw `terraform show -json` or a summary) of a root")
    parser.add_argument("--infracost", action="append", metavar="ROOT=FILE", help="infracost JSON of a root")
    parser.add_argument("--check", action="append", metavar="NAME=STATUS", help="result of a CI check (success|failure|skipped|warning)")
    parser.add_argument("--pr-title", help="pull request title (the author's stated intent)")
    parser.add_argument("--pr-body", help="pull request description")
    ai = parser.add_mutually_exclusive_group()
    ai.add_argument("--ai", action="store_true", help="run the AI summary (needs GEMINI_API_KEY); overrides common.yaml")
    ai.add_argument("--no-ai", action="store_true", help="never run the AI summary; overrides common.yaml")
    parser.add_argument("--branch", help="target branch of the PR: only the roots terraform.deploy lists for it are reported")
    parser.add_argument("--production", action="store_true", help="the PR targets production: destroying stateful resources is CRITICAL everywhere")
    parser.add_argument("--model", help="Gemini model (default: $GEMINI_MODEL)")
    parser.add_argument("--print-ai-payload", action="store_true", help="print exactly what the AI step would be sent (sanitized) and exit")
    parser.add_argument("--out", help="write the JSON review here")
    parser.add_argument("--markdown", help="write the PR-comment markdown here")
    args = parser.parse_args(argv)
    return local_review(os.path.abspath(args.root), args)


if __name__ == "__main__":
    sys.exit(main())
