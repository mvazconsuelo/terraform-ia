"""The AI step: build a controlled payload, ask the model, validate its answer, and check what it says against the evidence.

Gemini only interprets evidence that code already produced. Its answer is text for the PR comment: it carries no findings
and no decision, and it can never change the pass/fail verdict. The steps, in order:

  1. `build_evidence`  gather what the model may see: the evidence of the review, never the source files;
  2. `build_payload`   arrange it, together with the final verdict, into the one JSON document the model receives;
  3. `ask`             send it and validate the answer against schema.json (one retry if the answer is invalid);
  4. `review`          check every address, file and price in the answer against the evidence (see grounding.py).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..lib.redact_secrets import sanitize_text, sanitize_tree
from ..review.finding import Finding
from ..terraform.terraform_map import Repo
from .client import AIClient, AIError
from .grounding import allowed_amounts, evidence_corpus, file_exists, ground_text

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "schema.json"       # the contract of the answer
PROMPT_PATH = HERE / "prompt.md"         # the instructions given to the model

MAX_PR_BODY = 4_000      # the PR description is cut here, so the payload stays small


class AIReviewError(AIError):
    """The model's answer could not be used: invalid JSON, or it failed the schema twice."""


def load_schema() -> Dict[str, Any]:
    """Read ai/schema.json, the contract of the AI answer."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_prompt() -> str:
    """Read ai/prompt.md, the system prompt."""
    return PROMPT_PATH.read_text(encoding="utf-8")


# ----------------------------------------------------------------------------------------------------------------
# 1. Evidence: only what the review needs, sanitized. No repository dump, no state, no credentials.
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
    """Collect what the AI may see: the list of changed files (path and status, never their contents), the PR text, the
    checks, the findings, the plans and the costs. The AI reads the evidence the review produced, not the source code."""
    pull_request = None
    if pr and (pr.get("title") or pr.get("body")):
        pull_request = {
            "title": sanitize_text((pr.get("title") or "")[:300]),
            "description": sanitize_text((pr.get("body") or "")[:MAX_PR_BODY]),
        }
    return {
        "pull_request": pull_request,
        "checks": checks or {},
        "changed_files": [{"path": item["path"], "status": item.get("status", "modified")} for item in changed],
        "deterministic_findings": [finding.to_dict() for finding in findings],
        "plans": plans or {},
        "costs": costs or {},
    }


# ----------------------------------------------------------------------------------------------------------------
# 2. Payload: the one document the model receives
# ----------------------------------------------------------------------------------------------------------------
def repository_context(rules: List[dict]) -> Dict[str, Any]:
    """What the repository is. The mandatory tags come from the governance rule, the single source of truth."""
    tags: List[str] = next((rule.get("mandatory_tags", []) for rule in rules if rule.get("id") == "TAGS-001"), [])
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

    configurations = {}
    for configuration in repo.roots():
        configurations[configuration] = {
            "protected": repo.is_protected(configuration),
            "modules_used": sorted(folder for folder in repo.closure(configuration) if folder in modules),
        }
    return {
        "configuration_model": (
            "A root configuration is a folder with its own Terraform state that is planned and applied on its own. "
            "Only the configurations affected by a change are planned; a change to a shared module affects every "
            "configuration that uses it."
        ),
        "configurations": configurations,
        "affected_configurations": repo.affected(changed_paths),
        "module_domains": sorted({repo.module_relpath(module).split("/")[0] for module in modules}),
    }


def replacements(plans: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The resources the plan destroys and recreates, with the attributes that force it (a deterministic fact)."""
    replaced: List[Dict[str, Any]] = []
    for configuration, plan in sorted((plans or {}).items()):
        for change in plan.get("resource_changes", []):
            if not change.get("replace"):
                continue
            forcing = change.get("replace_paths") or []
            replaced.append({
                "configuration": configuration,
                "address": change.get("address"),
                "type": change.get("type"),
                "forced_by": [".".join(map(str, path)) if isinstance(path, list) else str(path) for path in forcing],
            })
    return replaced


