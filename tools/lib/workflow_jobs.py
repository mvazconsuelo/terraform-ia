"""The jobs of the workflow run that is building the review, with a link to each one (so the comment can point to their logs)."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

REVIEW_JOB_NAME = "PR comment"      # the job running this code: it is still in progress, so it is left out


def list_jobs(env: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """The other jobs of this run as [{"name", "result", "url"}], in the order GitHub lists them.

    `result` is the job's conclusion (success, failure, skipped, cancelled) or "running". Reads GITHUB_REPOSITORY, GITHUB_RUN_ID and
    GITHUB_TOKEN (the workflow needs `actions: read`). Informational, so any failure returns an empty list."""
    env = dict(os.environ) if env is None else env
    repository, run_id, token = env.get("GITHUB_REPOSITORY"), env.get("GITHUB_RUN_ID"), env.get("GITHUB_TOKEN")
    if not (repository and run_id and token):
        return []

    url = "{}/repos/{}/actions/runs/{}/jobs?per_page=100".format(env.get("GITHUB_API_URL", "https://api.github.com"), repository, run_id)
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "User-Agent": "terraform-ia-reviewer",
    })
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            jobs = json.load(response).get("jobs", [])
    except (OSError, ValueError):
        return []
    return [
        {"name": job["name"], "result": job.get("conclusion") or "running", "url": job["html_url"]}
        for job in jobs if job.get("name") != REVIEW_JOB_NAME
    ]
