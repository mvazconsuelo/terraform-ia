"""The check registries and the Finding builder shared by the contract checks and the plan checks.

A rule in rules.yaml names its check with `check: some_name`. The function that implements it announces that name with a
decorator, which stores it in one of two registries:

  * REGISTRY       contract checks: they read the code            fn(repo, rule)
  * PLAN_REGISTRY  plan checks: they read the plan and the cost   fn(plans, costs, rule)   (both keyed by root path)
"""
from __future__ import annotations

import os
import re
from typing import Callable, Dict, List

from ..review.finding import Finding
from ..terraform.terraform_map import Repo

Check = Callable[[Repo, dict], List[Finding]]
PlanCheck = Callable[[Dict[str, dict], Dict[str, dict], dict], List[Finding]]

REGISTRY: Dict[str, Check] = {}
PLAN_REGISTRY: Dict[str, PlanCheck] = {}


def check(name: str):
    """Decorator: register a contract check under the name that `check:` in rules.yaml refers to."""
    def register(function: Check) -> Check:
        REGISTRY[name] = function
        return function

    return register


def plan_check(name: str):
    """Decorator: register a plan check. It receives the plans and costs keyed by root path."""
    def register(function: PlanCheck) -> PlanCheck:
        PLAN_REGISTRY[name] = function
        return function

    return register


def make_finding(rule: dict, evidence: str, file=None, line=None, resource=None, **overrides) -> Finding:
    """Build a Finding from a rule's metadata and the evidence of one violation.

    The severity, title, explanation and recommendation come from the rule; `overrides` can replace any field (a check
    may raise or lower the severity for one case, for example)."""
    fields = dict(
        severity=rule["severity"],
        category=rule["category"],
        title=rule["title"],
        evidence=evidence,
        explanation=" ".join(str(rule.get("explanation", "")).split()),   # collapse the line breaks of the YAML text
        recommendation=rule.get("recommendation", ""),
        file=file,
        line=line,
        resource=resource,
        rule_id=rule["id"],
    )
    fields.update(overrides)
    return Finding(**fields)


def run_plan_checks(
    plans: Dict[str, dict], costs: Dict[str, dict], rules: List[dict], protected: Callable[[str], bool] = lambda root: False,
) -> List[Finding]:
    """Run every plan check (the PLAN-* rules). `protected(root)` says whether a root is protected."""
    findings: List[Finding] = []
    for rule in rules:
        check_function = PLAN_REGISTRY.get(rule.get("check", ""))
        if check_function is not None:                              # contract rules have no plan function
            findings.extend(check_function(plans, costs, dict(rule, _protected=protected)))
    return findings


# ----------------------------------------------------------------------------------------------------------------
# Small helpers shared by several checks
# ----------------------------------------------------------------------------------------------------------------
def folder_of(path: str) -> str:
    """The folder that contains a file."""
    return os.path.dirname(path)


def mentions_all(words: List[str], text: str) -> bool:
    """Whether every word appears in the text as a whole word (so `Owner` does not match `OwnerId`)."""
    return all(re.search(r"\b%s\b" % word, text) for word in words)
