"""Is there a newer Terraform or provider than the one a run used? Looks up the latest releases and links to what changed.

This only informs: nothing here changes a file, a version or the verdict. The versions in use come from the plan jobs
(`ci/terraform_versions.py`); the latest ones come from public, read-only endpoints:

  * Terraform  HashiCorp's release check (`checkpoint-api.hashicorp.com`);
  * providers  the Terraform Registry (`registry.terraform.io`).

If an endpoint does not answer, that component shows as "could not check" and the review goes on.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

TERRAFORM_LATEST_URL = "https://checkpoint-api.hashicorp.com/v1/check/terraform"
PROVIDER_VERSIONS_URL = "https://registry.terraform.io/v1/providers/{namespace}/{name}/versions"
TIMEOUT_SECONDS = 10

Fetch = Callable[[str], Any]
Version = Tuple[int, int, int]


def fetch_json(url: str) -> Any:
    """GET a URL and parse its JSON answer. Raises OSError or ValueError when the endpoint is unreachable or answers badly."""
    request = urllib.request.Request(url, headers={"User-Agent": "terraform-ia-reviewer", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def parse_version(text: str) -> Optional[Version]:
    """`1.16.3` or `v1.16.3` as (1, 16, 3). Pre-releases such as `1.17.0-rc1` return None: they are never offered as the latest."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(text).strip())
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else None


def kind_of_update(current: Version, latest: Version) -> Optional[str]:
    """What kind of update `latest` is over `current`: "major", "minor" or "patch"; None when it is not newer."""
    if latest <= current:
        return None
    if latest[0] > current[0]:
        return "major"
    return "minor" if latest[1] > current[1] else "patch"


def latest_terraform(fetch: Fetch) -> Optional[str]:
    """The latest stable Terraform version."""
    return fetch(TERRAFORM_LATEST_URL).get("current_version")


def latest_provider(source: str, fetch: Fetch) -> Optional[str]:
    """The latest stable version of a provider, for a source such as `registry.terraform.io/hashicorp/aws`."""
    _, namespace, name = source.split("/")[-3:]
    published = fetch(PROVIDER_VERSIONS_URL.format(namespace=namespace, name=name)).get("versions", [])
    stable = [(parse_version(item["version"]), item["version"]) for item in published if parse_version(item["version"])]
    return max(stable)[1] if stable else None


def release_url(source: str, version: str) -> str:
    """Where to read what changed in a release: the GitHub release page for Terraform and HashiCorp providers, the Registry otherwise."""
    if source == "terraform":
        return "https://github.com/hashicorp/terraform/releases/tag/v{}".format(version)
    _, namespace, name = source.split("/")[-3:]
    if namespace == "hashicorp":
        return "https://github.com/hashicorp/terraform-provider-{}/releases/tag/v{}".format(name, version)
    return "https://registry.terraform.io/providers/{}/{}/{}".format(namespace, name, version)


def display_name(source: str) -> str:
    """The name shown in the comment: `Terraform` or `hashicorp/aws provider`."""
    if source == "terraform":
        return "Terraform"
    return "{} provider".format("/".join(source.split("/")[-2:]))


def check_versions(in_use: Dict[str, str], fetch: Fetch = fetch_json) -> List[Dict[str, Any]]:
    """Compare each component in use with its latest release.

    `in_use` maps `terraform` or a provider source to the version a plan used. Returns one entry per component:
    {name, in_use, latest, update ("major", "minor", "patch" or None), url}. `latest` is None when it could not be checked."""
    results: List[Dict[str, Any]] = []
    for source, version in sorted(in_use.items(), key=lambda entry: (entry[0] != "terraform", entry[0])):
        try:
            latest = latest_terraform(fetch) if source == "terraform" else latest_provider(source, fetch)
        except (OSError, ValueError, KeyError, AttributeError):
            latest = None
        current_tuple, latest_tuple = parse_version(version), parse_version(latest or "")
        update = kind_of_update(current_tuple, latest_tuple) if current_tuple and latest_tuple else None
        results.append({
            "name": display_name(source), "in_use": version, "latest": latest, "update": update,
            "url": release_url(source, latest) if (update and latest) else None,
        })
    return results
