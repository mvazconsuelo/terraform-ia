"""Job "repository contract": run the rules that read the code (the .tf files) and report what they find."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from .git_diff import git_changed_files
from ..review.run_review import load_rules, run_checks
from ..terraform.terraform_map import Repo


def contract_check(root: str, base: Optional[str] = None, all_files: bool = False, output_format: str = "text") -> int:
    """Run the code rules and print the findings. Returns 1 when any finding is High or Critical, else 0.

    With `base` (and without `all_files`) only the findings in files changed since that git ref are reported; otherwise
    the whole repository is checked."""
    repo = Repo(root)
    changed = None if all_files or not base else [change["path"] for change in git_changed_files(root, base)]
    findings = run_checks(repo, load_rules(), changed)

    if output_format == "json":
        print(json.dumps([finding.to_dict() for finding in findings], indent=2))
    else:
        for finding in findings:
            print("{:<8} {:<10} {}:{}  {}".format(finding.severity, finding.rule_id, finding.file, finding.line or "-", finding.evidence))
        print("{} finding(s)".format(len(findings)))
    return 1 if any(finding.severity in ("CRITICAL", "HIGH") for finding in findings) else 0


def main(argv: Optional[List[str]] = None) -> int:
    """`python -m reviewer.ci.contract_check [--all | --base REF] [--format text|json]`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--base", help="only findings in files changed since this git ref")
    parser.add_argument("--all", action="store_true", help="report on the whole repository, not only changed files")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    return contract_check(os.path.abspath(args.root), args.base, args.all, args.format)


if __name__ == "__main__":
    sys.exit(main())