def build_payload(
    root: str,
    evidence: Dict[str, Any],
    rules: List[dict],
    affected: Optional[List[Dict[str, Any]]] = None,
    verdict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Everything the deterministic review produced, so the summary can cover all of it.

    `affected` is the list of roots the pipeline actually acted on (already limited to the target branch); `verdict` is the
    final risk and decision, which the model must report as given."""
    architecture = architecture_context(root, [item["path"] for item in evidence["changed_files"]])
    if affected is not None:
        architecture["affected_configurations"] = affected

    payload: Dict[str, Any] = {}
    if verdict:
        findings = evidence["deterministic_findings"]
        payload["review"] = {
            "risk": verdict.get("risk"),
            "decision": verdict.get("decision"),
            "decision_reasons": verdict.get("reasons") or [],
            "target": verdict.get("target"),
            "rules_evaluated": len(rules),
            "rules_violated": len([finding for finding in findings if finding.get("rule_id")]),
        }
    payload.update({
        "repository_context": repository_context(rules),
        "architecture_context": architecture,
        "pull_request": evidence["pull_request"],
        "changed_files": evidence["changed_files"],
        "checks": evidence["checks"],
        "plan": evidence["plans"],
        "replacements": replacements(evidence["plans"]),
        "cost": evidence["costs"],
        "deterministic_findings": evidence["deterministic_findings"],
    })
    return payload


# ----------------------------------------------------------------------------------------------------------------
# 3. Asking and validating
# ----------------------------------------------------------------------------------------------------------------
_JSON_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def validate(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """A small JSON Schema validator: type, enum, required, properties, additionalProperties, minLength and items.

    Returns the list of problems found (empty when the value matches). `path` names where in the document a problem is."""
    problems: List[str] = []

    if "enum" in schema and value not in schema["enum"]:
        return ["{} must be one of {}".format(path, schema["enum"])]

    expected_type = schema.get("type")
    if expected_type:
        if expected_type == "integer":
            type_ok = isinstance(value, int) and not isinstance(value, bool)
        else:
            type_ok = isinstance(value, _JSON_TYPES[expected_type]) if expected_type in _JSON_TYPES else False
        if not type_ok:
            return ["{} must be {}".format(path, expected_type)]

    if isinstance(value, str) and len(value.strip()) < schema.get("minLength", 0):
        problems.append("{} must not be empty".format(path))

    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                problems.append("{}.{} is required".format(path, name))
        properties = schema.get("properties", {})
        for name, item in value.items():
            if name in properties:
                problems += validate(item, properties[name], "{}.{}".format(path, name))
            elif schema.get("additionalProperties") is False:
                problems.append("{}.{} is not allowed".format(path, name))

    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            problems += validate(item, schema["items"], "{}[{}]".format(path, index))
    return problems


def ask(client: AIClient, payload: Dict[str, Any], system_prompt: Optional[str] = None, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Send the payload and return the validated answer. One call, plus a single retry if the answer is not valid JSON or
    does not match schema.json (the retry tells the model what was wrong)."""
    system = system_prompt if system_prompt is not None else load_prompt()
    schema = schema or load_schema()
    # Defence in depth: nothing that looks like a credential leaves, even if an earlier step missed it.
    user_text = json.dumps(sanitize_tree(payload), indent=1)

    problems: List[str] = []
    for _attempt in range(2):
        prompt = user_text
        if problems:
            prompt += "\n\nYour previous answer was invalid: {}. Return the corrected JSON only.".format("; ".join(problems[:6]))
        raw_answer = client.generate(system, prompt)

        try:
            answer = json.loads(raw_answer)
        except (json.JSONDecodeError, TypeError) as error:
            problems = ["not valid JSON: {}".format(error)]
            continue
        problems = validate(answer, schema)
        if not problems:
            return answer
    raise AIReviewError("AI answer failed schema validation: {}".format("; ".join(problems[:6])))


# ----------------------------------------------------------------------------------------------------------------
# 4. The whole step
# ----------------------------------------------------------------------------------------------------------------
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
    verdict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """The whole AI step. Returns {"summary": ..., "grounding_notes": [...]}.

    The summary is checked against the evidence: addresses, files and prices that cannot be verified are replaced by a
    marker, and a note says what was removed."""
    evidence = build_evidence(root, changed, findings, plans, costs, checks, pr)
    answer = ask(client, build_payload(root, evidence, rules, affected, verdict))

    corpus = evidence_corpus(evidence)
    amounts = allowed_amounts(costs)
    path_exists = file_exists(root)
    summary, notes = ground_text(answer["summary"], corpus, amounts, path_exists)
    return {"summary": summary or "", "grounding_notes": sorted(set(notes))}
