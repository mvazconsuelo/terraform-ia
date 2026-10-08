"""Step "terraform versions": record which Terraform and provider versions a plan used, so the review can say if newer ones exist."""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, Optional

from ..lib.github_actions import mode_of
from ..terraform.run_terraform import run_terraform


def versions_step(env: Optional[Dict[str, str]] = None) -> int:
    """Write `versions-<slug>.json`: {"terraform": "1.16.3", "providers": {"registry.terraform.io/hashicorp/aws": "5.82.0"}}.

    Informational only, so it never fails the job. Does nothing unless the run is a plan. Reads ROOT, SLUG and INPUT_MODE;
    runs after `terraform init`, which is what resolves the provider versions."""
    env = dict(os.environ) if env is None else env
    if mode_of(env) != "plan":
        print("This run applies; the versions are only recorded for a plan.")
        return 0
    result = run_terraform(env["ROOT"], "version", "-json", capture=True)
    if result.returncode:
        print("Could not read the Terraform versions: {}".format(result.stderr.strip()))
        return 0
    data = json.loads(result.stdout)
    with open("versions-{}.json".format(env["SLUG"]), "w", encoding="utf-8") as handle:
        json.dump({"terraform": data.get("terraform_version"), "providers": data.get("provider_selections") or {}}, handle, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(versions_step())
