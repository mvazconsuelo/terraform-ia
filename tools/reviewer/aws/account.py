"""Which AWS account a branch uses, and the checks that stop a run on the wrong one.

`main` uses its own keys; every other branch uses the develop keys. The keys are repository secrets named per branch
(`AWS_ACCESS_KEY_ID_MAIN`, `AWS_ACCESS_KEY_ID_DEVELOP`...); common.yaml says which account id each pair must belong to.
"""
from __future__ import annotations

import os
import subprocess
from typing import Dict, Optional, Tuple


def target_for(branch: str) -> str:
    """The key set a branch uses: "main" for the production branch, "develop" for everything else."""
    return "main" if branch == "main" else "develop"


def credentials_for(target: str, env: Dict[str, str]) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """The AWS keys of a target as (keys, None), or (None, error message) when one is missing.

    The workflow exposes them as KEY_ID_<TARGET> and KEY_SECRET_<TARGET>."""
    keys = {
        "AWS_ACCESS_KEY_ID": env.get("KEY_ID_" + target.upper(), ""),
        "AWS_SECRET_ACCESS_KEY": env.get("KEY_SECRET_" + target.upper(), ""),
    }
    for name, value in keys.items():
        if not value:
            return None, "Missing the {}_{} secret.".format(name, target.upper())
    return keys, None


def process_env(keys: Dict[str, str], region: str) -> Dict[str, str]:
    """The environment to run aws and terraform with: the current one plus the keys and the region."""
    return dict(os.environ, AWS_REGION=region, **keys)


def account_of(aws_env: Dict[str, str]) -> Tuple[Optional[str], str]:
    """Ask AWS which account the keys belong to. Returns (account id, "") or (None, the error)."""
    result = subprocess.run(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        env=aws_env, capture_output=True, text=True,
    )
    if result.returncode:
        return None, result.stderr.strip()[:200]
    return result.stdout.strip(), ""


def bucket_exists(bucket: str, aws_env: Dict[str, str]) -> bool:
    """Whether the S3 bucket exists and these keys can reach it."""
    return subprocess.run(["aws", "s3api", "head-bucket", "--bucket", bucket], env=aws_env, capture_output=True).returncode == 0


def session(env: Dict[str, str], branch: str) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """The environment to run aws and terraform with for `branch`, as (aws_env, None); or (None, error message).

    Reads AWS_REGION and the branch key variables the workflow exposes (KEY_ID_MAIN, KEY_SECRET_DEVELOP...)."""
    region = env.get("AWS_REGION", "")
    if not region:
        return None, "Set the AWS_REGION secret."
    keys, error = credentials_for(target_for(branch), env)
    if error:
        return None, error
    return process_env(keys, region), None
