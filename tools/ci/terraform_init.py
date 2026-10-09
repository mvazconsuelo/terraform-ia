"""Step "terraform init": check we are about to touch the right AWS account, then connect the root to its state.

Every check before `init` can stop the run without touching anything:
  1. pick the AWS keys of the branch (`main` -> the MAIN keys, any other branch -> the DEVELOP keys);
  2. check that those keys belong to the account of the repository variable AWS_ACCOUNT_ID_<DEVELOP|MAIN>, so keys pasted into the wrong
     secret cannot create resources in the wrong account;
  3. check that the state bucket `<project>-tfstate-<account>-<region>` exists (it is created by hand, once).
"""
from __future__ import annotations

import glob
import os
import re
import sys
from typing import Dict, Optional

import yaml

from ..aws import account
from ..lib.github_actions import branch_of, fail
from ..terraform.run_terraform import run_terraform


def _ensure_backend_block(folder: str) -> None:
    """Write `backend.tf` with an empty S3 backend, unless the root already declares one.

    The values (bucket, key, region...) are passed to `terraform init` instead, so they never live in the code."""
    declares_backend = any(
        re.search(r'^\s*backend\s+"s3"', open(path, encoding="utf-8").read(), re.MULTILINE)
        for path in glob.glob(os.path.join(folder, "*.tf"))
    )
    if not declares_backend:
        with open(os.path.join(folder, "backend.tf"), "w", encoding="utf-8") as handle:
            handle.write('terraform {\n  backend "s3" {}\n}\n')


def init_step(env: Optional[Dict[str, str]] = None) -> int:
    """`terraform init` of one root against the S3 state bucket. Reads ROOT, INPUT_BRANCH or REF_NAME, AWS_REGION and the branch key variables."""
    env = dict(os.environ) if env is None else env
    folder, branch, region = env["ROOT"], branch_of(env), env.get("AWS_REGION", "")

    # 1. the keys
    aws_env, error = account.session(env, branch)
    if aws_env is None or error:
        return fail(error or "No AWS session.")

    # 2. the account guard
    target = account.target_for(branch)
    with open("common.yaml", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    expected = account.expected_account(branch, env)
    if not expected:
        return fail("The repository variable AWS_ACCOUNT_ID_{} is not set: it says which account the '{}' keys must belong to. Nothing was run.".format(
            target.upper(), target))
    actual, reason = account.account_of(aws_env)
    if actual is None:
        return fail("Could not identify the AWS account of the '{}' keys: {}".format(target, reason))
    if actual != expected:
        return fail("The AWS keys for '{}' belong to account {}, but AWS_ACCOUNT_ID_{} expects {}. Nothing was run.".format(
            target, actual, target.upper(), expected))

    # 3. the state bucket
    bucket = "{}-tfstate-{}-{}".format(config["project"], actual, region)
    if not account.bucket_exists(bucket, aws_env):
        return fail("State bucket {} does not exist. Create it once (see docs/install.md).".format(bucket))

    # init: the state key is the root's path, so each root has its own state
    _ensure_backend_block(folder)
    backend = config.get("backend") or {}
    return run_terraform(
        folder, "init", "-input=false",
        "-backend-config=bucket=" + bucket,
        "-backend-config=key={}/terraform.tfstate".format(folder),
        "-backend-config=region=" + region,
        "-backend-config=encrypt=" + str(bool(backend.get("encrypt"))).lower(),
        "-backend-config=use_lockfile=" + str(bool(backend.get("use_lockfile"))).lower(),     # S3 native state lock, no DynamoDB
        env=aws_env,
    ).returncode

if __name__ == "__main__":
    sys.exit(init_step())
