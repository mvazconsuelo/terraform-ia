"""Summarise `terraform show -json` output. State, variables and sensitive values are dropped."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .sanitize import sanitize_value

# Attributes worth showing the reviewer; everything else is omitted to limit size and exposure.
INTERESTING = {
    "tags", "tags_all", "instance_types", "capacity_type", "scaling_config", "version", "engine_version",
    "instance_class", "allocated_storage", "multi_az", "storage_encrypted", "deletion_protection",
    "publicly_accessible", "endpoint_public_access", "vpc_config", "cidr_block", "name", "bucket",
    "load_balancer_type", "internal", "ami_type", "disk_size", "force_destroy",
}


def summarize_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce `terraform show -json` to counts and a sanitized list of changes. State and sensitive values are
    dropped."""
    changes: List[Dict[str, Any]] = []
    counts = {"create": 0, "update": 0, "delete": 0, "replace": 0}
    for rc in plan.get("resource_changes", []):
        ch = rc.get("change", {})
        actions = ch.get("actions", [])
        if actions in (["no-op"], ["read"]):
            continue
        replace = "delete" in actions and "create" in actions
        if replace:
            counts["replace"] += 1
        else:
            for a in ("create", "update", "delete"):
                if a in actions:
                    counts[a] += 1
        after = sanitize_value(ch.get("after") or {}, ch.get("after_sensitive"))
        entry = {
            "address": rc.get("address"),
            "type": rc.get("type"),
            "actions": actions,
            "replace": replace,
            "replace_paths": ch.get("replace_paths", []),
            "after": {k: v for k, v in (after or {}).items() if k in INTERESTING and v not in (None, [], {})},
        }
        if isinstance(entry["after"].get("tags"), dict):
            entry["tag_keys"] = sorted(entry["after"]["tags"])
        changes.append(entry)
    return {
        "terraform_version": plan.get("terraform_version"),
        "counts": counts,
        "resource_changes": changes,
        "variable_names": sorted((plan.get("variables") or {}).keys()),  # names only, never values
    }


def load_plan(path: str) -> Dict[str, Any]:
    """Accepts a raw `terraform show -json` file or an already sanitized summary (as produced by `plan-summary`)."""
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if "resource_changes" in doc and "counts" not in doc:
        return summarize_plan(doc)
    return doc
