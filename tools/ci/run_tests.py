"""Job "tests": the tests of the reviewer (pytest) and of the modules (terraform test). They need no AWS and no secrets."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Dict, List, Optional

from ..terraform.run_terraform import run_terraform

REVIEWER_TESTS = "tests/reviewer"
MODULE_TESTS = "tests/terraform"


def _reviewer_tests() -> bool:
    """pytest over tests/reviewer. True when they pass."""
    print("== reviewer tests ({})".format(REVIEWER_TESTS), flush=True)
    return subprocess.run([sys.executable, "-m", "pytest", REVIEWER_TESTS]).returncode == 0


def _module_tests() -> bool:
    """`terraform test` over tests/terraform, with the AWS provider mocked. True when they pass."""
    print("== module tests ({})".format(MODULE_TESTS), flush=True)
    init = run_terraform(MODULE_TESTS, "init", "-backend=false", "-input=false", "-no-color", capture=True)
    if init.returncode:
        print(init.stdout + init.stderr)                  # the output of init is only shown when it fails
        return False
    return run_terraform(MODULE_TESTS, "test", "-no-color").returncode == 0


def tests_step(env: Optional[Dict[str, str]] = None) -> int:
    """Run both kinds of tests, whatever the first one says, and fail if any did. Reads RUNNER_TEMP."""
    env = dict(os.environ) if env is None else env
    # One provider cache: otherwise each run would unpack its own copy of the AWS provider and fill the runner's disk.
    os.environ["TF_PLUGIN_CACHE_DIR"] = os.path.join(env.get("RUNNER_TEMP") or "/tmp", "tf-plugins")
    os.makedirs(os.environ["TF_PLUGIN_CACHE_DIR"], exist_ok=True)

    failed: List[str] = []
    if not _reviewer_tests():
        failed.append(REVIEWER_TESTS)
    if not _module_tests():
        failed.append(MODULE_TESTS)

    print("FAILED: " + ", ".join(failed) if failed else "all tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(tests_step())
