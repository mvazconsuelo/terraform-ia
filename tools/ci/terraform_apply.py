"""Step "terraform apply": apply the plan that `terraform plan` saved, so exactly what was shown is what runs."""
from __future__ import annotations

import os
import sys
from typing import Dict, Optional

from ..aws import account
from ..lib.github_actions import branch_of, fail, mode_of
from ..terraform.run_terraform import run_terraform


def apply_step(env: Optional[Dict[str, str]] = None) -> int:
    """`terraform apply` of the saved plan `tfplan` of one root. Does nothing when the run is only a plan.

    Reads ROOT, INPUT_MODE, INPUT_BRANCH or REF_NAME, AWS_REGION and the branch key variables."""
    env = dict(os.environ) if env is None else env
    if mode_of(env) != "apply":
        print("This run only plans; nothing to apply.")
        return 0
    aws_env, error = account.session(env, branch_of(env))
    if error:
        return fail(error)
    return run_terraform(env["ROOT"], "apply", "-input=false", "-lock-timeout=10m", "tfplan", env=aws_env).returncode


if __name__ == "__main__":
    sys.exit(apply_step())
