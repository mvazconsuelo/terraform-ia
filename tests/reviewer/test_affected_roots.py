"""Which roots a change affects, and which of them a branch may act on."""
from __future__ import annotations

from typing import List

from tools.terraform.affected_roots import discover
from tools.terraform.terraform_map import Repo

from .conftest import REPO_ROOT

DEV = "infra-example/dev/web-demo"
PROD = "infra-example/prod/web-demo"


def _roots(changed: List[str], branch: str = "") -> List[str]:
    return [item["root"] for item in discover(Repo(str(REPO_ROOT)), changed, branch or None)]


def test_a_change_in_a_shared_module_affects_every_root_that_uses_it() -> None:
    # given: the vpc module, which both environments call
    assert _roots(["modules/vpc/main.tf"]) == [DEV, PROD]


def test_a_change_in_one_root_affects_only_that_root() -> None:
    assert _roots([DEV + "/inputs.yaml"]) == [DEV]


def test_a_change_in_common_yaml_affects_the_roots_that_read_it() -> None:
    # given: both roots read common.yaml for their project and environment
    assert _roots(["common.yaml"]) == [DEV, PROD]


def test_a_change_in_the_docs_affects_nothing() -> None:
    assert _roots(["docs/files.md", "README.md"]) == []


def test_a_branch_only_gets_the_roots_of_its_environments() -> None:
    # given: a change that affects both roots, seen from each branch
    changed = ["modules/vpc/main.tf"]

    # when / then: develop plans dev, main plans prod
    assert _roots(changed, "develop") == [DEV]
    assert _roots(changed, "main") == [PROD]
