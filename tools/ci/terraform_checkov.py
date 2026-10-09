"""Job "Checkov": the security scanner for Terraform (encryption, public access, logging...)."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional

from ..lib.git_diff import git_changed_files
from ..lib.github_actions import append_to_github_file
from ..terraform.terraform_map import Repo


def checkov_step(env: Optional[Dict[str, str]] = None, base: Optional[str] = None) -> int:
    """Checkov on every module the PR affects, and publish the number of findings as the step output `failed`.

    Checkov runs with --soft-fail: its findings are shown in the log but do not make it exit with an error, so they do not
    block yet. The number is published so the review shows the findings instead of a clean pass. The exit code is non-zero
    only when Checkov itself breaks."""
    env = dict(os.environ) if env is None else env
    repo_root = os.path.abspath(".")
    modules = Repo(repo_root).affected_modules([change["path"] for change in git_changed_files(repo_root, base or env["BASE"])])

    if not modules:
        print("No module affected; nothing to scan.")
        append_to_github_file("GITHUB_OUTPUT", "failed=0\n", env)
        return 0

    command = ["checkov", "--framework", "terraform", "--compact", "--soft-fail"]
    for module in modules:
        command += ["-d", module]

    failed_checks = 0
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout or []:
        sys.stdout.write(line)                                             # keep Checkov's output in the job log
        summary = re.search(r"Failed checks: (\d+)", line)                 # "Passed checks: 123, Failed checks: 31, ..."
        if summary:
            failed_checks += int(summary.group(1))
    append_to_github_file("GITHUB_OUTPUT", "failed={}\n".format(failed_checks), env)
    return process.wait()


def main(argv: Optional[List[str]] = None) -> int:
    """`python -m tools.ci.terraform_checkov [--base REF]` (the base defaults to $BASE)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="git ref to compare with (default: $BASE)")
    return checkov_step(base=parser.parse_args(argv).base)


if __name__ == "__main__":
    sys.exit(main())
