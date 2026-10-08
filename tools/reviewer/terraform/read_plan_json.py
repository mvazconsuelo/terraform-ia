"""Summarise `terraform show -json`: what will change, without state, variable values or sensitive data.

A raw plan can hold secrets (passwords, keys), so it never leaves the job that ran it. This module turns it into the small,
sanitized summary that the review, the report and the AI read.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from ..redact_secrets import sanitize_value

# The attributes worth showing a reviewer. Everything else is left out, to keep the summary small and to expose less.
INTERESTING = {
    "tags", "tags_all", "instance_types", "capacity_type", "scaling_config", "version", "engine_version",
    "instance_class", "allocated_storage", "multi_az", "storage_encrypted", "deletion_protection",
    "publicly_accessible", "endpoint_public_access", "vpc_config", "cidr_block", "name", "bucket",
    "load_balancer_type", "internal", "ami_type", "disk_size", "force_destroy",
}


def _is_empty(value: Any) -> bool:
    """Whether an attribute value carries no information (None, empty list, empty dict)."""
    return value is None or value == [] or value == {}


def summarize_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce `terraform show -json` to counts and a sanitized list of changes.

    `counts` has create, update, delete and replace. A replacement is a delete plus a create of the same resource, so it is
    counted once, as "replace", and not also as a delete and a create."""
    changes: List[Dict[str, Any]] = []
    counts = {"create": 0, "update": 0, "delete": 0, "replace": 0}

    for resource in plan.get("resource_changes", []):
        change = resource.get("change", {})
        actions = change.get("actions", [])
        if actions in (["no-op"], ["read"]):
            continue                                             # nothing will happen to this resource

        is_replacement = "delete" in actions and "create" in actions
        if is_replacement:
            counts["replace"] += 1
        else:
            for action in ("create", "update", "delete"):
                if action in actions:
                    counts[action] += 1

        # The values the resource will have after the change, with the secrets removed.
        after = sanitize_value(change.get("after") or {}, change.get("after_sensitive")) or {}
        shown = {name: value for name, value in after.items() if name in INTERESTING and not _is_empty(value)}

        entry = {
            "address": resource.get("address"),
            "type": resource.get("type"),
            "actions": actions,
            "replace": is_replacement,
            "replace_paths": change.get("replace_paths", []),    # the attributes that force a replacement
            "after": shown,
        }
        if isinstance(shown.get("tags"), dict):
            entry["tag_keys"] = sorted(shown["tags"])            # only the names of the tags, for the governance check
        changes.append(entry)

    return {
        "terraform_version": plan.get("terraform_version"),
        "counts": counts,
        "resource_changes": changes,
        "variable_names": sorted((plan.get("variables") or {}).keys()),    # names only, never the values
    }


def load_plan(path: str) -> Dict[str, Any]:
    """Read a plan file: either a raw `terraform show -json` (it gets summarized) or a summary already made by `plan-summary`."""
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    is_raw_plan = "resource_changes" in document and "counts" not in document
    return summarize_plan(document) if is_raw_plan else document
