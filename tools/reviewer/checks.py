"""The organisation's deterministic checks: the repository contract and the terraform plan.

Each check is `fn(repo, rule) -> list[Finding]` and is selected by the `check:` key of a
rule in rules.yaml. These checks enforce the *module engineering contract*;
generic security/format scanning stays with Checkov/tfsec/terraform fmt.
"""
from __future__ import annotations

import os
import re
from typing import Callable, Dict, List

from .model import Finding
from .repo import Repo, glob_match

Check = Callable[[Repo, dict], List[Finding]]
REGISTRY: Dict[str, Check] = {}


def check(name: str):
    """Decorator: register a contract check under the name that `check:` in rules.yaml refers to."""
    def deco(fn: Check) -> Check:
        REGISTRY[name] = fn
        return fn

    return deco


def _f(rule: dict, evidence: str, file=None, line=None, resource=None, **over) -> Finding:
    """Build a Finding from a rule's metadata and the evidence of one violation."""
    data = dict(
        severity=rule["severity"],
        category=rule["category"],
        title=rule["title"],
        evidence=evidence,
        explanation=" ".join(str(rule.get("explanation", "")).split()),
        recommendation=rule.get("recommendation", ""),
        file=file,
        line=line,
        resource=resource,
        rule_id=rule["id"],
    )
    data.update(over)
    return Finding(**data)


def _module_of(path: str) -> str:
    """Folder that contains a file."""
    return os.path.dirname(path)


def _in(path: str, prefixes: List[str]) -> bool:
    """True when the path starts with any of the prefixes."""
    return any(path.startswith(p) for p in prefixes)


@check("reusable_capability_outside_module")
def reusable_capability_outside_module(repo: Repo, rule: dict) -> List[Finding]:
    """MOD-001: a resource type that has a module is declared in a folder that is not a module."""
    out = []
    caps = rule["capabilities"]
    for b in repo.all_blocks("resource"):
        if b.type in caps and not repo.is_module_dir(_module_of(b.file)):
            out.append(_f(
                rule,
                "{} is declared directly in {}; {} owns this capability.".format(b.address, b.file, caps[b.type]),
                b.file, b.line, b.address,
                recommendation="Consume {} (creating it first if it does not exist yet) instead of declaring {} directly.".format(caps[b.type], b.type),
                expected=caps[b.type] + "/",
            ))
    return out


@check("module_required_files")
def module_required_files(repo: Repo, rule: dict) -> List[Finding]:
    """MOD-002: each module has the files and folders the contract requires."""
    out = []
    for d in repo.module_dirs():
        missing = [f for f in rule["required"] if not repo.exists(os.path.join(d, f))]
        missing += [x + "/" for x in rule["required_dirs"] if not repo.exists(os.path.join(d, x))]
        if missing:
            anchor = repo.files_in(d)[0]
            out.append(_f(rule, "{} is missing: {}.".format(d, ", ".join(missing)), anchor, 1))
    return out


_ARBITRARY_NAME_RE = re.compile(r"(^|_)(my|prod|production|dev|staging|stage|test|foo|bar|main|default|example)(_|$)|\d{2,}")


def _arbitrary_name(rtype: str, name: str) -> bool:
    """`this` and role names (public, private, nat, s3) are fine; env/arbitrary/type-echo names are not."""
    if name == "this":
        return False
    type_words = set(rtype.replace("aws_", "").split("_"))
    return bool(_ARBITRARY_NAME_RE.search(name)) or name in type_words or name == rtype.replace("aws_", "")


@check("primary_resource_naming")
def primary_resource_naming(repo: Repo, rule: dict) -> List[Finding]:
    """MOD-003: resources are named `this` or by role, not arbitrarily (`my_bucket`, `prod_bucket`, `bucket123`)."""
    out = []
    for d in repo.module_dirs():
        by_type: Dict[str, list] = {}
        for rel in repo.files_in(d):
            for b in repo.blocks(rel):
                if b.kind == "resource":
                    by_type.setdefault(b.type, []).append(b)
        for rtype, items in by_type.items():
            for b in items:
                if len(items) == 1 and b.name != "this" and _arbitrary_name(rtype, b.name):
                    out.append(_f(rule, "{} is the only {} in {} and has an arbitrary name; expected `this`.".format(b.address, rtype, d), b.file, b.line, b.address))
                elif len(items) > 1 and _arbitrary_name(rtype, b.name):
                    out.append(_f(rule, "{} has an arbitrary name; use a role-based name (e.g. `public`, `private`).".format(b.address), b.file, b.line, b.address))
    return out


