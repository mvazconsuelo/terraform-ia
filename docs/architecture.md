# How it works

English · [Español](es/architecture.md)

![Terraform-ia architecture](images/architecture.svg)

1. **A root configuration is the unit of work:** a folder with its own state, planned and applied on its own.
2. **Code decides what runs and whether a change passes.** Discovery, the verdict and the account check are deterministic.
3. **The AI only reads.** It writes a summary of the evidence; it cannot change a verdict or start anything.

```
lib/git_diff → what changed ─► terraform/ → what it affects ─► rules/ → which rules it breaks
                                                              │
                       review/ → verdict and PR comment  ◄────┘        ai/ → optional summary
```

## Affected-root discovery

No folder name is assumed. Roots come from `terraform.roots` (globs) or are inferred: a folder nobody calls as a module, outside the modules folder, with resources, modules, a provider or a backend. Modules are the folders under `terraform.modules` (default `modules`) plus anything called through a local `source`.

`terraform/affected_roots.py` walks the module-call graph from each root. A root is affected when:

| Cause | Example |
| --- | --- |
| A file in the root changed | `infra-example/dev/web-demo/network.tf` |
| A module it uses changed, directly or through another module | `modules/vpc/main.tf` |
| A shared file it reads changed (`file()`, `templatefile()` with `../` paths) | `../shared/policy.json` |
| `.terraform-version` changed | every root |

`*.md` affects nothing. Unaffected roots are never initialised, planned, validated or applied. The same logic gives the affected modules (`Repo.affected_modules`), which `validate`, TFLint and Checkov run on.

## Branches and accounts

| Branch | Keys (secrets) | Expected account |
| --- | --- | --- |
| `main` (production) | `AWS_ACCESS_KEY_ID_MAIN`, `AWS_SECRET_ACCESS_KEY_MAIN` | the `account` of the environments with `branch: main` |
| `develop` and any other branch | `AWS_ACCESS_KEY_ID_DEVELOP`, `AWS_SECRET_ACCESS_KEY_DEVELOP` | the `account` of the environments with `branch: develop` |

The branch picks the keys (the target branch for a PR, the selected branch for a manual run). Before `init` the pipeline asks AWS for the keys' account and compares it with the `account` of the environment that names the branch in `terraform.environments`; a mismatch, a missing secret or a missing id stops the run before anything is touched. The `roots` of the environments of a branch are the roots it may plan, review and apply, so a run on `develop` never touches production roots even when they share modules.

## State

One state per root: key `<root path>/terraform.tfstate` in the bucket `<project>-tfstate-<account id>-<region>`, created by hand once per account and region. Locking is S3 native (`use_lockfile`). The pipeline writes an empty `backend "s3" {}` block unless the root declares its own, and passes bucket, key, region, encryption and locking to `terraform init`.

## Pipelines

**`pull-request.yml`**: `discover` → `fmt` · `python` (ruff, mypy) · `validate` · `tflint` · `checkov` (affected modules) · `tests` · `contract` → `plan` per affected root (calls `terraform.yml`, read-only) → `review` (comment). A PR into the default branch (production) skips those six checks, which already passed in the PR into `develop`, runs plan, cost and review with the production keys, and marks every root protected. Fork PRs get no secrets and no AI.

**`terraform.yml`**: called by PRs for a read-only plan, and run by hand to plan or apply one root (`gh workflow run`). **Merging a pull request never touches AWS**: deploying is always an explicit, manual run, and only from a branch that an environment names.

Both workflows: the actions are pinned by commit SHA (Dependabot keeps them current), every job has a timeout, and a new push to a pull request cancels its run in progress. An `apply` is never cancelled: runs of the same root queue.

## The reviewer

`tools`: findings from contract checks on the code (`rules/rules.yaml` + `rules/code_rules.py`) and checks on the plan and cost, then:

