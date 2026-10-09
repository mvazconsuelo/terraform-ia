"""Step "which roots" of terraform.yml: decide which root configurations a run acts on."""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, Optional

from ..lib.github_actions import append_to_github_file, branch_of
from ..terraform.affected_roots import discover
from ..terraform.terraform_map import Repo


def select_roots(env: Optional[Dict[str, str]] = None) -> int:
    """Decide which root a terraform.yml run acts on, and publish it as the step outputs `matrix` and `count`.

    A run is always about the one root that was asked for (by a PR plan or by hand). A manual run deploys, so the selected branch must be
    named by an environment of `terraform.environments` in common.yaml, and the root must belong to one of those environments; otherwise
    nothing runs (a run from `feature/x` cannot reach a root).
    Reads EVENT, ROOT and REF_NAME from the environment."""
    env = dict(os.environ) if env is None else env
    repo = Repo(os.path.abspath("."))
    manual = env.get("EVENT") == "workflow_dispatch"
    branch = (branch_of(env) or None) if manual else None
    if manual and (branch is None or repo.roots_of_branch(branch) is None):
        found: list = []
        print("No environment of terraform.environments names the branch '{}': a manual run deploys, so it needs one.".format(branch))
    else:
        found = [root for root in discover(repo, None, branch) if root["root"] == env.get("ROOT")]

    matrix = {"include": [{key: value for key, value in root.items() if key != "reasons"} for root in found]}
    # Compact JSON (no spaces): the workflow compares and reads it as-is.
    append_to_github_file("GITHUB_OUTPUT", "matrix={}\ncount={}\n".format(json.dumps(matrix, separators=(",", ":")), len(found)))
    print("{} root(s): {}".format(len(found), ", ".join(root["root"] for root in found) or "nothing to run (not a root, or this branch may not deploy it)"))
    return 0


if __name__ == "__main__":
    sys.exit(select_roots())
