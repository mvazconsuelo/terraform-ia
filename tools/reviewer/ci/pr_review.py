"""The review step of the pull-request workflow: build the review and the text of the PR comment."""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from typing import Any, Dict, List, Optional, Tuple

from ..infracost.read_infracost_json import load_infracost
from ..lib.git_diff import git_changed_files
from ..lib.github_actions import append_to_github_file
from ..lib.workflow_jobs import list_jobs
from ..review.render_pr_comment import COMMENT_MARKER, render_pr_comment
from ..review.run_review import ai_enabled, review
from ..terraform.read_plan_json import load_plan
from ..versions.latest_versions import check_versions, parse_version


def _check_results(env: Dict[str, str]) -> Dict[str, str]:
    """What each CI job reported, by name: {"terraform fmt": "success", ...}. Jobs that did not report are left out.

    Checkov runs without blocking, so a scan that succeeded but found problems is reported as a "warning" with the number
    of findings, never as a clean pass."""
    results = {
        "terraform fmt": env.get("R_FMT", ""),
        "terraform validate": env.get("R_VALIDATE", ""),
        "TFLint": env.get("R_TFLINT", ""),
        "repository contract": env.get("R_CONTRACT", ""),
    }
    checkov_findings = env.get("R_CHECKOV_FAILED") or "0"
    if env.get("R_CHECKOV") == "success" and checkov_findings != "0":
        results["Checkov ({} findings, non-blocking)".format(checkov_findings)] = "warning"
    else:
        results["Checkov"] = env.get("R_CHECKOV", "")
    return {name: status for name, status in results.items() if status}


def _plans_and_costs(env: Dict[str, str], plans_dir: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The plan summary and the cost estimate of each affected root, keyed by the root path.

    The plan jobs uploaded `plan-<slug>.json` and `cost-<slug>.json`; MATRIX says which roots (and slugs) to look for."""
    plans: Dict[str, Any] = {}
    costs: Dict[str, Any] = {}
    matrix = json.loads(env.get("MATRIX") or '{"include": []}')
    for item in matrix.get("include", []):
        plan_file = os.path.join(plans_dir, "plan-{}.json".format(item["slug"]))
        cost_file = os.path.join(plans_dir, "cost-{}.json".format(item["slug"]))
        if os.path.isfile(plan_file):
            plans[item["root"]] = load_plan(plan_file)
        if os.path.isfile(cost_file):
            costs[item["root"]] = load_infracost(cost_file)
    return plans, costs


def _versions_in_use(env: Dict[str, str], plans_dir: str) -> Dict[str, str]:
    """The Terraform and provider versions the plan jobs used, from their `versions-<slug>.json`: {"terraform": "1.16.3", provider source: "5.82.0"}.

    When roots used different versions, the oldest one is kept: it is the one furthest behind."""
    in_use: Dict[str, str] = {}
    for item in json.loads(env.get("MATRIX") or '{"include": []}').get("include", []):
        path = os.path.join(plans_dir, "versions-{}.json".format(item["slug"]))
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        found = dict(data.get("providers") or {})
        found["terraform"] = data.get("terraform")
        for name, version in found.items():
            if version and (name not in in_use or (parse_version(version) or (0, 0, 0)) < (parse_version(in_use[name]) or (0, 0, 0))):
                in_use[name] = version
    return in_use


def pr_review(env: Optional[Dict[str, str]] = None, plans_dir: str = "plans", out: str = "review.json", markdown: str = "review.md") -> int:
    """Build the review of a pull request and write the JSON, the comment text and the job summary.

    The workflow passes what it knows as environment variables: BASE, BASE_REF and DEFAULT_BRANCH (git refs), PR_TITLE and
    PR_BODY (the author's text), IS_FORK, the R_* results of the earlier jobs, and MATRIX (the affected roots).
    The earlier jobs are the gate, so this always exits 0; if the reviewer itself crashes, the comment says so instead of
    disappearing, and the traceback stays in the job log."""
    env = dict(os.environ) if env is None else env
    repo_root = os.path.abspath(".")
    target_branch = env.get("BASE_REF", "")

    try:
        plans, costs = _plans_and_costs(env, plans_dir)
        # The AI is optional: off unless common.yaml enables it, and never for forks (they get no secrets).
        use_ai = env.get("IS_FORK") != "true" and ai_enabled(repo_root)
        result = review(
            repo_root,
            git_changed_files(repo_root, env["BASE"]),
            plans, costs, _check_results(env),
            {"title": env.get("PR_TITLE", ""), "body": env.get("PR_BODY", "")},
            use_ai=use_ai,
            production=bool(target_branch) and target_branch == env.get("DEFAULT_BRANCH"),   # a PR into production protects every root
            branch=target_branch or None,
            versions=check_versions(_versions_in_use(env, plans_dir)),
            jobs=list_jobs(env),
        )
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
        comment = render_pr_comment(result)
        print("decision: {} · risk: {}".format(result["decision"], result["risk"]))
    except Exception:
        traceback.print_exc()
        comment = "{}\n# Infrastructure Review\n\n⚠️ The reviewer failed to run. See the `review` job log.\n".format(COMMENT_MARKER)

    with open(markdown, "w", encoding="utf-8") as handle:
        handle.write(comment)
    append_to_github_file("GITHUB_STEP_SUMMARY", comment, env)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """`python -m reviewer.ci.pr_review [--plans-dir plans] [--out review.json] [--markdown review.md]`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plans-dir", default="plans", help="folder with the plan-<slug>.json and cost-<slug>.json files of the plan jobs")
    parser.add_argument("--out", default="review.json")
    parser.add_argument("--markdown", default="review.md")
    args = parser.parse_args(argv)
    return pr_review(plans_dir=args.plans_dir, out=args.out, markdown=args.markdown)


if __name__ == "__main__":
    sys.exit(main())
