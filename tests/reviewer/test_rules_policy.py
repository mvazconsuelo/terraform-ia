"""POLICY: do the values of a root meet the project's policy? Today that is what a production root must have."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List

from tools.review.finding import Finding

from .conftest import Sandbox

Findings = Callable[..., List[Finding]]
PROD = "infra-example/prod/web-demo"
DEV = "infra-example/dev/web-demo"


def test_policy_001_flags_a_production_database_without_deletion_protection(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: the production database can be deleted
    sandbox.edit(PROD + "/inputs.yaml", "deletion_protection: true", "deletion_protection: false")

    # when / then: only that requirement fails, and the finding says why it exists
    found = findings_of(sandbox.root, "POLICY-001")
    assert len(found) == 1 and "database.deletion_protection" in found[0].evidence


def test_policy_001_flags_a_production_web_tier_of_one_instance(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: the production Auto Scaling Group may shrink to a single instance
    sandbox.edit(PROD + "/inputs.yaml", "min_size: 2", "min_size: 1")

    # when / then
    found = findings_of(sandbox.root, "POLICY-001")
    assert len(found) == 1 and "compute.min_size" in found[0].evidence


def test_policy_001_flags_a_production_load_balancer_without_https(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: the production listener serves plain HTTP
    sandbox.edit(PROD + "/inputs.yaml", "protocol: HTTPS\n      certificate: web", "protocol: HTTP\n      certificate: web")

    # when / then
    assert any("alb.listeners" in finding.evidence for finding in findings_of(sandbox.root, "POLICY-001"))


def test_policy_001_flags_an_environment_that_moves_to_the_production_branch(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: dev is now deployed from main, so it is a production environment
    sandbox.edit("common.yaml", "      branch: develop", "      branch: main")

    # when / then: dev, which is built to be cheap, breaks the production requirements
    assert {finding.resource for finding in findings_of(sandbox.root, "POLICY-001")} == {DEV}


def test_policy_001_does_not_apply_to_a_non_production_environment(findings_of: Findings, pristine: Path) -> None:
    # given: the repository as it is: dev has deletion protection off, one instance and no NAT
    # when / then: no finding, because dev is deployed from develop
    assert findings_of(pristine, "POLICY-001") == []
