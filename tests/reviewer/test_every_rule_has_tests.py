"""The rule that keeps the other tests honest: every rule of the catalog is tested, in both directions."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, List

import pytest

from tools.review.finding import Finding

from .conftest import REPO_ROOT, load_rules

RULE_IDS = [rule["id"] for rule in load_rules()]


def _test_names() -> List[str]:
    """The names of every test function in tests/reviewer."""
    names = []
    for path in sorted(Path(__file__).parent.glob("test_*.py")):
        names += [node.name for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(node, ast.FunctionDef)]
    return names


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_every_rule_passes_on_the_repository(rule_id: str, findings_of: Callable[..., List[Finding]]) -> None:
    # given: the repository as it is
    # when:  the rule runs
    found = findings_of(REPO_ROOT, rule_id)

    # then:  nothing is flagged, because the repository follows its own rules
    assert found == [], [finding.evidence for finding in found]


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_every_rule_has_a_test_that_flags_it(rule_id: str) -> None:
    # given: the tests of the reviewer, named test_<rule id>_flags_<what> (for example test_root_003_flags_a_root_outside_every_environment)
    prefix = "test_" + rule_id.lower().replace("-", "_") + "_flags_"

    # when:  we look for one that breaks this rule on purpose
    flagging = [name for name in _test_names() if name.startswith(prefix)]

    # then:  there is at least one, so a rule that stops working is noticed
    assert flagging, "no test named {}... breaks {}".format(prefix, rule_id)