@check("no_any_type")
def no_any_type(repo: Repo, rule: dict) -> List[Finding]:
    """MOD-004: no variable declares `type = any`."""
    out = []
    for b in repo.all_blocks("variable"):
        t = b.attrs.get("type", "")
        if re.search(r"\bany\b", t):
            out.append(_f(rule, 'variable "{}" declares type = {}.'.format(b.name, t.split("\n")[0]), b.file, b.line, "variable." + b.name))
    return out


@check("eks_domain_layout")
def eks_domain_layout(repo: Repo, rule: dict) -> List[Finding]:
    """MOD-006: components live under their domain folder (eks/, ec2/, elb/), not as top-level eks-*, ec2-* or
    elb-* modules."""
    out = []
    seen = set()
    for d in repo.module_dirs():
        top = repo.module_relpath(d).split("/")[0]
        if top not in seen and any((top + "/").startswith(pre) for pre in rule["forbidden_prefixes"]):
            seen.add(top)
            out.append(_f(rule, "{} should live inside its domain directory (<modules>/<domain>/<component>).".format(d), repo.files_in(d)[0], 1))
    return out


def _tag_contract_ok(expr: str, module_text: str, mandatory: List[str]) -> bool:
    """True when a `tags` expression carries every mandatory tag: it uses local.tags and the module defines each
    tag, or it lists them itself."""
    if re.search(r"\blocal\.(tags|mandatory_tags|common_tags)\b", expr):
        return all(re.search(r"\b%s\b" % k, module_text) for k in mandatory)
    return all(re.search(r"\b%s\b" % k, expr) for k in mandatory)


@check("missing_mandatory_tags")
def missing_mandatory_tags(repo: Repo, rule: dict) -> List[Finding]:
    """GOV-001: every taggable resource in a module has a `tags` argument that carries the mandatory tags."""
    out = []
    taggable = set(rule["taggable_types"])
    mandatory = rule["mandatory_tags"]
    for d in repo.module_dirs():
        files = repo.files_in(d)
        text = "\n".join(repo.text(f) for f in files)
        for rel in files:
            for b in repo.blocks(rel):
                if b.kind != "resource" or b.type not in taggable:
                    continue
                expr = b.attrs.get("tags")
                if expr is None:
                    out.append(_f(rule, "{} has no `tags` argument.".format(b.address), b.file, b.line, b.address))
                elif not _tag_contract_ok(expr, text, mandatory):
                    out.append(_f(rule, "{} tags do not include all of: {}.".format(b.address, ", ".join(mandatory)), b.file, b.line, b.address))
    return out


@check("tag_variable_contract")
def tag_variable_contract(repo: Repo, rule: dict) -> List[Finding]:
    """GOV-002: a module that creates taggable resources declares the `tags` and `extra_tags` variables."""
    out = []
    taggable = set(rule["_rules"]["GOV-001"]["taggable_types"])
    for d in repo.module_dirs():
        blocks = [b for f in repo.files_in(d) for b in repo.blocks(f)]
        if not any(b.kind == "resource" and b.type in taggable for b in blocks):
            continue
        have = {b.name for b in blocks if b.kind == "variable"}
        missing = [v for v in ("tags", "extra_tags") if v not in have]
        if missing:
            out.append(_f(rule, "{} creates taggable resources but lacks variable(s): {}.".format(d, ", ".join(missing)), repo.files_in(d)[0], 1))
    return out


@check("module_has_tests")
def module_has_tests(repo: Repo, rule: dict) -> List[Finding]:
    """TF-003: each module has `tests/*.tftest.hcl`."""
    out = []
    for d in repo.module_dirs():
        tdir = os.path.join(d, "tests")
        if repo.exists(tdir) and not any(f.endswith(".tftest.hcl") for f in repo.listdir(tdir)):
            out.append(_f(rule, "{} exists but contains no *.tftest.hcl files.".format(tdir), repo.files_in(d)[0], 1))
    return out


