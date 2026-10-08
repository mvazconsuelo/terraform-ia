"""Step "infracost": estimate the monthly cost of a plan. The only source of prices in the review.

The step decides by itself whether to run, and installs Infracost if the machine does not have it, so the workflow only calls it.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from typing import Dict, Optional

from ..terraform.run_terraform import run_terraform
from .github_actions import mode_of

# The Infracost release to install on a Linux runner, pinned so a run is reproducible. Its checksum is verified.
INFRACOST_VERSION = "v0.10.46"
_RELEASE = "https://github.com/infracost/infracost/releases/download/{version}/infracost-linux-amd64.tar.gz"


def _install_infracost(directory: str) -> str:
    """Download the pinned Infracost release into `directory`, verify its SHA-256 and return the path of the program."""
    url = _RELEASE.format(version=INFRACOST_VERSION)
    with urllib.request.urlopen(url, timeout=120) as response:
        archive = response.read()
    with urllib.request.urlopen(url + ".sha256", timeout=60) as response:
        expected = response.read().decode().split()[0]            # the file reads "<hash>  <name>"
    if hashlib.sha256(archive).hexdigest() != expected:
        raise RuntimeError("the downloaded Infracost does not match its published checksum")

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        member = next(item for item in tar.getmembers() if item.isfile() and item.name.startswith("infracost"))
        content = tar.extractfile(member).read()
    program = os.path.join(directory, "infracost")
    with open(program, "wb") as handle:
        handle.write(content)
    os.chmod(program, os.stat(program).st_mode | stat.S_IEXEC)
    return program


def estimate_step(env: Optional[Dict[str, str]] = None) -> int:
    """Write `cost-<slug>.json`: the Infracost estimate of the plan saved by the plan step.

    Does nothing unless the run is a plan and an Infracost key exists. An Infracost failure is not an error for the pipeline:
    it only warns, and the cost section of the comment stays empty. The raw plan it reads goes to a temporary file that is
    deleted at once, because a raw plan can hold secrets. Reads ROOT, SLUG, INPUT_MODE and INFRACOST_API_KEY."""
    env = os.environ if env is None else env
    if mode_of(env) != "plan":
        print("This run applies; the cost estimate is only needed for a plan.")
        return 0
    if not env.get("INFRACOST_API_KEY"):
        print("Infracost is not configured (no INFRACOST_API_KEY); no cost estimate.")
        return 0

    shown = run_terraform(env["ROOT"], "show", "-json", "tfplan", capture=True)
    if shown.returncode:
        print(shown.stderr)
        return shown.returncode

    workdir = tempfile.mkdtemp()
    try:
        program = shutil.which("infracost") or _install_infracost(workdir)
        raw_plan = os.path.join(workdir, "raw-plan.json")
        with open(raw_plan, "w", encoding="utf-8") as handle:
            handle.write(shown.stdout)
        done = subprocess.run(
            [program, "diff", "--path", raw_plan, "--format", "json", "--out-file", "cost-{}.json".format(env["SLUG"])],
            env=dict(os.environ, INFRACOST_API_KEY=env["INFRACOST_API_KEY"], INFRACOST_SKIP_UPDATE_CHECK="true"),
        )
        if done.returncode:
            print("::warning::Infracost failed; the cost section will be empty")
    except Exception as error:                                    # a download or install problem must not fail the pipeline
        print("::warning::Infracost could not run ({}); the cost section will be empty".format(error))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(estimate_step())
