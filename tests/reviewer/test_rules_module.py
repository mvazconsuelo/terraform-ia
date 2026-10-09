"""MODULE and TAGS: is the module built as the standard says, and does everything that can be tagged carry the tags?"""
from __future__ import annotations

from typing import Callable, List

from tools.review.finding import Finding

from .conftest import Sandbox

Findings = Callable[..., List[Finding]]


# ---------------------------------------------------------------- MODULE-001: a capability is built only inside its module
def test_module_001_flags_a_bucket_declared_in_a_root(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: a root that declares an S3 bucket itself instead of calling modules/s3
    sandbox.write("infra-example/dev/web-demo/logs.tf", 'resource "aws_s3_bucket" "logs" {\n  bucket = "logs"\n}\n')

    # when / then
    found = findings_of(sandbox.root, "MODULE-001")
    assert [finding.file for finding in found] == ["infra-example/dev/web-demo/logs.tf"]
    assert "modules/s3" in found[0].evidence or "modules/s3" in found[0].recommendation


# ---------------------------------------------------------------- MODULE-002: the contract files
def test_module_002_flags_a_module_without_readme(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: a module whose README was deleted
    sandbox.remove("modules/s3/README.md")

    # when / then
    found = findings_of(sandbox.root, "MODULE-002")
    assert len(found) == 1 and "README.md" in found[0].evidence


# ---------------------------------------------------------------- MODULE-003: the primary resource is called `this`
def test_module_003_flags_a_resource_named_after_its_type(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: a resource with an arbitrary name
    sandbox.append("modules/s3/main.tf", '\nresource "aws_s3_bucket_versioning" "my_bucket" {}\n')

    # when / then
    assert len(findings_of(sandbox.root, "MODULE-003")) == 1


# ---------------------------------------------------------------- MODULE-004: no `type = any`
def test_module_004_flags_a_variable_typed_any(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: a variable without a real type
    sandbox.append("modules/s3/variables.tf", '\nvariable "anything" {\n  type = any\n}\n')

    # when / then
    assert len(findings_of(sandbox.root, "MODULE-004")) == 1


# ---------------------------------------------------------------- MODULE-005: components live in their domain folder
def test_module_005_flags_a_component_outside_its_domain(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: an EKS module at the top of modules/ instead of modules/eks/<component>
    sandbox.write("modules/eks-extra/versions.tf", 'terraform {\n  required_version = ">= 1.11.0"\n}\n')

    # when / then
    assert len(findings_of(sandbox.root, "MODULE-005")) == 1


# ---------------------------------------------------------------- MODULE-006: EKS capacity is not a raw Auto Scaling Group
def test_module_006_flags_an_autoscaling_group_in_the_eks_domain(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: the EKS cluster module declaring an Auto Scaling Group
    sandbox.append("modules/eks/cluster/main.tf", '\nresource "aws_autoscaling_group" "workers" {}\n')

    # when / then
    assert len(findings_of(sandbox.root, "MODULE-006")) == 1


# ---------------------------------------------------------------- TAGS-001: taggable resources receive the tags
def test_tags_001_flags_a_taggable_resource_without_tags(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: an elastic IP in the vpc module with no tags at all
    sandbox.append("modules/vpc/main.tf", '\nresource "aws_eip" "untagged" {\n  domain = "vpc"\n}\n')

    # when / then
    found = findings_of(sandbox.root, "TAGS-001")
    assert [finding.resource for finding in found] == ["aws_eip.untagged"]


# ---------------------------------------------------------------- TAGS-002: a module that tags exposes `tags` and `extra_tags`
def test_tags_002_flags_a_module_without_the_tag_variables(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: a new module with a taggable resource and no tags variable
    sandbox.write("modules/notags/main.tf", 'resource "aws_s3_bucket" "this" {\n  bucket = "x"\n}\n')
    sandbox.write("modules/notags/variables.tf", 'variable "name" {\n  type = string\n}\n')

    # when / then
    found = findings_of(sandbox.root, "TAGS-002")
    assert [finding.file for finding in found] == ["modules/notags/main.tf"]
    assert "tags, extra_tags" in found[0].evidence


# ---------------------------------------------------------------- TAGS-003: an Auto Scaling Group propagates the tags
def test_tags_003_flags_an_autoscaling_group_without_tag_blocks(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: an Auto Scaling Group with no `tag` blocks
    sandbox.write("modules/ec2/asg-extra/main.tf", 'resource "aws_autoscaling_group" "this" {\n  max_size = 1\n  min_size = 1\n}\n')

    # when / then
    assert len(findings_of(sandbox.root, "TAGS-003")) == 1
