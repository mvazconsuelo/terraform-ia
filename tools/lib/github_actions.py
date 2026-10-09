"""Helpers for talking to GitHub Actions: step outputs, the job summary and errors."""
from __future__ import annotations

import os
from typing import Dict, Optional


def append_to_github_file(variable: str, text: str, env: Optional[Dict[str, str]] = None) -> None:
    """Append text to the file a GitHub Actions variable points at, if the variable is set.

    `$GITHUB_OUTPUT` holds the outputs of a step (`name=value` lines the next jobs can read) and `$GITHUB_STEP_SUMMARY` holds
    the Markdown shown on the run's page. Outside GitHub the variables are not set and nothing is written."""
    path = (os.environ if env is None else env).get(variable)
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)


def fail(message: str) -> int:
    """Report an error in the GitHub Actions log and return the exit code 1."""
    print("::error::{}".format(message))
    return 1


def mode_of(env: Dict[str, str]) -> str:
    """What this run does: "plan" or "apply". Every run says so (INPUT_MODE); if one does not, it only plans."""
    return env.get("INPUT_MODE") or "plan"


def branch_of(env: Dict[str, str]) -> str:
    """The branch this run belongs to, which decides the AWS account. A PR plan is told its target branch (INPUT_BRANCH);
    otherwise it is the branch that was pushed or selected (REF_NAME)."""
    return env.get("INPUT_BRANCH") or env.get("REF_NAME", "")
