"""The checks that read the code: the .tf files of the repository.

Each function implements one rule of rules.yaml (the catalog). The rule is named in the `@check("...")` decorator; the
docstring says which rule it is. Three families:

  MODULE  how modules are built, and what must not be built outside one   (MODULE-001 .. MODULE-006)
  TAGS    every taggable resource carries the mandatory tags              (TAGS-001 .. TAGS-003)
  ROOT    the layout of a family of roots (their `roots` patterns)        (ROOT-001, ROOT-002, ROOT-005)

A "module" is a folder under `modules/`; a "root" is a folder where Terraform is run.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List

from ..review.finding import Finding
from ..terraform.terraform_map import Repo, glob_match
from .registry import check, folder_of, make_finding, mentions_all

# --------------------------------------------------------------------------------------------------------------------
# MODULE: how modules are built, and what must not be built outside one
# --------------------------------------------------------------------------------------------------------------------

@check("resource_declared_outside_its_module")
def resource_declared_outside_its_module(repo: Repo, rule: dict) -> List[Finding]:
    """MODULE-001: a resource type that has a module is declared in a folder that is not a module."""
    findings = []
    modules_by_type = rule["capabilities"]            # e.g. aws_s3_bucket -> modules/s3
    for block in repo.all_blocks("resource"):
        has_a_module = block.type in modules_by_type
        if has_a_module and not repo.is_module_dir(folder_of(block.file)):
            owner = modules_by_type[block.type]
            findings.append(make_finding(
                rule,
                "{} is declared directly in {}; {} owns this capability.".format(block.address, block.file, owner),
                block.file, block.line, block.address,
                recommendation="Consume {} (creating it first if it does not exist yet) instead of declaring {} directly.".format(owner, block.type),
                expected=owner + "/",
            ))
    return findings


@check("module_missing_required_files")
def module_missing_required_files(repo: Repo, rule: dict) -> List[Finding]:
    """MODULE-002: each module has the files and folders the contract requires."""
    findings = []
    for module in repo.module_dirs():
        missing = [name for name in rule["required"] if not repo.exists(os.path.join(module, name))]
        missing += [name + "/" for name in rule.get("required_dirs", []) if not repo.exists(os.path.join(module, name))]
        if missing:
            first_file = repo.files_in(module)[0]          # a finding needs a file to point at
            findings.append(make_finding(rule, "{} is missing: {}.".format(module, ", ".join(missing)), first_file, 1))
    return findings


# Words that make a resource name arbitrary: environment names, "test", "foo"... or two or more digits (bucket123).
_ARBITRARY_NAME_RE = re.compile(r"(^|_)(my|prod|production|dev|staging|stage|test|foo|bar|main|default|example)(_|$)|\d{2,}")


def _arbitrary_name(resource_type: str, name: str) -> bool:
    """Whether a resource name is arbitrary. `this` and role names (public, private, nat) are fine; environment names
    (prod_bucket), numbers (bucket123) and names that just repeat the type (`bucket` for aws_s3_bucket) are not."""
    if name == "this":
        return False
    type_words = set(resource_type.replace("aws_", "").split("_"))
    repeats_the_type = name in type_words or name == resource_type.replace("aws_", "")
    return bool(_ARBITRARY_NAME_RE.search(name)) or repeats_the_type


@check("resource_has_arbitrary_name")
def resource_has_arbitrary_name(repo: Repo, rule: dict) -> List[Finding]:
    """MODULE-003: resources are named `this` or by role, not arbitrarily (`my_bucket`, `prod_bucket`, `bucket123`)."""
    findings = []
    for module in repo.module_dirs():
        # Group the module's resources by type: the only resource of a type must be `this`; several need role names.
        resources_by_type: Dict[str, list] = {}
        for path in repo.files_in(module):
            for block in repo.blocks(path):
                if block.kind == "resource":
                    resources_by_type.setdefault(block.type, []).append(block)

        for resource_type, resources in resources_by_type.items():
            for block in resources:
                if len(resources) == 1 and block.name != "this" and _arbitrary_name(resource_type, block.name):
                    findings.append(make_finding(
                        rule, "{} is the only {} in {} and has an arbitrary name; expected `this`.".format(block.address, resource_type, module),
                        block.file, block.line, block.address))
                elif len(resources) > 1 and _arbitrary_name(resource_type, block.name):
                    findings.append(make_finding(
                        rule, "{} has an arbitrary name; use a role-based name (e.g. `public`, `private`).".format(block.address),
                        block.file, block.line, block.address))
    return findings


@check("variable_typed_any")
def variable_typed_any(repo: Repo, rule: dict) -> List[Finding]:
    """MODULE-004: no variable declares `type = any`."""
    findings = []
    for block in repo.all_blocks("variable"):
        declared_type = block.attrs.get("type", "")
        if re.search(r"\bany\b", declared_type):
            findings.append(make_finding(
                rule, 'variable "{}" declares type = {}.'.format(block.name, declared_type.split("\n")[0]),
                block.file, block.line, "variable." + block.name))
    return findings


@check("component_outside_domain_folder")
def component_outside_domain_folder(repo: Repo, rule: dict) -> List[Finding]:
    """MODULE-005: components live under their domain folder (eks/, ec2/, elb/), not as top-level eks-*, ec2-* or
    elb-* modules."""
    findings = []
    already_reported = set()
    for module in repo.module_dirs():
        top_folder = repo.module_relpath(module).split("/")[0]       # modules/eks-nodegroup -> eks-nodegroup
        is_forbidden = any((top_folder + "/").startswith(prefix) for prefix in rule["forbidden_prefixes"])
        if is_forbidden and top_folder not in already_reported:
            already_reported.add(top_folder)
            findings.append(make_finding(
                rule, "{} should live inside its domain directory (<modules>/<domain>/<component>).".format(module),
                repo.files_in(module)[0], 1))
    return findings


@check("eks_autoscaling_group_declared_directly")
def eks_autoscaling_group_declared_directly(repo: Repo, rule: dict) -> List[Finding]:
    """MODULE-006: an Auto Scaling Group in the EKS module domain, or in any root configuration, bypasses eks/node-group."""
    findings = []
    for block in repo.all_blocks("resource"):
        if block.type != "aws_autoscaling_group":
            continue
        folder = folder_of(block.file)
        in_eks_domain = repo.is_module_dir(folder) and any(
            (repo.module_relpath(folder) + "/").startswith(prefix) for prefix in rule["module_paths"])
        in_a_root = folder in repo.roots()
        if in_eks_domain or in_a_root:
            findings.append(make_finding(rule, "{} is declared in {}.".format(block.address, block.file), block.file, block.line, block.address))
    return findings


# --------------------------------------------------------------------------------------------------------------------
# TAGS: every taggable resource carries the mandatory tags
# --------------------------------------------------------------------------------------------------------------------

def _tag_contract_ok(tags_expression: str, module_text: str, mandatory_tags: List[str]) -> bool:
    """Whether a resource's `tags = ...` expression carries every mandatory tag.

    Either it uses the module's shared tags (`local.tags`) and the module defines each mandatory tag somewhere, or it
    lists all of them itself."""
    if re.search(r"\blocal\.(tags|mandatory_tags|common_tags)\b", tags_expression):
        return mentions_all(mandatory_tags, module_text)
    return mentions_all(mandatory_tags, tags_expression)


@check("resource_missing_mandatory_tags")
def resource_missing_mandatory_tags(repo: Repo, rule: dict) -> List[Finding]:
    """TAGS-001: every taggable resource in a module has a `tags` argument that carries the mandatory tags."""
    findings = []
    taggable_types = set(rule["taggable_types"])
    mandatory_tags = rule["mandatory_tags"]
    for module in repo.module_dirs():
        files = repo.files_in(module)
        module_text = "\n".join(repo.text(path) for path in files)
        for path in files:
            for block in repo.blocks(path):
                if block.kind != "resource" or block.type not in taggable_types:
                    continue
                tags_expression = block.attrs.get("tags")
                if tags_expression is None:
                    findings.append(make_finding(rule, "{} has no `tags` argument.".format(block.address), block.file, block.line, block.address))
                elif not _tag_contract_ok(tags_expression, module_text, mandatory_tags):
                    findings.append(make_finding(
                        rule, "{} tags do not include all of: {}.".format(block.address, ", ".join(mandatory_tags)),
                        block.file, block.line, block.address))
    return findings


@check("module_missing_tag_variables")
def module_missing_tag_variables(repo: Repo, rule: dict) -> List[Finding]:
    """TAGS-002: a module that creates taggable resources declares the `tags` and `extra_tags` variables."""
    findings = []
    taggable_types = set(rule["_rules"]["TAGS-001"]["taggable_types"])    # the list of taggable types lives in TAGS-001
    for module in repo.module_dirs():
        blocks = [block for path in repo.files_in(module) for block in repo.blocks(path)]
        creates_taggable = any(block.kind == "resource" and block.type in taggable_types for block in blocks)
        if not creates_taggable:
            continue
        declared_variables = {block.name for block in blocks if block.kind == "variable"}
        missing = [name for name in ("tags", "extra_tags") if name not in declared_variables]
        if missing:
            findings.append(make_finding(
                rule, "{} creates taggable resources but lacks variable(s): {}.".format(module, ", ".join(missing)),
                repo.files_in(module)[0], 1))
    return findings


@check("autoscaling_group_does_not_propagate_tags")
def autoscaling_group_does_not_propagate_tags(repo: Repo, rule: dict) -> List[Finding]:
    """TAGS-003: Auto Scaling Groups use `tag` blocks with propagate_at_launch = true for the mandatory tags.

    An Auto Scaling Group cannot use a plain `tags` map to tag the instances it launches, so it needs `tag` blocks."""
    findings = []
    for module in repo.module_dirs():
        files = repo.files_in(module)
        module_text = "\n".join(repo.text(path) for path in files)
        for path in files:
            for block in repo.blocks(path):
                if block.kind != "resource" or block.type != "aws_autoscaling_group":
                    continue
                has_tag_block = re.search(r'^\s*(dynamic\s+"tag"|tag)\s*\{', block.body, re.MULTILINE)
                propagates = re.search(r"propagate_at_launch\s*=\s*true", block.body)
                names_every_tag = mentions_all(rule["mandatory_tags"], module_text)
                if not (has_tag_block and propagates and names_every_tag):
                    findings.append(make_finding(
                        rule, "{} has no `tag` blocks with propagate_at_launch = true for the mandatory tags.".format(block.address),
                        block.file, block.line, block.address))
    return findings


# --------------------------------------------------------------------------------------------------------------------
# ROOT: the layout of a family of roots (the roots are the `roots` patterns of the rule; with none, nothing applies)
# --------------------------------------------------------------------------------------------------------------------

# A double-quoted string, escapes included.
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')

# Files that are not part of the layout because the pipeline or Terraform generates them.
_GENERATED_FILES = {"backend.tf", "tests", ".terraform", ".terraform.lock.hcl", "tfplan"}

# What the root's main.tf must NOT declare, with the wording used in the finding.
_FORBIDDEN_IN_ROOT_MAIN = (
    (re.compile(r'^\s*provider\s+"', re.MULTILINE), "declares a provider block"),
    (re.compile(r"^\s*required_providers\s*\{", re.MULTILINE), "declares required_providers"),
    (re.compile(r'^\s*backend\s+"', re.MULTILINE), "declares a backend"),
)


def _family_roots(repo: Repo, rule: dict) -> List[str]:
    """The roots a ROOT rule applies to: those that match its `roots` patterns. With no patterns, none."""
    return [root for root in repo.roots() if any(glob_match(pattern, root) for pattern in rule.get("roots") or [])]


@check("root_breaks_layout")
def root_breaks_layout(repo: Repo, rule: dict) -> List[Finding]:
    """ROOT-001: the roots of the rule hold only the listed files and templates, and their main.tf declares no provider,
    required_providers or backend."""
    roots = _family_roots(repo, rule)
    findings = []
    required_files = rule.get("files", [])
    template_suffixes = tuple(rule.get("template_suffixes", []))

    for root in roots:
        names_in_root = set(os.listdir(os.path.join(repo.root, root)))

        for needed in required_files:
            if needed not in names_in_root:
                anchor = "main.tf" if "main.tf" in names_in_root else sorted(names_in_root)[0]
                findings.append(make_finding(rule, "{} is missing {}.".format(root, needed), root + "/" + anchor, 1))

        for extra in sorted(names_in_root - set(required_files) - _GENERATED_FILES):
            if template_suffixes and extra.endswith(template_suffixes):
                continue          # templates that main.tf renders with templatefile() live next to it
            findings.append(make_finding(
                rule, "{}/{} is not allowed: a configuration holds {} and its templates.".format(root, extra, ", ".join(required_files)),
                "{}/{}".format(root, extra), 1))

        if "main.tf" in names_in_root:
            main_text = repo.text(root + "/main.tf")
            for pattern, what in _FORBIDDEN_IN_ROOT_MAIN:
                match = pattern.search(main_text)
                if match:
                    line = main_text.count("\n", 0, match.start()) + 1
                    findings.append(make_finding(
                        rule, "{}/main.tf {}; that belongs to the pipeline (AWS_REGION, generated backend) or the modules' constraints.".format(root, what),
                        root + "/main.tf", line))
    return findings


@check("root_files_differ")
def root_files_differ(repo: Repo, rule: dict) -> List[Finding]:
    """ROOT-002: the files matching `identical` are byte-identical across the roots of the rule."""
    roots = _family_roots(repo, rule)
    findings = []
    first_seen: Dict[str, tuple] = {}              # file name -> (path, contents) of the first root that has it
    patterns = rule.get("identical", [])

    for root in roots:
        for name in sorted(os.listdir(os.path.join(repo.root, root))):
            if not any(glob_match(pattern, name) for pattern in patterns):
                continue
            path = "{}/{}".format(root, name)
            if name.endswith(".tf"):
                contents = repo.text(path)
            else:
                with open(os.path.join(repo.root, path), encoding="utf-8") as handle:
                    contents = handle.read()
            if name not in first_seen:
                first_seen[name] = (path, contents)
            elif contents != first_seen[name][1]:
                findings.append(make_finding(rule, "{} differs from {}.".format(path, first_seen[name][0]), path, 1))
    return findings


@check("root_call_holds_logic")
def root_call_holds_logic(repo: Repo, rule: dict) -> List[Finding]:
    """ROOT-005: a `module` block of a root reshapes values with a `for` expression, a conditional or one of the forbidden functions.

    A call only passes values (`local.inputs.*`, other modules' outputs, `templatestring`). Resolving and defaulting is the module's job."""
    findings: List[Finding] = []
    function_call = re.compile(r"\b(%s)\s*\(" % "|".join(re.escape(name) for name in rule.get("forbidden_functions", [])))
    for block in repo.all_blocks("module"):
        if folder_of(block.file) not in repo.roots():
            continue
        code = _STRING.sub('""', block.body)                      # what is written inside a string is text, not logic
        uses = []
        if re.search(r"\bfor\s+[\w\s,]+\s+in\b", code):
            uses.append("a `for` expression")
        if "?" in code:
            uses.append("a conditional (`? :`)")
        called = sorted({match.group(1) for match in function_call.finditer(code)}) if rule.get("forbidden_functions") else []
        if called:
            uses.append("the function(s) " + ", ".join("`{}`".format(name) for name in called))
        if uses:
            findings.append(make_finding(
                rule, "module.{} in {} uses {}.".format(block.name, folder_of(block.file), " and ".join(uses)),
                block.file, block.line, "module." + block.name))
    return findings
