"""ROOT: is the root built as the project says? Its files, its environment, its tags and the calls to the modules."""
from __future__ import annotations

from typing import Callable, List

from tools.review.finding import Finding

from .conftest import Sandbox

Findings = Callable[..., List[Finding]]
DEV = "infra-example/dev/web-demo"


# ---------------------------------------------------------------- ROOT-001: a root holds only its listed files
def test_root_001_flags_a_file_that_is_not_in_the_layout(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: a stray file in a root
    sandbox.write(DEV + "/extra.tf", "# not part of the layout\n")

    # when / then
    found = findings_of(sandbox.root, "ROOT-001")
    assert [finding.file for finding in found] == [DEV + "/extra.tf"]


def test_root_001_flags_a_provider_block_in_main_tf(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: main.tf declaring a provider, which belongs to the pipeline
    sandbox.append(DEV + "/main.tf", '\nprovider "aws" {}\n')

    # when / then
    found = findings_of(sandbox.root, "ROOT-001")
    assert len(found) == 1 and "provider" in found[0].evidence


# ---------------------------------------------------------------- ROOT-002: the .tf files are identical in every environment
def test_root_002_flags_a_file_that_differs_between_environments(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: network.tf edited in dev only
    sandbox.append(DEV + "/network.tf", "\n# drift\n")

    # when / then
    found = findings_of(sandbox.root, "ROOT-002")
    assert len(found) == 1 and "network.tf" in found[0].evidence


# ---------------------------------------------------------------- ROOT-003: a root belongs to an environment
def test_root_003_flags_a_root_outside_every_environment(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: common.yaml no longer lists the dev root under any environment
    sandbox.edit("common.yaml", "        - infra-example/dev/web-demo", "        - infra-example/dev/somewhere-else")

    # when / then
    found = findings_of(sandbox.root, "ROOT-003")
    assert [finding.resource for finding in found] == [DEV]


# ---------------------------------------------------------------- ROOT-004: the tags of a root
def test_root_004_flags_tags_that_set_the_environment(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: inputs.yaml setting a tag that common.yaml decides
    sandbox.edit(DEV + "/inputs.yaml", "  owner: platform-team", "  environment: dev\n  owner: platform-team")

    # when / then
    found = findings_of(sandbox.root, "ROOT-004")
    assert len(found) == 1 and "environment" in found[0].evidence


def test_root_004_flags_tags_without_an_owner(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: inputs.yaml without the owner
    sandbox.edit(DEV + "/inputs.yaml", "  owner: platform-team\n", "")

    # when / then
    found = findings_of(sandbox.root, "ROOT-004")
    assert len(found) == 1 and "owner" in found[0].evidence


# ---------------------------------------------------------------- ROOT-005: a module call passes values, it does not reshape them
def test_root_005_flags_try_in_a_module_call(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: a call that defaults a value itself
    sandbox.edit(DEV + "/database.tf", "local.inputs.database.serverless_v2", "try(local.inputs.database.serverless_v2, null)")

    # when / then
    found = findings_of(sandbox.root, "ROOT-005")
    assert len(found) == 1 and "`try`" in found[0].evidence


def test_root_005_flags_a_for_expression_and_a_conditional(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: a call that rebuilds the listeners with a loop and a condition
    sandbox.edit(
        DEV + "/load_balancer.tf",
        "  listeners     = local.inputs.alb.listeners",
        '  listeners = { for key, listener in local.inputs.alb.listeners : key => listener.port == 80 ? listener : listener }',
    )

    # when / then
    found = findings_of(sandbox.root, "ROOT-005")
    assert len(found) == 1 and "`for` expression" in found[0].evidence and "conditional" in found[0].evidence


def test_root_005_ignores_a_question_mark_inside_a_string(sandbox: Sandbox, findings_of: Findings) -> None:
    # given: text with a "?" and a "for x in y" inside a string, which is text and not logic
    sandbox.edit(DEV + "/load_balancer.tf", '  certificates  = { web = module.certificate.certificate_arn }',
                 '  certificates  = { web = module.certificate.certificate_arn }\n  extra_tags    = { note = "why? for each in all" }')

    # when / then
    assert findings_of(sandbox.root, "ROOT-005") == []
