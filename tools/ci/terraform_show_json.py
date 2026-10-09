"""Step "terraform show -json": read the saved plan as JSON and reduce it to the small, secret-free file the PR review reads."""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, Optional

from ..lib.github_actions import mode_of
from ..terraform.read_plan_json import summarize_plan
from ..terraform.run_terraform import run_terraform


def show_json_step(env: Optional[Dict[str, str]] = None) -> int:
    """Write `plan-<slug>.json`: the saved plan (`terraform show -json`) reduced to counts and sanitized changes.

    The raw plan can hold secrets, so it is only ever held in memory: the file that is written has none. Does nothing unless the run is a plan.
    Reads ROOT, SLUG and INPUT_MODE; expects the plan saved by the plan step (`tfplan`) in the root folder."""
    env = dict(os.environ) if env is None else env
    if mode_of(env) != "plan":
        print("This run applies; the plan summary is only needed for a plan.")
        return 0
    shown = run_terraform(env["ROOT"], "show", "-json", "tfplan", capture=True)
    if shown.returncode:
        print(shown.stderr)               # why there is no saved plan to read
        return shown.returncode
    with open("plan-{}.json".format(env["SLUG"]), "w", encoding="utf-8") as handle:
        json.dump(summarize_plan(json.loads(shown.stdout)), handle, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(show_json_step())
