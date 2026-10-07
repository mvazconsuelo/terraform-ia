"""The AI step: build the controlled payload, ask the model, validate the answer against schema.json, ground the text.

Gemini only interprets evidence that code already produced. Its answer is text for the PR comment: it carries no
findings and no decision, and it never touches the pass/fail verdict.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..model import Finding
from ..repo import Repo
from ..sanitize import is_blocked, sanitize_text, sanitize_tree
from .client import AIClient, AIError
from .grounding import allowed_amounts, evidence_corpus, file_exists, ground_text

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "schema.json"
PROMPT_PATH = HERE / "prompt.md"

MAX_FILE_BYTES = 40_000
MAX_TOTAL_BYTES = 250_000
MAX_PR_BODY = 4_000
TEXT_SUFFIXES = (".tf", ".hcl", ".yaml", ".yml", ".md", ".json", ".tftpl")


class AIReviewError(AIError):
    pass


def load_schema() -> Dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


# ----------------------------------------------------------------------------------------------------------------
# Evidence and payload: only what the review needs, sanitized. No repository dump, no state, no credentials.
# ----------------------------------------------------------------------------------------------------------------
def build_evidence(
    root: str,
    changed: List[Dict[str, str]],
    findings: List[Finding],
    plans: Dict[str, Dict[str, Any]],
    costs: Dict[str, Dict[str, Any]],
    checks: Dict[str, str],
    pr: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    total = 0
    skipped: List[str] = []
    for entry in changed:
        path = entry["path"]
        if is_blocked(path):
            skipped.append(path + " (blocked: sensitive file type)")
            continue
        if entry["status"] == "deleted":
            files.append({"path": path, "status": "deleted"})
            continue
        if not path.endswith(TEXT_SUFFIXES):
            skipped.append(path + " (non-text)")
            continue
        full = os.path.join(root, path)
        if not os.path.isfile(full):
            continue
        with open(full, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        truncated = len(text) > MAX_FILE_BYTES
        text = sanitize_text(text[:MAX_FILE_BYTES])
        if total + len(text) > MAX_TOTAL_BYTES:
            skipped.append(path + " (context budget exceeded)")
            continue
        total += len(text)
        files.append({"path": path, "status": entry["status"], "truncated": truncated, "content": text})

    pull_request = None
    if pr and (pr.get("title") or pr.get("body")):
        pull_request = {
            "title": sanitize_text((pr.get("title") or "")[:300]),
            "description": sanitize_text((pr.get("body") or "")[:MAX_PR_BODY]),
        }
    return {
        "pull_request": pull_request,
        "checks": checks or {},
        "changed_files": files,
        "skipped_files": skipped,
        "deterministic_findings": [f.to_dict() for f in findings],
        "plans": plans or {},
        "costs": costs or {},
    }


def repository_context(rules: List[dict]) -> Dict[str, Any]:
    """What the repository is. The mandatory tags come from the governance rule, the single source of truth."""
    tags = next((r.get("mandatory_tags", []) for r in rules if r.get("id") == "GOV-001"), [])
    return {
        "purpose": (
            "Terraform module engineering repository: reusable AWS modules, the Terraform root configurations built from "
            "them, and a pull-request reviewer (tools/reviewer/) that enforces the repository contract."
        ),
        "principles": [
            "Reusable capabilities are implemented as modules; root configurations only consume modules.",
            "Every taggable AWS resource carries the mandatory tags.",
            "Each root configuration has its own state and is planned on its own.",
            "Destroying or replacing stateful resources in a protected configuration requires explicit human review.",
            "Code decides pass or fail; the reviewer is advisory.",
        ],
        "governance": {"required_tags": list(tags)},
    }


def architecture_context(root: str, changed_paths: List[str]) -> Dict[str, Any]:
    """How this repository is organised, derived from its own sources by the same discovery the workflows use."""
    repo = Repo(root)
    modules = set(repo.module_dirs())
    configurations = {
        r: {
            "protected": repo.is_protected(r),
            "modules_used": sorted(d for d in repo.closure(r) if d in modules),
        }
        for r in repo.roots()
    }
    return {
        "configuration_model": (
            "A root configuration is a folder with its own Terraform state that is planned and applied on its own. "
            "Only the configurations affected by a change are planned; a change to a shared module affects every "
            "configuration that uses it."
        ),
        "configurations": configurations,
        "affected_configurations": repo.affected(changed_paths),
        "module_domains": sorted({repo.module_relpath(d).split("/")[0] for d in modules}),
    }


def replacements(plans: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resources the plan destroys and recreates, with the attributes that force it (a deterministic fact)."""
    out: List[Dict[str, Any]] = []
    for env, plan in sorted((plans or {}).items()):
        for rc in plan.get("resource_changes", []):
            if rc.get("replace"):
                out.append({
                    "configuration": env,
                    "address": rc.get("address"),
                    "type": rc.get("type"),
                    "forced_by": [".".join(map(str, p)) if isinstance(p, list) else str(p) for p in rc.get("replace_paths") or []],
                })
    return out


