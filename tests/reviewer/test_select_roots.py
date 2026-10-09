"""Which root a run of terraform.yml acts on. A manual run deploys, so it is the strictest case."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

from tools.ci.select_roots import select_roots

from .conftest import REPO_ROOT

DEV = "infra-example/dev/web-demo"
PROD = "infra-example/prod/web-demo"


def _roots_selected(event: str, ref: str, root: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Run the step as the workflow does and return how many roots it selected (the `count` output)."""
    output = tmp_path / "github_output"
    environment: Dict[str, str] = {"EVENT": event, "ROOT": root, "REF_NAME": ref}
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))                  # the step writes its outputs to this file, as on a runner
    monkeypatch.chdir(REPO_ROOT)
    assert select_roots(environment) == 0
    lines = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    return int(lines["count"])


def test_a_manual_run_from_develop_can_reach_the_dev_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _roots_selected("workflow_dispatch", "develop", DEV, tmp_path, monkeypatch) == 1


def test_a_manual_run_from_main_can_reach_the_prod_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _roots_selected("workflow_dispatch", "main", PROD, tmp_path, monkeypatch) == 1


def test_a_manual_run_from_develop_cannot_reach_the_prod_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # given: develop's keys belong to the dev account, and prod is another environment
    assert _roots_selected("workflow_dispatch", "develop", PROD, tmp_path, monkeypatch) == 0


def test_a_manual_run_from_a_branch_no_environment_names_reaches_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # given: feature/x is not the branch of any environment, so a deployment from it is not allowed
    assert _roots_selected("workflow_dispatch", "feature/x", DEV, tmp_path, monkeypatch) == 0
    assert _roots_selected("workflow_dispatch", "feature/x", PROD, tmp_path, monkeypatch) == 0


def test_a_plan_called_by_a_pull_request_reaches_the_root_it_was_asked_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # given: a read-only plan from a PR, whatever its branch
    assert _roots_selected("workflow_call", "feature/x", DEV, tmp_path, monkeypatch) == 1