- **Verdict:** `REQUEST_CHANGES` when a confirmed finding is HIGH or CRITICAL or an external check failed (fmt, ruff and mypy, tests, validate, TFLint, the repository contract), else `PASS`. Checkov only warns for now. Risk is the highest severity found. A skipped check is not a failure.
- **`PLAN-001`:** a plan that destroys or replaces a stateful resource is CRITICAL in a protected root (every root in a PR into production) and HIGH elsewhere.
- **Comment:** one per PR, updated in place. The header is a coloured box (green for PASS, red or yellow for REQUEST_CHANGES) with the decision and the risk, then a table with the environment, the AWS account, the reviewed commit and the link to the run; then eight sections: AI Gemini summary, affected configurations, checks, Terraform plan (replacements included), cost, versions, repository rules, decision. Each check name and each root's plan link to the log of the job that ran it.

- **Versions:** the Terraform and provider versions the plan used, against the latest releases, with a link to what changed. It only informs; it never changes a file and never affects the decision. If the registries do not answer, the section says so.

Every rule, with its severity and the function that implements it, is in [The checks](checks.md).

## AI boundary

Off by default (`ai.enabled`). It receives one sanitized payload (verdict, affected roots, checks, plan, replacements, cost, findings, the names of the changed files (never their contents), PR text; never state or credentials). It never receives source files, only the evidence above, and returns one text validated against `ai/schema.json`. Every Terraform address, file path and dollar amount in it is checked against the evidence and replaced by `<unverified …>` if it cannot be verified. No tools, no filesystem, no AWS or GitHub access. If it is disabled, errors or the PR is from a fork, the comment says so and everything else is identical.

## Configuration

`common.yaml`:

| Key | Meaning |
| --- | --- |
| `project` | First part of the state bucket name; also used for tags and names |
| `backend.encrypt`, `backend.use_lockfile` | Passed to `terraform init` |
| `ai.enabled` | Turns the AI summary on |
| `terraform.roots`, `terraform.modules` | Pin the roots, or the modules folders (default `modules`) |
| `terraform.environments.<name>` | **Required.** One entry per environment: `branch` (the branch that deploys it), `account` (AWS account id of that branch's keys) and `roots` (the roots that belong to it). A root takes its `environment` tag from here, and an environment deployed from `main` must meet `POLICY-001`. Environments of one branch share its keys, so they name the same account |

## Code map

Every file and what it is for: [What each file is](files.md). Every rule: [The checks](checks.md).

## Dependency updates (Dependabot)

The workflows run third-party code (GitHub Actions) with your token and secrets, so they must not fall behind. Dependabot, configured in
[`.github/dependabot.yml`](../.github/dependabot.yml), opens **one pull request a week into `develop`** that raises the versions of the
actions in the workflows. It never merges anything and never touches Terraform or the provider versions of the modules.

When one arrives:
- Read it. A **major** bump (for example `checkout` 4 to 7) can change how the pipeline behaves.
- The usual checks run on it; merge it only if they pass. It reaches `main` later, like any change, with the next release pull request.
- Its comment says "AI summary unavailable / `GEMINI_API_KEY` is not set": Dependabot pull requests do not receive the repository secrets. The
  rest of the review is valid.
- Comment `@dependabot rebase` to refresh it, or `@dependabot close` to dismiss it.

Separately, the *Dependabot alerts* of the repository warn when a dependency has a known vulnerability.

## Known limits

- Checkov runs with `--soft-fail` until its findings on the modules are triaged.
- Infracost may not price resources it cannot resolve in a plan (for example an Auto Scaling Group whose launch template is created in the same plan); the cost section lists what it could not price.
- Roots are applied in path order; dependencies between roots are not modelled.
- Production means the repository's default branch.
- The tests (`tests/`) cover the reviewer (every rule, the verdict, which roots a run reaches, the redaction of secrets) and the modules that resolve or validate something. They run only in the pipeline, with no AWS and no secrets. Only the behaviour of a real `apply` is not covered: it rests on `validate`, the plan and the modules' own validations.
- The tag check on planned resources is not shown in the comment; tags are enforced on the code by `TAGS-001`.

---

[← Previous: Setup](install.md) · [README](../README.md) · [Next: What each file is →](files.md)
