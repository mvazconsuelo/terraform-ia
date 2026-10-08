"""Step "terraform plan": plan one root and save the plan to the file `tfplan`, so a later `apply` runs exactly that plan."""
from __future__ import annotations

import os
import sys
from typing import Dict, Optional

from ..aws import account
from ..lib.github_actions import branch_of, fail
from ..terraform.run_terraform import run_terraform


def plan_step(env: Optional[Dict[str, str]] = None) -> int:
    """`terraform plan` of one root, saved to `tfplan`. Reads ROOT, INPUT_BRANCH or REF_NAME, AWS_REGION and the branch key variables."""
    env = dict(os.environ) if env is None else env
    aws_env, error = account.session(env, branch_of(env))
    if error:
        return fail(error)
    return run_terraform(env["ROOT"], "plan", "-input=false", "-lock-timeout=10m", "-out=tfplan", env=aws_env).returncode


if __name__ == "__main__":
    sys.exit(plan_step())
