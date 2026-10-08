"""Job "affected configurations": list the Terraform roots a PR affects, for the branch it targets, and hand them to the workflow."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

from ..lib.git_diff import git_changed_files
from ..lib.github_actions import append_to_github_file
from ..terraform.affected_roots import discover
from ..terraform.terraform_map import Repo


def publish_affected_roots(found: List[Dict[str, Any]]) -> None:
    """Give the pull-request workflow the affected roots: the matrix its plan jobs fan out over, how many there are, and a
    readable list for the job summary."""
    matrix = json.dumps({"include": [{key: value for key, value in root.items() if key != "reasons"} for root in found]})
    append_to_github_file("GITHUB_OUTPUT", "matrix={}\ncount={}\n".format(matrix, len(found)))

    lines = ["- `{}`: {}".format(root["root"], "; ".join(root["reasons"][:3])) for root in found]
    lines = lines or ["No Terraform configuration is affected."]
    append_to_github_file("GITHUB_STEP_SUMMARY", "### Affected configurations\n\n" + "\n".join(lines) + "\n")
    print("{} affected configuration(s)".format(len(found)))


def main(argv: Optional[List[str]] = None) -> int:
    """`python -m reviewer.ci.discover_roots --base origin/develop --branch develop`: the roots changed since `base` that `branch` owns."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="git ref (or SHA); the roots affected by the changes since it")
    parser.add_argument("--branch", help="keep only the roots that terraform.deploy in common.yaml lists for this branch (no entry = all)")
    args = parser.parse_args(argv)

    root = os.path.abspath(".")
    changed = [change["path"] for change in git_changed_files(root, args.base)]
    publish_affected_roots(discover(Repo(root), changed, args.branch))
    return 0


if __name__ == "__main__":
    sys.exit(main())
