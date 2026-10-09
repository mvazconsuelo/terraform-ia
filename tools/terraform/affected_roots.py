"""Which root configurations a change affects, for a target branch.

This is the decision the workflows rely on: only the roots returned here are planned, reviewed and applied.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .terraform_map import Repo, glob_match, slug


def for_branch(repo: Repo, roots: List[Dict[str, Any]], branch: Optional[str]) -> List[Dict[str, Any]]:
    """Keep only the roots the branch is allowed to act on.

    A branch may act on the roots of the environments that name it in `terraform.environments` (common.yaml), e.g. develop -> dev.
    A branch that no environment names (or no branch at all) keeps every root."""
    allowed_patterns = repo.roots_of_branch(branch) if branch else None
    if allowed_patterns is None:
        return roots

    kept = []
    for root in roots:
        if any(glob_match(pattern, root["root"]) for pattern in allowed_patterns):
            kept.append(root)
    return kept


def discover(repo: Repo, changed: Optional[List[str]], branch: Optional[str] = None) -> List[Dict[str, Any]]:
    """The roots to act on, each as {"root": folder, "slug": file-safe name, "reasons": why it is affected}.

    `changed` is the list of changed file paths; None means "every root". With a `branch`, only the roots that branch owns
    are returned, so a PR into develop never plans or applies the production roots."""
    if changed is None:
        affected = [{"root": root, "reasons": ["all configurations requested"]} for root in repo.roots()]
    else:
        affected = repo.affected(changed)

    return [
        {"root": item["root"], "slug": slug(item["root"]), "reasons": item["reasons"]}
        for item in for_branch(repo, affected, branch)
    ]
