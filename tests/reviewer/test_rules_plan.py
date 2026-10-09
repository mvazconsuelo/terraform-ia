"""PLAN: what will terraform do, and what will it cost? These rules read the plan and the Infracost estimate."""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from tools.review.finding import Finding
from tools.review.run_review import load_rules
from tools.rules.registry import run_plan_checks
from tools.terraform.terraform_map import Repo

from .conftest import REPO_ROOT

PROD = "infra-example/prod/web-demo"
DEV = "infra-example/dev/web-demo"


def _plan_with(address: str, kind: str, actions: List[str], replace: bool = False) -> Dict[str, Any]:
    """A plan with one resource change, in the shape the reviewer reads."""
    return {"resource_changes": [{"address": address, "type": kind, "actions": actions, "replace": replace}]}


def _run(plans: Dict[str, Any], costs: Dict[str, Any], protected: Callable[[str], bool] = lambda root: False) -> List[Finding]:
    return run_plan_checks(plans, costs, load_rules(), protected)


# ---------------------------------------------------------------- PLAN-001: destroying something that holds state
def test_plan_001_flags_a_plain_destroy_as_critical_everywhere() -> None:
    # given: a plan that deletes a database in dev, which is not protected
    plans = {DEV: _plan_with("module.database.aws_rds_cluster.this", "aws_rds_cluster", ["delete"])}

    # when / then
    assert [finding.severity for finding in _run(plans, {})] == ["CRITICAL"]


def test_plan_001_flags_a_replacement_as_high_in_an_unprotected_root() -> None:
    # given: a plan that replaces (destroys and recreates) a database in dev
    plans = {DEV: _plan_with("module.database.aws_rds_cluster.this", "aws_rds_cluster", ["delete", "create"], replace=True)}

    # when / then
    assert [finding.severity for finding in _run(plans, {})] == ["HIGH"]


def test_plan_001_flags_a_replacement_as_critical_in_a_protected_root() -> None:
    # given: the same replacement, in a root that is protected
    plans = {PROD: _plan_with("module.database.aws_rds_cluster.this", "aws_rds_cluster", ["delete", "create"], replace=True)}

    # when / then
    assert [finding.severity for finding in _run(plans, {}, protected=lambda root: root == PROD)] == ["CRITICAL"]


def test_plan_001_ignores_the_destruction_of_something_without_state() -> None:
    # given: a plan that deletes a security group rule
    plans = {DEV: _plan_with("module.sg.aws_vpc_security_group_ingress_rule.this", "aws_vpc_security_group_ingress_rule", ["delete"])}

    # when / then
    assert _run(plans, {}) == []


# ---------------------------------------------------------------- who is protected
def test_protection_follows_the_protected_environments_of_the_rule() -> None:
    # given: the repository, and the environments PLAN-001 protects
    repo = Repo(str(REPO_ROOT))
    repo.protected_environments = ["prod"]

    # when / then: prod is protected, dev is not
    assert repo.is_protected(PROD) and not repo.is_protected(DEV)


def test_protection_covers_every_root_in_a_pull_request_into_production() -> None:
    # given: a review of a pull request into the production branch
    repo = Repo(str(REPO_ROOT))
    repo.protect_all = True

    # when / then
    assert repo.is_protected(DEV) and repo.is_protected(PROD)


# ---------------------------------------------------------------- PLAN-002: a large monthly increase
def test_plan_002_flags_an_increase_above_the_threshold() -> None:
    # given: Infracost estimates +250 USD a month, the threshold is 200
    costs = {DEV: {"monthly_delta": 250.0, "currency": "USD", "current_monthly_cost": 100, "proposed_monthly_cost": 350}}

    # when / then
    found = _run({}, costs)
    assert len(found) == 1 and "+250" in found[0].evidence


def test_plan_002_ignores_an_increase_below_the_threshold() -> None:
    # given: +50 USD a month
    costs = {DEV: {"monthly_delta": 50.0, "currency": "USD", "current_monthly_cost": 100, "proposed_monthly_cost": 150}}

    # when / then
    assert _run({}, costs) == []
