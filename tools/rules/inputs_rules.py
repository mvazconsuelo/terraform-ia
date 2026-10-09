"""The checks that read the `inputs.yaml` of a root: the values a project gives to the modules it calls.

A module never sees this file (its variables are its contract); the project that builds the infrastructure owns it. These checks hold the
project's own policy, which is data in `rules.yaml` and `common.yaml`, so another project changes the data and not the code. The
environment of a root comes from `terraform.environments` in `common.yaml`; an environment deployed from the `main` branch is the production one.

  ROOT-003    the root is assigned to an environment (terraform.environments in common.yaml)
  ROOT-004    its `tags` have the owner and the cost center and nothing that common.yaml sets
  POLICY-001  a root of a production environment meets the requirements listed in the catalog
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterator, List, Optional, Tuple

import yaml

from ..review.finding import Finding
from ..terraform.terraform_map import Repo
from .registry import check, make_finding

Inputs = Tuple[str, str, Optional[Dict[str, Any]], Optional[str]]


def _environment_of_root(repo: Repo, root: str) -> Optional[Tuple[str, bool]]:
    """(the environment this root belongs to, whether it is deployed from the production branch), from `terraform.environments`; None if it belongs to none."""
    name = repo.environment_of(root)
    return None if name is None else (name, repo.branch_of_environment(name) == "main")


def _environments_declared(repo: Repo) -> bool:
    """Whether common.yaml declares any environment at all."""
    return bool(repo.cfg.get("environments"))


def _inputs_of_roots(repo: Repo, filename: str) -> Iterator[Inputs]:
    """For each root that has the file: (root, path, its data, None), or (root, path, None, the YAML error)."""
    for root in repo.roots():
        path = filename if root == "." else os.path.join(root, filename)
        if not repo.exists(path):
            continue
        try:
            data = yaml.safe_load(repo.text(path))
        except yaml.YAMLError as error:
            yield root, path, None, str(error).splitlines()[0]
            continue
        yield root, path, data if isinstance(data, dict) else {}, None


@check("root_not_in_an_environment")
def root_not_in_an_environment(repo: Repo, rule: dict) -> List[Finding]:
    """ROOT-003: a root that has an inputs.yaml is listed under no environment of `terraform.environments`."""
    findings: List[Finding] = []
    if not _environments_declared(repo):
        return findings
    for root, path, data, _error in _inputs_of_roots(repo, rule["file"]):
        if data is not None and _environment_of_root(repo, root) is None:
            findings.append(make_finding(rule, "{} is not listed under any environment of terraform.environments in common.yaml.".format(root), path, 1, root))
    return findings


@check("root_tags_invalid")
def root_tags_invalid(repo: Repo, rule: dict) -> List[Finding]:
    """ROOT-004: the `tags` of a root lack the owner or the cost center, or set a tag that common.yaml owns."""
    findings = []
    for root, path, data, error in _inputs_of_roots(repo, rule["file"]):
        if data is None:
            findings.append(make_finding(rule, "{} is not valid YAML: {}".format(path, error), path, 1))
            continue
        problems = []
        tags = data.get("tags")
        if not isinstance(tags, dict):
            problems.append("`tags` must be a block with " + ", ".join(rule["required_tags"]))
        else:
            missing = [key for key in rule["required_tags"] if not str(tags.get(key) or "").strip()]
            if missing:
                problems.append("`tags` has no value for " + ", ".join(missing))
            owned = [key for key in rule["common_tags"] if key in tags]
            if owned:
                problems.append("`tags` sets {}, which common.yaml decides for every root".format(", ".join(owned)))
        if problems:
            findings.append(make_finding(rule, "{}: {}.".format(path, "; ".join(problems)), path, 1, root))
    return findings


def _values_at(data: Any, path: str) -> List[Any]:
    """The values found at a dotted path of the data. A `*` step goes through every value of a mapping (or item of a list)."""
    found = [data]
    for step in path.split("."):
        next_found: List[Any] = []
        for item in found:
            if step == "*":
                next_found.extend(item.values() if isinstance(item, dict) else item if isinstance(item, list) else [])
            elif isinstance(item, dict) and step in item:
                next_found.append(item[step])
        found = next_found
    return found


def _unmet(data: Dict[str, Any], requirement: Dict[str, Any]) -> Optional[str]:
    """Why a requirement is not met (None when it is). A requirement has a `path` and one test: equals, any_equals, at_least or count_at_least."""
    path = requirement["path"]
    values = _values_at(data, path)
    if not values:
        return "`{}` is not set".format(path)
    if "equals" in requirement and values[0] != requirement["equals"]:
        return "`{}` is {!r}, it must be {!r}".format(path, values[0], requirement["equals"])
    if "any_equals" in requirement and requirement["any_equals"] not in values:
        return "no `{}` is {!r}".format(path, requirement["any_equals"])
    if "at_least" in requirement and not (isinstance(values[0], (int, float)) and values[0] >= requirement["at_least"]):
        return "`{}` is {!r}, it must be at least {}".format(path, values[0], requirement["at_least"])
    if "count_at_least" in requirement:
        size = len(values[0]) if isinstance(values[0], (dict, list)) else 0
        if size < requirement["count_at_least"]:
            return "`{}` has {} item(s), it needs at least {}".format(path, size, requirement["count_at_least"])
    return None


@check("production_requirements_not_met")
def production_requirements_not_met(repo: Repo, rule: dict) -> List[Finding]:
    """POLICY-001: a root that belongs to a production environment does not meet a requirement of the catalog."""
    findings = []
    for root, path, data, _error in _inputs_of_roots(repo, rule["file"]):
        environment = _environment_of_root(repo, root)
        if environment is None or not environment[1]:
            continue
        for requirement in rule["requirements"]:
            reason = _unmet(data or {}, requirement)
            if reason:
                findings.append(make_finding(rule, "{}: {} ({}).".format(path, reason, requirement["why"]), path, 1, root))
    return findings
