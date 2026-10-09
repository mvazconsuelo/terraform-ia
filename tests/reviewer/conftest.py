"""What the reviewer tests share: the real repository as the "good" case, and a copy of it that a test can break.

A test follows three steps, in this order and with these names in the comments:

    # given: break one thing in a copy of the repository (or take the repository as it is)
    # when:  run the check
    # then:  say what must come out
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, List

import pytest

from tools.review.finding import Finding
from tools.review.run_review import load_rules, run_all
from tools.terraform.terraform_map import Repo

REPO_ROOT = Path(__file__).resolve().parents[2]
COPIED = ("common.yaml", "modules", "infra-example")                  # all the reviewer reads of a repository
LEFT_OUT = shutil.ignore_patterns(".terraform", ".terraform.lock.hcl", "__pycache__", "backend.tf", "*.tfstate*")


class Sandbox:
    """A copy of the repository in a temporary folder, with small helpers to break it."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def edit(self, relative: str, old: str, new: str) -> None:
        """Replace text in a file; the test fails if the text is not there, so a typo never hides a missing case."""
        path = self.root / relative
        text = path.read_text(encoding="utf-8")
        assert old in text, "{} does not contain {!r}".format(relative, old)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def append(self, relative: str, text: str) -> None:
        """Add text at the end of a file."""
        path = self.root / relative
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

    def write(self, relative: str, text: str) -> None:
        """Create a file (and its folders)."""
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def remove(self, relative: str) -> None:
        """Delete a file."""
        (self.root / relative).unlink()


@pytest.fixture(scope="session")
def rules() -> List[dict]:
    """The catalog of rules, as the reviewer loads it."""
    return load_rules()


@pytest.fixture(scope="session")
def pristine(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One clean copy of the repository, made once; every `sandbox` starts from it."""
    destination = tmp_path_factory.mktemp("pristine")
    for name in COPIED:
        source = REPO_ROOT / name
        if source.is_dir():
            shutil.copytree(source, destination / name, ignore=LEFT_OUT)
        else:
            shutil.copy(source, destination / name)
    return destination


@pytest.fixture
def sandbox(pristine: Path, tmp_path: Path) -> Sandbox:
    """A fresh copy of the repository for one test to break."""
    destination = tmp_path / "repo"
    shutil.copytree(pristine, destination)
    return Sandbox(destination)


@pytest.fixture
def findings_of(rules: List[dict]) -> Callable[..., List[Finding]]:
    """`findings_of(path, "ROOT-003")`: what the reviewer finds for that rule in the repository at `path`."""
    def find(path: Path, rule_id: str) -> List[Finding]:
        return [finding for finding in run_all(Repo(str(path)), rules) if finding.rule_id == rule_id]

    return find
