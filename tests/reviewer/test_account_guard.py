"""The account guard: which AWS account the keys of a branch must belong to. The id is a repository variable, never a file of the repository."""
from __future__ import annotations

import pytest
import yaml

from tools.aws.account import expected_account
from tools.review.run_review import target_of
from tools.terraform.terraform_map import Repo

from .conftest import REPO_ROOT

DEVELOP = "111111111111"
MAIN = "222222222222"
VARIABLES = {"AWS_ACCOUNT_ID_DEVELOP": DEVELOP, "AWS_ACCOUNT_ID_MAIN": MAIN}


def test_develop_expects_the_develop_account() -> None:
    assert expected_account("develop", VARIABLES) == DEVELOP


def test_main_expects_the_main_account() -> None:
    assert expected_account("main", VARIABLES) == MAIN


def test_any_other_branch_uses_the_develop_account() -> None:
    # given: a feature branch, whose keys are the develop ones
    assert expected_account("feature/x", VARIABLES) == DEVELOP


def test_a_variable_that_is_not_set_expects_nothing_so_the_run_stops() -> None:
    assert expected_account("develop", {}) == ""
    assert expected_account("main", {"AWS_ACCOUNT_ID_DEVELOP": DEVELOP}) == ""


def test_spaces_around_the_id_are_ignored() -> None:
    assert expected_account("develop", {"AWS_ACCOUNT_ID_DEVELOP": " 111111111111\n"}) == DEVELOP


def test_the_pr_comment_shows_only_the_last_four_digits(monkeypatch: pytest.MonkeyPatch) -> None:
    # given: the variable of the develop branch
    monkeypatch.setenv("AWS_ACCOUNT_ID_DEVELOP", DEVELOP)

    # when / then: the comment never carries the whole id
    target = target_of(Repo(str(REPO_ROOT)), "develop", False)
    assert target is not None and target["account"] == "****1111"


def test_the_pr_comment_says_nothing_when_the_variable_is_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_ACCOUNT_ID_DEVELOP", raising=False)
    target = target_of(Repo(str(REPO_ROOT)), "develop", False)
    assert target is not None and target["account"] is None


def test_common_yaml_holds_no_account_id() -> None:
    # given: the environments of common.yaml
    environments = yaml.safe_load((REPO_ROOT / "common.yaml").read_text(encoding="utf-8"))["terraform"]["environments"]

    # when / then: only the branch and the roots; the account is a repository variable
    assert all(set(environment) == {"branch", "roots"} for environment in environments.values())
