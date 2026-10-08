"""The comment step of the pull-request workflow: publish the review as the one comment of the PR."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from itertools import count
from typing import Any, Dict, List, Optional

from ..review.markdown_report import MARKER


def pr_comment(env: Optional[Dict[str, str]] = None, markdown: str = "review.md") -> int:
    """Create or update the review comment of a pull request through the GitHub API.

    The comment is found by the hidden marker on its first line, so every run edits the same comment instead of adding a
    new one. Needs GITHUB_TOKEN (with pull-requests: write), GITHUB_REPOSITORY and PR_NUMBER."""
    env = os.environ if env is None else env
    api = env.get("GITHUB_API_URL", "https://api.github.com")
    issues = "{}/repos/{}/issues".format(api, env["GITHUB_REPOSITORY"])
    number = env["PR_NUMBER"]

    def call(method: str, url: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        """One request to the GitHub API, returning its JSON answer."""
        request = urllib.request.Request(
            url, method=method, data=None if payload is None else json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + env["GITHUB_TOKEN"], "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "terra-ai-reviewer", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    with open(markdown, encoding="utf-8") as handle:
        body = handle.read()
    try:
        # Look for our comment among the PR's comments, 100 per page.
        existing = None
        for page in count(1):
            comments = call("GET", "{}/{}/comments?per_page=100&page={}".format(issues, number, page))
            existing = next((comment for comment in comments if MARKER in (comment.get("body") or "")), None)
            if existing or len(comments) < 100:
                break

        if existing:
            call("PATCH", "{}/comments/{}".format(issues, existing["id"]), {"body": body})
            print("Updated comment {} on PR #{}".format(existing["id"], number))
        else:
            call("POST", "{}/{}/comments".format(issues, number), {"body": body})
            print("Created the review comment on PR #{}".format(number))
    except urllib.error.HTTPError as error:
        print("GitHub API error {}: {}".format(error.code, error.read().decode(errors="replace")[:300]), file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """`python -m reviewer.ci.pr_comment [--markdown review.md]`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", default="review.md")
    return pr_comment(markdown=parser.parse_args(argv).markdown)


if __name__ == "__main__":
    sys.exit(main())
