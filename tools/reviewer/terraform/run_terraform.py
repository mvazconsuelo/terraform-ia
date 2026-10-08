"""Run the `terraform` program in a folder. The only place that starts it; it knows nothing about GitHub or AWS."""
from __future__ import annotations

import subprocess
from typing import Dict, Optional


def run_terraform(folder: str, *arguments: str, env: Optional[Dict[str, str]] = None, capture: bool = False) -> "subprocess.CompletedProcess[str]":
    """`terraform -chdir=<folder> <arguments>`. The output goes to the log, or is returned when `capture` is set.

    `env` is the process environment (for example the one with the AWS keys); None keeps the current one."""
    return subprocess.run(["terraform", "-chdir=" + folder, *arguments], env=env, text=True, capture_output=capture)
