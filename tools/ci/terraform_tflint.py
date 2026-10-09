"""Job "TFLint": the linter for Terraform modules (required versions, documented and typed variables, naming...).

Its rules live in `.tflint.hcl` at the repository root. Root configurations are not linted: they are not modules, so the
module-structure rules do not apply to them.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Dict, List, Optional

from ..lib.git_diff import git_changed_files
from ..terraform.terraform_map import Repo


def _run(command: List[str], folder: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(command, cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def tflint_step(env: Optional[Dict[str, str]] = None) -> int:
    """TFLint on every module the PR affects. Every module is linted even if an earlier one fails. Reads BASE."""
    env = dict(os.environ) if env is None else env
    repo_root = os.path.abspath(".")
    modules = Repo(repo_root).affected_modules([change["path"] for change in git_changed_files(repo_root, env["BASE"])])
    if not modules:
        print("No module affected; nothing to lint.")
        return 0

    config = os.path.join(repo_root, ".tflint.hcl")
    setup = _run(["tflint", "--init", "--config", config], repo_root)          # downloads the rule plugins
    print(setup.stdout)
    if setup.returncode:
        return setup.returncode

    failed = []
    for module in modules:
        print("== tflint {}".format(module), flush=True)
        result = _run(["tflint", "--chdir", module, "--config", config], repo_root)
        print(result.stdout)
        if result.returncode:
            failed.append(module)
    if failed:
        print("FAILED: {}".format(", ".join(failed)), file=sys.stderr)
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(tflint_step())
