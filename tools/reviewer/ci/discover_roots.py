"""Job "affected configurations": list the Terraform roots (or modules) a change affects, for a target branch."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

from .git_diff import git_changed_files
from ..terraform.affected_roots import discover
from ..terraform.terraform_map import Repo
from .github_actions import append_to_github_file


def publish_affected_roots(found: List[Dict[str, Any]]) -> None:
    """Give the pull-request workflow the affected roots: the matrix its plan jobs fan out over, how many there are, and a
    readable list for the job summary. Used by `discover --github`."""
    matrix = json.dumps({"include": [{key: value for key, value in root.items() if key != "reasons"} for root in found]})
    append_to_github_file("GITHUB_OUTPUT", "matrix={}\ncount={}\n".format(matrix, len(found)))

    lines = ["- `{}`: {}".format(root["root"], "; ".join(root["reasons"][:3])) for root in found]
    lines = lines or ["No Terraform configuration is affected."]
    append_to_github_file("GITHUB_STEP_SUMMARY", "### Affected configurations\n\n" + "\n".join(lines) + "\n")
    print("{} affected configuration(s)".format(len(found)))


def discover_command(root: str, base: Optional[str], all_roots: bool, branch: Optional[str], output_format: str, github: bool, modules: bool) -> int:
    """List the roots (or, with `modules`, the shared modules) that a change affects.

    `all_roots` ignores the change and lists everything. `output_format` is json, matrix or text. With `github` the result is
    handed to the workflow as step outputs instead of printed."""
    repo = Repo(root)
    changed = None if all_roots else [change["path"] for change in git_changed_files(root, base)]

    if modules:
        names = repo.module_dirs() if all_roots else repo.affected_modules(changed)
        print("\n".join(names))
        return 0

    found = discover(repo, changed, branch)
    if github:
        publish_affected_roots(found)
    elif output_format == "matrix":
        print(json.dumps({"include": [{key: value for key, value in item.items() if key != "reasons"} for item in found]}))
    elif output_format == "text":
        for item in found:
            print("{}  ({})".format(item["root"], "; ".join(item["reasons"][:3])))
    else:
        print(json.dumps(found, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """`python -m reviewer.ci.discover_roots --base REF [--branch B] [--format text|matrix|json] [--github] [--modules]`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--base", help="git ref (or SHA); the roots affected by the changes since it")
    selection.add_argument("--all", action="store_true", help="every root")
    parser.add_argument("--format", choices=["json", "matrix", "text"], default="json", help='matrix = {"include": [...]} for a GitHub Actions strategy')
    parser.add_argument("--branch", help="keep only the roots that terraform.deploy in common.yaml lists for this branch (no entry = all)")
    parser.add_argument("--github", action="store_true", help="GitHub Actions: write matrix and count to $GITHUB_OUTPUT and the list to the job summary")
    parser.add_argument("--modules", action="store_true", help="list the shared modules affected (one path per line) instead of the roots")
    args = parser.parse_args(argv)
    return discover_command(os.path.abspath(args.root), args.base, args.all, args.branch, args.format, args.github, args.modules)


if __name__ == "__main__":
    sys.exit(main())
