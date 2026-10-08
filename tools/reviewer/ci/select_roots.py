"""Step "which roots" of terraform.yml: decide which root configurations a run acts on."""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, Optional

from .git_diff import git_changed_files
from ..terraform.affected_roots import discover
from ..terraform.terraform_map import Repo
from .github_actions import append_to_github_file, branch_of


def select_roots(env: Optional[Dict[str, str]] = None) -> int:
    """Decide which roots a terraform.yml run acts on, and publish them as the step outputs `matrix` and `count`.

    On a push: the roots that push affected and that the pushed branch may apply (`terraform.deploy`).
    Otherwise (called by a PR, or run by hand): the one root that was asked for.
    Reads EVENT, BEFORE (the commit before the push), REF_NAME and ROOT from the environment."""
    env = os.environ if env is None else env
    repo_root = os.path.abspath(".")
    repo = Repo(repo_root)

    if env.get("EVENT") == "push":
        base = env.get("BEFORE", "")
        if base.startswith("0000000"):          # the first push of a branch has no previous commit
            base = "HEAD~1"
        changed = [change["path"] for change in git_changed_files(repo_root, base)]
        found = discover(repo, changed, branch_of(env) or None)
    else:
        found = [root for root in discover(repo, None) if root["root"] == env.get("ROOT")]

    matrix = {"include": [{key: value for key, value in root.items() if key != "reasons"} for root in found]}
    # Compact JSON (no spaces): the workflow compares and reads it as-is.
    append_to_github_file("GITHUB_OUTPUT", "matrix={}\ncount={}\n".format(json.dumps(matrix, separators=(",", ":")), len(found)))
    print("{} root(s): {}".format(len(found), ", ".join(root["root"] for root in found) or "nothing to run"))
    return 0


if __name__ == "__main__":
    sys.exit(select_roots())
