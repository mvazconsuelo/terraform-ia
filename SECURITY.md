# Security policy

English · [Español](docs/es/security.md)

## Reporting a vulnerability

**Do not open a public issue.** Use GitHub's private report: the **Security** tab of the repository → **Report a vulnerability**. You will get an answer
in a few days.

What counts as a vulnerability here:

- The reviewer or a workflow leaks a secret or a key (the PR comment, the logs, the AI summary).
- A way to make a workflow run something it should not (script injection through a PR title, a branch name or an input), or to deploy to AWS without the manual run.
- A module whose defaults are insecure (public by default, unencrypted, open to the internet).

A weakness in a dependency or in a GitHub Action is also welcome: Dependabot covers the known ones.

## What is protected

- Merging a pull request never touches AWS. Deploying is a manual run of `terraform.yml`, and only from the branch of an environment.
- The AI never receives file contents, and every text that could carry a secret is redacted before it leaves the repository.
- Pull requests from forks get no secrets.

## If you used this repository

Never commit keys or account ids. If a key was exposed, rotate it first and then clean up. The AWS keys live in the repository secrets, one pair per branch.
