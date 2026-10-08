# How it works

[← README](../README.md) · English · [Español](es/architecture.md)

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
| A shared file it reads changed (`file()`, `templatefile()` with `../` paths) | `common.yaml` |
| `.terraform-version` changed | every root |

`*.md` affects nothing. Unaffected roots are never initialised, planned, validated or applied. The same logic gives the affected modules (`Repo.affected_modules`), which `validate`, TFLint and Checkov run on.

## Branches and accounts

| Branch | Keys (secrets) | Expected account |
| --- | --- | --- |
| `main` (production) | `AWS_ACCESS_KEY_ID_MAIN`, `AWS_SECRET_ACCESS_KEY_MAIN` | `terraform.accounts.main` |
| `develop` and any other branch | `AWS_ACCESS_KEY_ID_DEVELOP`, `AWS_SECRET_ACCESS_KEY_DEVELOP` | `terraform.accounts.develop` |

The branch picks the keys (the target branch for a PR, the pushed branch for a push). Before `init` the pipeline asks AWS for the keys' account and compares it with `terraform.accounts`; a mismatch, a missing secret or a missing id stops the run before anything is touched. `terraform.deploy.<branch>` lists the roots each branch may plan, review and apply, so a push to `develop` never touches production roots even when they share modules.

## State

One state per root: key `<root path>/terraform.tfstate` in the bucket `<project>-tfstate-<account id>-<region>`, created by hand once per account and region. Locking is S3 native (`use_lockfile`). The pipeline writes an empty `backend "s3" {}` block unless the root declares its own, and passes bucket, key, region, encryption and locking to `terraform init`.

## Pipelines

**`pull-request.yml`**: `discover` → `fmt` · `python` (ruff, mypy) · `validate` · `tflint` · `checkov` (affected modules) · `contract` → `plan` per affected root (calls `terraform.yml`, read-only) → `review` (comment). A PR into the default branch (production) skips those six checks, which already passed in the PR into `develop`, runs plan, cost and review with the production keys, and marks every root protected. Fork PRs get no secrets and no AI.

**`terraform.yml`**: called by PRs for a read-only plan; on push to `develop` or `main` it discovers the roots that push affected for that branch and runs `init` → `plan` → `apply` for each, one at a time; also runnable by hand with `gh workflow run`.

## The reviewer

`tools/reviewer`: findings from contract checks on the code (`rules/rules.yaml` + `rules/code_rules.py`) and checks on the plan and cost, then:

- **Verdict:** `REQUEST_CHANGES` when a confirmed finding is HIGH or CRITICAL or an external check failed (fmt, ruff and mypy, validate, TFLint, the repository contract), else `PASS`. Checkov only warns for now. Risk is the highest severity found. A skipped check is not a failure.
- **`PLAN-001`:** a plan that destroys or replaces a stateful resource is CRITICAL in a protected root (every root in a PR into production) and HIGH elsewhere.
- **Comment:** one per PR, updated in place. The header is a coloured box (green for PASS, red or yellow for REQUEST_CHANGES) with the decision and the risk, then a table with the environment, the AWS account and the link to the run; then eight sections: AI Gemini summary (optional), affected configurations, checks, Terraform plan (replacements included), cost, versions, findings, decision. Each check name and each root's plan link to the log of the job that ran it.

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
| `terraform.accounts.<develop\|main>` | **Required.** AWS account id of that branch's keys |
| `terraform.deploy.<branch>` | Globs of the roots that branch may plan and apply |
| `terraform.roots`, `terraform.modules` | Pin the roots, or the modules folders (default `modules`) |
| `terraform.protected` | Roots where destroying stateful resources is CRITICAL |
| `terraform.conventions.layout` | Opt-in rules ROOT-001 / ROOT-002 for a family of roots |

## Code map

Every file and what it is for: [What each file is](files.md). Every rule: [The checks](checks.md).

## Known limits

- Checkov runs with `--soft-fail` until its findings on the modules are triaged.
- Infracost may not price resources it cannot resolve in a plan (for example an Auto Scaling Group whose launch template is created in the same plan); the cost section lists what it could not price.
- Roots are applied in path order; dependencies between roots are not modelled.
- Production means the repository's default branch.
- There are no unit tests for modules or for the reviewer: correctness rests on `validate`, the contract, the plan and the preconditions. The reviewer's Python is checked with ruff and mypy on every PR.
- The tag check on planned resources is not shown in the comment; tags are enforced on the code by `TAGS-001`.
