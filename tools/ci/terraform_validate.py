"""Job "terraform validate": does the configuration of each affected module and root make sense (syntax, references, types)?"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Dict, List, Optional

from ..lib.git_diff import git_changed_files
from ..terraform.affected_roots import for_branch
from ..terraform.terraform_map import Repo


def _validate_folders(folders: List[str], repo_root: str, runner_temp: str) -> List[str]:
    """Run `terraform init -backend=false` and `terraform validate` in each folder. Returns the folders that failed.

    Every folder is validated even if an earlier one fails. All of them share one provider cache: otherwise each folder
    would unpack its own copy of the AWS provider (hundreds of MB) and fill the runner's disk."""
    os.environ["TF_PLUGIN_CACHE_DIR"] = os.path.join(runner_temp or "/tmp", "tf-plugins")
    os.makedirs(os.environ["TF_PLUGIN_CACHE_DIR"], exist_ok=True)

    failed = []
    for folder in folders:
        print("== validate {}".format(folder), flush=True)
        for command in (["terraform", "init", "-backend=false", "-input=false", "-no-color"], ["terraform", "validate", "-no-color"]):
            result = subprocess.run(command, cwd=os.path.join(repo_root, folder), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if result.returncode:
                print(result.stdout)             # the output is only shown when something fails
                failed.append(folder)
                break

    print("validated: {}".format(", ".join(folders) or "nothing was affected"))
    if failed:
        print("FAILED: {}".format(", ".join(failed)), file=sys.stderr)
    return failed


def validate_step(env: Optional[Dict[str, str]] = None) -> int:
    """`terraform validate` in every module and every root the PR affects. Reads BASE, BASE_REF and RUNNER_TEMP."""
    env = dict(os.environ) if env is None else env
    repo_root = os.path.abspath(".")
    repo = Repo(repo_root)
    paths = [change["path"] for change in git_changed_files(repo_root, env["BASE"])]

    modules = repo.affected_modules(paths)
    roots = [root["root"] for root in for_branch(repo, repo.affected(paths), env.get("BASE_REF") or None)]
    failed = _validate_folders(modules + roots, repo_root, env.get("RUNNER_TEMP", ""))
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(validate_step())