def build_payload(root: str, evidence: Dict[str, Any], rules: List[dict]) -> Dict[str, Any]:
    return {
        "repository_context": repository_context(rules),
        "architecture_context": architecture_context(root, [c["path"] for c in evidence["changed_files"]]),
        "pull_request": evidence["pull_request"],
        "changed_files": evidence["changed_files"],
        "plan": evidence["plans"],
        "replacements": replacements(evidence["plans"]),
        "cost": evidence["costs"],
        "checks": evidence["checks"],
        "deterministic_findings": evidence["deterministic_findings"],
    }


# ----------------------------------------------------------------------------------------------------------------
# Asking, validating, grounding
# ----------------------------------------------------------------------------------------------------------------
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def validate(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """Minimal JSON Schema validator (type, enum, required, properties, additionalProperties, minLength, items)."""
    errs: List[str] = []
    if "enum" in schema and value not in schema["enum"]:
        return ["{} must be one of {}".format(path, schema["enum"])]
    t = schema.get("type")
    if t:
        ok = isinstance(value, _TYPES[t]) if t in _TYPES else False
        if t == "integer":
            ok = isinstance(value, int) and not isinstance(value, bool)
        if not ok:
            return ["{} must be {}".format(path, t)]
    if isinstance(value, str) and len(value.strip()) < schema.get("minLength", 0):
        errs.append("{} must not be empty".format(path))
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                errs.append("{}.{} is required".format(path, k))
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                errs += validate(v, props[k], "{}.{}".format(path, k))
            elif schema.get("additionalProperties") is False:
                errs.append("{}.{} is not allowed".format(path, k))
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errs += validate(item, schema["items"], "{}[{}]".format(path, i))
    return errs


def ask(client: AIClient, payload: Dict[str, Any], system_prompt: Optional[str] = None, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One call plus a single retry when the answer is not valid JSON or does not match schema.json."""
    system = system_prompt if system_prompt is not None else load_prompt()
    schema = schema or load_schema()
    # defence in depth: nothing that looks like a credential leaves, even if an upstream step missed it
    user = json.dumps(sanitize_tree(payload), indent=1)
    errors: List[str] = []
    for _ in range(2):
        prompt = user if not errors else user + "\n\nYour previous answer was invalid: {}. Return the corrected JSON only.".format("; ".join(errors[:6]))
        raw = client.generate(system, prompt)
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            errors = ["not valid JSON: {}".format(e)]
            continue
        errors = validate(obj, schema)
        if not errors:
            return obj
    raise AIReviewError("AI answer failed schema validation: {}".format("; ".join(errors[:6])))


def review(
    client: AIClient,
    root: str,
    changed: List[Dict[str, str]],
    findings: List[Finding],
    plans: Dict[str, Dict[str, Any]],
    costs: Dict[str, Dict[str, Any]],
    checks: Dict[str, str],
    pr: Optional[Dict[str, str]],
    rules: List[dict],
    affected: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """The whole AI step. Every piece of free text is grounded against the evidence; unverifiable references are removed."""
    evidence = build_evidence(root, changed, findings, plans, costs, checks, pr)
    raw = ask(client, build_payload(root, evidence, rules))
    corpus, amounts, exists = evidence_corpus(evidence), allowed_amounts(costs), file_exists(root)
    notes: List[str] = []

    def clean(text: str) -> str:
        out, n = ground_text(text, corpus, amounts, exists)
        notes.extend(n)
        return out or ""

    return {
        "intent_vs_infrastructure": {
            "status": raw["intent_vs_infrastructure"]["status"],
            "explanation": clean(raw["intent_vs_infrastructure"]["explanation"]),
        },
        "architecture_impact": {
            "severity": raw["architecture_impact"]["severity"],
            "explanation": clean(raw["architecture_impact"]["explanation"]),
        },
        "reviewer_summary": clean(raw["reviewer_summary"]),
        "grounding_notes": sorted(set(notes)),
    }
