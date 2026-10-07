# How it works

[← README](../README.md)

![terra-ai architecture](images/architecture.svg)

1. **A root configuration is the unit of work:** a folder with its own state, planned and applied on its own.
2. **Code decides what runs and whether a change passes.** Discovery, the verdict and the account check are deterministic.
3. **The AI only reads.** It writes a summary of the evidence; it cannot change a verdict or start anything.

## Affected-root discovery

No folder name is assumed. Roots come from `terraform.roots` (globs) or are inferred: a folder nobody calls as a module, outside the modules folder, with resources, modules, a provider or a backend. Modules are the folders under `terraform.modules` (default `modules`) plus anything called through a local `source`.

`engine.py discover` walks the module-call graph from each root. A root is affected when:

| Cause | Example |
| --- | --- |
| A file in the root changed | `infra-example/dev/web-demo/network.tf` |
| A module it uses changed, directly or through another module | `modules/vpc/main.tf` |
| A shared file it reads changed (`file()`, `templatefile()` with `../` paths) | `common.yaml` |
| `.terraform-version` changed | every root |

`*.md` and `*.tftest.hcl` affect nothing. Unaffected roots are never initialised, planned, validated or applied. The same logic gives the affected modules (`discover --modules`), which `validate`, `test`, TFLint and Checkov run on.

```bash
PYTHONPATH=tools python -m reviewer.engine discover --base origin/develop --branch develop --format text
```

## Branches and accounts

| Branch | Keys (secrets) | Expected account |
| --- | --- | --- |
| `main` (production) | `AWS_ACCESS_KEY_ID_MAIN`, `AWS_SECRET_ACCESS_KEY_MAIN` | `terraform.accounts.main` |
| `develop` and any other branch | `AWS_ACCESS_KEY_ID_DEVELOP`, `AWS_SECRET_ACCESS_KEY_DEVELOP` | `terraform.accounts.develop` |

The branch picks the keys (the target branch for a PR, the pushed branch for a push). Before `init` the pipeline asks AWS for the keys' account and compares it with `terraform.accounts`; a mismatch, a missing secret or a missing id stops the run before anything is touched. `terraform.deploy.<branch>` lists the roots each branch may plan, review and apply, so a push to `develop` never touches production roots even when they share modules.

## State

One state per root: key `<root path>/terraform.tfstate` in the bucket `<project>-tfstate-<account id>-<region>`, created by hand once per account and region. Locking is S3 native (`use_lockfile`). The pipeline writes an empty `backend "s3" {}` block unless the root declares its own, and passes bucket, key, region, encryption and locking to `terraform init`.

## Pipelines

**`pull-request.yml`**: `discover` → `fmt` · `validate` · `test` · `tflint` · `checkov` (affected modules) · `contract` → `plan` per affected root (calls `terraform.yml`, read-only) → `review` (comment). A PR into the default branch (production) skips the six checks already passed in the PR into `develop`, runs plan, cost and review with the production keys, and marks every root protected. Fork PRs get no secrets.

**`terraform.yml`**: called by PRs for a read-only plan; on push to `develop` or `main` it discovers the roots that push affected for that branch and runs `init` → `plan` → `apply` for each, one at a time; also runnable by hand with `gh workflow run`.

## The reviewer

`tools/reviewer`: findings from contract checks on the changed files (`rules.yaml` + `checks.py`) and checks on the plan and cost, then:

- **Verdict:** `REQUEST_CHANGES` when a confirmed finding is HIGH or CRITICAL or an external check failed, else `PASS`. Risk is the highest severity found. A skipped check is not a failure.
- **`PLAN-001`:** a plan that destroys or replaces a stateful resource is CRITICAL in a protected root (every root in a PR into production) and HIGH elsewhere.
- **Comment:** AI Summary, then the evidence (affected configurations, validation, plan, resource changes, replacements, cost, governance, module standard, contract, finding counts, decision). The header shows the risk, the decision and the environment.

Rules: `MOD-001/002/003/004/006` (module boundaries and shape), `GOV-001/002/003` (mandatory tags), `AWS-001`, `NET-001`, `TF-003/004/006`, `PLAN-001/002`. Module rules are in the [module standard](module-standard.md).

## AI boundary

Off by default (`ai.enabled`). It receives one sanitized payload (verdict, affected roots, checks, plan, replacements, cost, findings, changed files, PR text; never state or credentials) and returns one text validated against `ai/schema.json`. Every Terraform address, file path and dollar amount in it is checked against the evidence and replaced by `<unverified …>` if it cannot be verified. No tools, no filesystem, no AWS or GitHub access. If it is disabled, errors or the PR is from a fork, the comment says so and everything else is identical.

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
| `terraform.conventions.layout` | Opt-in rules TF-004 / TF-006 for a family of roots |

## Code map

| File | What it does |
| --- | --- |
| `tools/reviewer/engine.py` | Coordinator and command line (`check`, `review`, `discover`, `plan-summary`). Runs the review in order and computes the deterministic verdict. |
| `tools/reviewer/repo.py` | Reads the repository: scans `.tf` files into blocks, builds the module-call graph, finds roots and modules, and maps a change to the roots and modules it affects. |
| `tools/reviewer/checks.py` | The checks. Contract checks (`MOD-*`, `GOV-*`, `AWS-001`, `NET-001`, `TF-*`) read the code; plan checks (`PLAN-*`) read the plan and the cost. Each is registered under the name `rules.yaml` uses. |
| `tools/reviewer/rules.yaml` | The review contract: id, severity, title, explanation and parameters of each rule. The only source of truth for the checks. |
| `tools/reviewer/plan.py` | Reduces `terraform show -json` to counts and sanitized changes; state and sensitive values are dropped. |
| `tools/reviewer/cost.py` | Reduces Infracost JSON to totals, delta, per-resource cost and what could not be priced. Prices come only from here. |
| `tools/reviewer/report.py` | Builds the PR comment in Markdown from the review result. |
| `tools/reviewer/sanitize.py` | Redacts credentials and blocks sensitive file types before anything is shared. |
| `tools/reviewer/model.py` | The `Finding` structure and severity order. |
| `tools/reviewer/ai/` | The optional layer: `client.py` (Gemini, one method), `reviewer.py` (payload, call, schema check), `grounding.py` (verifies the cited addresses, files and prices), `prompt.md`, `schema.json`. |
| `.github/workflows/pull-request.yml` | The PR pipeline: discovery, checks on affected modules, a plan per affected root, the comment. |
| `.github/workflows/terraform.yml` | `init` → `plan` → `apply` for a root: called by PRs for a plan, on push for an apply, or by hand. Selects the branch's keys and checks the account. |

## Known limits

- Checkov runs with `--soft-fail` until its findings on the modules are triaged.
- Infracost may not price resources it cannot resolve in a plan (for example an Auto Scaling Group whose launch template is created in the same plan); the cost section lists what it could not price.
- Roots are applied in path order; dependencies between roots are not modelled.
- Production means the repository's default branch.
- The reviewer's unit tests live outside this repository.
