"""Every module has its test in tests/terraform. The modules still waiting for it are listed in PENDING, so the backlog is visible and cannot grow."""
from __future__ import annotations

import pytest

from .conftest import REPO_ROOT

MODULES_DIR = REPO_ROOT / "modules"
TESTS_DIR = REPO_ROOT / "tests" / "terraform"

# Modules whose test is still to be written: empty today, every module has its test. A new module needs its test in the same change; this list is
# only for a backlog on purpose. A module in it that already has its test fails (strict xfail), so the list only ever gets shorter.
PENDING: list = []


def _modules() -> list:
    """Every module: a folder under modules/ with a versions.tf, as its path below modules/ (`elb/alb`)."""
    return sorted(path.parent.relative_to(MODULES_DIR).as_posix() for path in MODULES_DIR.rglob("versions.tf"))


def _test_file(module: str) -> str:
    """The test of a module: its path with `/` and `-` as `_` (`elb/alb` is `elb_alb.tftest.hcl`)."""
    return module.replace("/", "_").replace("-", "_") + ".tftest.hcl"


def _cases() -> list:
    """One case per module; a pending module is expected to fail until its test exists."""
    waiting = pytest.mark.xfail(strict=True, reason="its test is still to be written (remove it from PENDING when it is)")
    return [pytest.param(module, marks=waiting) if module in PENDING else module for module in _modules()]


@pytest.mark.parametrize("module", _cases())
def test_every_module_has_a_terraform_test(module: str) -> None:
    # given: a module of modules/
    # when:  we look for its test, named after its path
    expected = TESTS_DIR / _test_file(module)

    # then:  it exists
    assert expected.is_file(), "modules/{} has no test: write tests/terraform/{}".format(module, expected.name)


def test_pending_lists_only_modules_that_exist() -> None:
    # given: the backlog above
    # when / then: every name in it is still a module, so the list cannot hold a stale name
    assert [module for module in PENDING if module not in _modules()] == []
