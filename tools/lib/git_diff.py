"""git diff: which files a change touches. The starting point of the CI: everything else asks what this PR changed."""
from __future__ import annotations

import subprocess
from typing import Dict, List

# `git diff --name-status` prints a letter per file; we use words.
_STATUS_WORDS = {"A": "added", "M": "modified", "D": "deleted"}


def git_changed_files(root: str, base: str) -> List[Dict[str, str]]:
    """Files changed between `base` and HEAD, as {"status": "added|modified|deleted", "path": ...}.

    `base...HEAD` (three dots) compares HEAD with the point where it branched off `base`, which is what a pull request shows.
    Only committed changes count: edits that are not committed yet are not part of the diff."""
    diff = subprocess.run(
        ["git", "-C", root, "diff", "--name-status", "--no-renames", "{}...HEAD".format(base)],
        capture_output=True, text=True, check=True,
    ).stdout

    changed = []
    for line in diff.splitlines():
        # Each line looks like "M<TAB>modules/vpc/main.tf".
        status, _, path = line.partition("\t")
        changed.append({"status": _STATUS_WORDS.get(status[:1], status), "path": path})
    return changed