@check("eks_asg_forbidden")
def eks_asg_forbidden(repo: Repo, rule: dict) -> List[Finding]:
    """An Auto Scaling Group in the EKS module domain, or in any root configuration, bypasses eks/node-group."""
    out = []
    for b in repo.all_blocks("resource"):
        if b.type != "aws_autoscaling_group":
            continue
        d = _module_of(b.file)
        in_eks = repo.is_module_dir(d) and any((repo.module_relpath(d) + "/").startswith(p) for p in rule["module_paths"])
        if in_eks or d in repo.roots():
            out.append(_f(rule, "{} is declared in {}.".format(b.address, b.file), b.file, b.line, b.address))
    return out


@check("nat_without_justification")
def nat_without_justification(repo: Repo, rule: dict) -> List[Finding]:
    """Only meaningful when the consumer says which roots are protected (terraform.protected in common.yaml)."""
    out = []
    if not repo.cfg["protected"]:
        return out
    for b in repo.all_blocks("module"):
        d = _module_of(b.file)
        if d in repo.roots() and not repo.is_protected(d) and re.search(r'nat_gateway_mode\s*=\s*"per_az"', b.body):
            out.append(_f(rule, "module.{} uses per_az NAT in {}, which is not a protected configuration.".format(b.name, d), b.file, b.line, "module." + b.name, confidence="MEDIUM", type="INFERRED"))
    return out


@check("asg_tag_blocks")
def asg_tag_blocks(repo: Repo, rule: dict) -> List[Finding]:
    """GOV-003: Auto Scaling Groups use `tag` blocks with propagate_at_launch = true for the mandatory tags."""
    out = []
    for d in repo.module_dirs():
        files = repo.files_in(d)
        text = "\n".join(repo.text(f) for f in files)
        for rel in files:
            for b in repo.blocks(rel):
                if b.kind != "resource" or b.type != "aws_autoscaling_group":
                    continue
                has_tag_block = re.search(r'^\s*(dynamic\s+"tag"|tag)\s*\{', b.body, re.MULTILINE)
                propagates = "propagate_at_launch" in b.body and re.search(r"propagate_at_launch\s*=\s*true", b.body)
                keys_ok = all(re.search(r"\b%s\b" % k, text) for k in rule["mandatory_tags"])
                if not (has_tag_block and propagates and keys_ok):
                    out.append(_f(rule, "{} has no `tag` blocks with propagate_at_launch = true for the mandatory tags.".format(b.address), b.file, b.line, b.address))
    return out


_GENERATED_FILES = {"backend.tf", "tests", ".terraform", ".terraform.lock.hcl", "tfplan"}
_FORBIDDEN_IN_ROOT_MAIN = (
    (re.compile(r'^\s*provider\s+"', re.MULTILINE), "declares a provider block"),
    (re.compile(r"^\s*required_providers\s*\{", re.MULTILINE), "declares required_providers"),
    (re.compile(r'^\s*backend\s+"', re.MULTILINE), "declares a backend"),
)


def _layout(repo: Repo):
    """Roots that opt in to a layout through terraform.conventions.layout in common.yaml; none when it is not configured."""
    conv = (repo.cfg["conventions"] or {}).get("layout") or {}
    if not conv:
        return conv, []
    return conv, [r for r in repo.roots() if any(glob_match(g, r) for g in conv.get("roots", []))]


@check("root_layout")
def root_layout(repo: Repo, rule: dict) -> List[Finding]:
    """TF-004 (opt-in): roots matched by terraform.conventions.layout hold only the listed files and templates, and
    their main.tf declares no provider, required_providers or backend."""
    conv, roots = _layout(repo)
    out = []
    files = conv.get("files", [])
    suffixes = tuple(conv.get("template_suffixes", []))
    for rel in roots:
        names = set(os.listdir(os.path.join(repo.root, rel)))
        for need in files:
            if need not in names:
                out.append(_f(rule, "{} is missing {}.".format(rel, need), rel + "/" + ("main.tf" if "main.tf" in names else sorted(names)[0]), 1))
        for extra in sorted(names - set(files) - _GENERATED_FILES):
            if suffixes and extra.endswith(suffixes):
                continue  # templates rendered by main.tf (templatefile) live next to it
            out.append(_f(rule, "{}/{} is not allowed: a configuration holds {} and its templates.".format(rel, extra, ", ".join(files)), "{}/{}".format(rel, extra), 1))
        if "main.tf" in names:
            text = repo.text(rel + "/main.tf")
            for pattern, what in _FORBIDDEN_IN_ROOT_MAIN:
                m = pattern.search(text)
                if m:
                    out.append(_f(rule, "{}/main.tf {}; that belongs to the pipeline (AWS_REGION, generated backend) or the modules' constraints.".format(rel, what), rel + "/main.tf", text.count("\n", 0, m.start()) + 1))
    return out


@check("root_files_identical")
def root_files_identical(repo: Repo, rule: dict) -> List[Finding]:
    """The files named in terraform.conventions.layout.identical are byte-identical across the roots of that layout."""
    conv, roots = _layout(repo)
    out = []
    first: Dict[str, tuple] = {}
    patterns = conv.get("identical", [])
    for rel in roots:
        for name in sorted(os.listdir(os.path.join(repo.root, rel))):
            if not any(glob_match(p, name) for p in patterns):
                continue
            path = "{}/{}".format(rel, name)
            text = repo.text(path) if name.endswith(".tf") else open(os.path.join(repo.root, path), encoding="utf-8").read()
            if name not in first:
                first[name] = (path, text)
            elif text != first[name][1]:
                out.append(_f(rule, "{} differs from {}.".format(path, first[name][0]), path, 1))
    return out


# ----------------------------------------------------------------------------------------------------------------
# Plan checks: correlate what terraform WILL do (sanitized plan summary) and the Infracost estimate with the contract.
# They are facts about the plan; the model never decides them.
# ----------------------------------------------------------------------------------------------------------------
PlanCheck = Callable[[Dict[str, dict], Dict[str, dict], dict], List[Finding]]  # plans and costs are keyed by root path
PLAN_REGISTRY: Dict[str, PlanCheck] = {}


def plan_check(name: str):
    """Decorator: register a plan check. It receives the plans and costs keyed by root path."""
    def deco(fn: PlanCheck) -> PlanCheck:
        PLAN_REGISTRY[name] = fn
        return fn

    return deco


@plan_check("plan_stateful_change")
def plan_stateful_change(plans: Dict[str, dict], costs: Dict[str, dict], rule: dict) -> List[Finding]:
    """PLAN-001: the plan destroys or replaces a stateful resource (CRITICAL in a protected root or on a plain
    destroy, HIGH for a replacement elsewhere)."""
    out = []
    stateful = set(rule["stateful_types"])
    protected = rule.get("_protected", lambda root: False)
    for env, plan in sorted(plans.items()):
        for rc in plan.get("resource_changes", []):
            if rc.get("type") not in stateful or "delete" not in rc.get("actions", []):
                continue
            replaced = bool(rc.get("replace"))
            severity = "CRITICAL" if (protected(env) or not replaced) else "HIGH"
            what = "replaced (destroyed and recreated)" if replaced else "destroyed"
            paths = rc.get("replace_paths") or []
            why = " Forcing attributes: {}.".format(", ".join(".".join(str(x) for x in p) if isinstance(p, list) else str(p) for p in paths)) if paths else ""
            out.append(_f(
                rule,
                "{}: {} ({}) will be {}.{}".format(env, rc.get("address"), rc.get("type"), what, why),
                env, None, rc.get("address"), severity=severity,
            ))
    return out


@plan_check("plan_cost_delta")
def plan_cost_delta(plans: Dict[str, dict], costs: Dict[str, dict], rule: dict) -> List[Finding]:
    """PLAN-002: Infracost reports a monthly increase above the rule's threshold."""
    out = []
    limit = float(rule["monthly_delta_usd"])
    for env, cost in sorted(costs.items()):
        delta = cost.get("monthly_delta")
        if delta is not None and delta > limit:
            out.append(_f(
                rule,
                "{}: Infracost estimates {:+,.0f} {}/month (threshold {:,.0f}); current {} -> proposed {}.".format(
                    env, delta, cost.get("currency", "USD"), limit, cost.get("current_monthly_cost"), cost.get("proposed_monthly_cost")),
                env, None, None,
            ))
    return out


def run_plan_checks(plans: Dict[str, dict], costs: Dict[str, dict], rules: List[dict], protected: Callable[[str], bool] = lambda root: False) -> List[Finding]:
    """Run every plan check (PLAN-*). `protected(root)` says whether a root is protected."""
    findings: List[Finding] = []
    for rule in rules:
        fn = PLAN_REGISTRY.get(rule.get("check", ""))
        if fn is not None:
            findings.extend(fn(plans, costs, dict(rule, _protected=protected)))
    return findings
