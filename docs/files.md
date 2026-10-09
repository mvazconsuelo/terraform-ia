# What each file is

English · [Español](es/files.md)

Every file and folder in the repository: what it does, what it is for and what it represents.

## Root

| File | What it is |
| --- | --- |
| `README.md`, `README.es.md` | Entry point: what the project is, the architecture and where to start. English is the default; the Spanish version is `README.es.md`. |
| `common.yaml` | The shared configuration of the project. Each root reads its `project` and its `environment` from it (the environment is the one whose list of roots has the root; owner and cost center are in the root's `inputs.yaml`); the pipeline and the reviewer read `project` (state bucket and checks) and `backend`, `ai`, and `terraform` (`environments`, each with its `branch` and `roots`, and the optional `roots`, `modules`, `protected`, `conventions`). It represents the one place a team edits to adapt the platform to its accounts. |
| `.terraform-version` | The Terraform version for tools such as tfenv (the workflows pin `~> 1.16.0`). A change to it makes every root "affected". |
| `.tflint.hcl` | TFLint configuration: the Terraform and AWS rule sets and the enabled rules (required version and providers, documented and typed variables and outputs, naming). |
| `LICENSE` | The MIT license: anyone may use, copy, modify and distribute the code, keeping the copyright notice. |
| `CONTRIBUTING.md`, `SECURITY.md` | How to propose something (an issue; pull requests are the maintainer's) and how to report a vulnerability (Spanish copies in `docs/es/contributing.md` and `docs/es/security.md`). GitHub shows them in the repository. |
| `CLAUDE.md` | What Claude Code reads in every session: how the repository works, where things live and every convention. The single place to change a convention. |
| `.claude/agents/terraform-ia-engineer.md` | The project's assistant for Claude Code. It reads `CLAUDE.md`, proposes and waits for approval, never runs commands, and gives you the git commands to run. |
| `.claude/settings.json`, `.claude/hooks/after_edit.py` | Claude Code runs the hook after every edit: `ruff` and `mypy` after a change in `tools/`, `terraform fmt` after a change in a `.tf` file. If a check fails, the output goes back to Claude so it fixes the file. `settings.json` also blocks the commands that belong to the owner: git writes (`add`, `commit`, `push`, `merge`...), `gh workflow run` and the other `gh` commands that publish or change settings, and `terraform apply`, `destroy`, `import` and `state`. |
| `.claude/skills/new-module/`, `new-rule/`, `new-root/` | The step-by-step lists for creating a module, adding a reviewer rule, and building infrastructure from the modules (a new environment or stack). Claude Code uses them when you ask for either; the agent follows them as its proposal. |
| `pyproject.toml` | Settings for `ruff` and `mypy` (the `python` job of every PR) and for `pytest` (the `tests` job). |
| `tests/` | Every test, in one place, run only by the pipeline: see [`tests/`](#tests-the-tests). |
| `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/` | The template of every pull request (what changes, kind of change, checklist) and the two issue forms (bug and improvement). Blank issues are off; a security problem goes to the private report. |
| `.github/CODEOWNERS` | Who reviews what: GitHub requests a review from the owner on every pull request that touches the workflows, the reviewer, `common.yaml`, the modules, the examples or the docs. |
| `.github/dependabot.yml` | Dependabot: one weekly pull request **into `develop`** that updates the GitHub Actions the workflows use, grouped in one. See [Dependency updates](architecture.md#dependency-updates-dependabot). |
| `.gitignore` | Keeps out state, plans, the Python environment, the `backend.tf` the pipeline generates and editor history. |

## `.github/workflows/`: the pipeline

| File | What it does |
| --- | --- |
| `pull-request.yml` | Runs on every pull request. Discovers the affected roots and modules, runs `fmt`, the Python checks (ruff, mypy), `validate`, TFLint, Checkov, the tests and the repository contract, asks `terraform.yml` for a read-only plan of each affected root, then builds the review comment. A PR into production skips those six checks and runs plan, cost and review only. |
| `terraform.yml` | The only workflow that touches AWS. For one root it selects the branch's keys, verifies the account, checks the state bucket, then runs `init` → `plan` → (`apply`). Called by PRs for a plan, or started by hand for a plan or an apply: merging never deploys. |

## `tools/`: the reviewer

A Python package that the workflows run: each step calls its own file, for example `python -m tools.ci.terraform_init`. Its only
dependency is PyYAML. Its code quality is enforced on every PR by the `python` job: `ruff` (errors, imports, likely bugs) and `mypy` (types), configured in `pyproject.toml`. Each folder is one concern:

```
lib/git_diff → what changed  ─►  terraform/ → what it affects  ─►  rules/ → which rules it breaks
                                                                    │
                          review/ → verdict and PR comment  ◄───────┘          ai/ → optional summary
```

| Folder / file | What it is |
| --- | --- |
| `ci/` | What the workflows run, one file per step. |
| `terraform/` | Understanding the Terraform code and the plan. |
| `rules/` | The contract: the catalog of rules and the code that checks them. |
| `review/` | The review itself: the verdict and the PR comment. |
| `infracost/`, `aws/`, `versions/` | Reading the Infracost data; checking which AWS account the keys belong to; looking up newer Terraform and provider releases. |
| `ai/` | The optional AI summary. |
| `chat/` | **Next, in development; not in the repository yet** (it is local and ignored by git). A read-only terminal chat with Gemini that will answer questions about the project from its documentation and, with `/reviews`, from the review comments of recent pull requests: plans, costs, versions, findings by date. |
| `lib/` | Helpers every other folder can use, none of them a workflow step: `git_diff.py` (the files a PR changes: `git diff base...HEAD`, committed changes only), `github_actions.py` (writes `$GITHUB_OUTPUT` and `$GITHUB_STEP_SUMMARY`, reports errors, tells the mode and the branch) `workflow_jobs.py` (the jobs of the current run with a link to each one, so the comment can link to their logs) and `redact_secrets.py` (hides credentials in the text and values the AI receives). |

### `terraform/`: understanding the Terraform code and the plan

| File | What it does |
| --- | --- |
| `read_tf_files.py` | Reads a `.tf` file and finds its blocks (`resource`, `module`, `variable`...) and their attributes. |
| `terraform_map.py` | The map of the repository: which folders are roots and which are modules, which module calls which, and which of them a set of changed files affects. Also reads the `terraform:` block of `common.yaml`. |
| `affected_roots.py` | Which roots to act on for a target branch (applying the roots of the environments of that branch). The decision the workflows rely on. |
| `read_plan_json.py` | Reads the plan (`terraform show -json`) and reduces it to counts and sanitized changes, without state, variable values or secrets. |
| `run_terraform.py` | The one place that starts the `terraform` program in a folder. It knows nothing about GitHub or AWS. |

### `rules/`: the contract

| File | What it does |
| --- | --- |
| `rules.yaml` | The catalog: one entry per rule (id, severity, title, explanation, parameters). The only source of truth. |
| `code_rules.py` | The rules that read the `.tf` files: `MODULE-*`, `TAGS-*`, `ROOT-001`, `ROOT-002` and `ROOT-005`. |
| `inputs_rules.py` | The rules that read a root's `inputs.yaml`: `ROOT-003`, `ROOT-004` and `POLICY-*`. The policy is data in `rules.yaml`. |
| `plan_rules.py` | The rules that read the plan and the cost estimate: `PLAN-*`. |
| `registry.py` | Connects a rule's `check:` name to its function, builds findings, and runs the plan rules. |

The list of rules is in [The checks](checks.md).

### `review/`: the review itself

| File | What it does |
| --- | --- |
| `finding.py` | The shape of a finding (severity, evidence, file, line, rule...) that every rule returns, and the severity order. It is the form a rule fills in to report a problem; it does not say how modules must be built (that is the [module standard](module-standard.md)). |
| `run_review.py` | One review, in order: affected roots, findings, the deterministic verdict and the optional AI summary. |
| `render_pr_comment.py` | Builds the text of the PR comment (Markdown) from a review result: eight sections, from the AI summary to the decision. |

### `infracost/`, `aws/` and `versions/`: the cost data, the AWS account and the releases

| File | What it does |
| --- | --- |
| `infracost/read_infracost_json.py` | Reads the Infracost result and reduces it to totals, the monthly delta, per-resource cost and what could not be priced. It never runs Infracost and never estimates a price: prices come only from here. |
| `versions/latest_versions.py` | Looks up the latest Terraform and provider releases (HashiCorp's release check and the Terraform Registry), compares them with the ones the plan used and gives the release-notes link. It only informs: it never changes a file or the verdict, and if a lookup fails the comment says so. |
| `aws/account.py` | Picks the AWS keys of a branch, asks AWS which account they belong to, and checks the state bucket exists. |

### `ci/`: one file per step of the workflows

Each file is the code one step runs. It reads the environment variables the workflow passes, asks which roots and modules the PR
affects, runs the tool and writes back what the workflow needs (step outputs, the job summary, the comment). The name is the name
of the step you see in GitHub.

| File | Step | What it does |
| --- | --- | --- |
| `discover_roots.py` | affected configurations | The roots a PR affects and its target branch owns: gives the workflow the matrix for the plan jobs, how many there are, and the list with the reasons. |
| `select_roots.py` | which roots (terraform.yml) | The root a `terraform.yml` run acts on: the one asked for (a manual run must also belong to an environment of its branch). |
| `contract_check.py` | repository contract | The rules that read the code, over the whole repository; fails on any High or Critical finding. |
| `run_tests.py` | tests | The tests of the reviewer (`pytest`) and of the modules (`terraform test`, AWS mocked), no secrets. A failure makes the verdict `REQUEST_CHANGES`. |
| `terraform_validate.py` | terraform validate | `terraform validate` in the modules and roots a PR affects, with one shared provider cache. |
| `terraform_tflint.py` | TFLint | TFLint, with the repository's `.tflint.hcl`, on the affected modules. |
| `terraform_checkov.py` | Checkov | Checkov on the affected modules; publishes the number of findings. |
| `terraform_init.py` | terraform init | Picks the branch's AWS keys, checks their account against the repository variable of the branch, checks the state bucket, then `terraform init`. |
| `terraform_plan.py` | terraform plan | `terraform plan` of one root, saved to `tfplan`. |
| `terraform_show_json.py` | terraform show -json | The saved plan as JSON (`terraform show -json`) reduced to a sanitized summary the review reads. The raw plan is never written to disk. |
| `terraform_versions.py` | terraform versions | Records which Terraform and provider versions the plan used, in `versions-<slug>.json`. Informational: it never fails the job. |
| `infracost_estimate.py` | infracost | The Infracost estimate of the plan, written to `cost-<slug>.json`. It decides by itself whether to run (only a plan, only with an Infracost key) and installs the pinned Infracost release, verifying its checksum, if the machine does not have it. |
| `terraform_apply.py` | terraform apply | Applies the saved plan. Does nothing when the run is only a plan. |
| `pr_review.py` | PR comment | Collects the check results, plans and costs, runs the review and writes the comment text. Never fails the job. |
| `pr_comment.py` | PR comment | Creates or updates the single PR comment through the GitHub API. |

### `ai/`: the optional layer

| File | What it does |
| --- | --- |
| `summary.py` | The AI step: builds the sanitized payload, calls the model, validates the answer against the schema and grounds the text. Runs only after the verdict is final. |
| `client.py` | Talks to Gemini through its REST API behind a one-method interface. Retries temporary errors. |
| `grounding.py` | Checks every Terraform address, file path and dollar amount in the model's text against the evidence; what cannot be verified is replaced by `<unverified …>`. |
| `prompt.md` | The system prompt: what the model receives, what it may and may not do, and the shape of the summary. |
| `schema.json` | The contract of the answer: one field, `summary`. |

## `modules/`: reusable AWS capabilities

Each module has the same files: `versions.tf` (Terraform and provider constraints), `variables.tf` (typed, validated inputs), `main.tf` (resources), `locals.tf` (names and tags), `outputs.tf`, and `README.md`. The rules are in the [module standard](module-standard.md).

| Module | Creates |
| --- | --- |
| `vpc` | A VPC with a private tier, an optional public tier, per-AZ route tables, opt-in NAT and a free S3 gateway endpoint. |
| `security-group` | A least-privilege security group with one resource per rule; no rules and no egress by default. |
| `iam` | An IAM role with trust policy, managed and inline policies and an optional instance profile. |
| `s3` | A private, encrypted, versioned bucket with a TLS-only policy and optional lifecycle rules. |
| `aurora` | An Aurora cluster, PostgreSQL or MySQL (the `engine` input selects it). |
| `lambda` | A Lambda function with its log group, optional VPC attachment, dead-letter queue and tracing. |
| `eventbridge` | EventBridge rules and targets on the default or a custom bus, with retries, dead-letter queue and invoke permissions. |
| `api-gateway` | An HTTP API with Lambda and private (VPC Link) integrations, access logs and throttling. |
| `acm` | A public ACM certificate validated by DNS, with its Route 53 validation records. |
| `route53/zone` | A Route 53 hosted zone, public or private, protected from deletion with records. |
| `route53/records` | Route 53 records in an existing zone: standard records and aliases. |
| `elb/alb` | An Application Load Balancer: HTTP/HTTPS listeners, forwarding rules, redirects, optional WAF and access logs. |
| `elb/nlb` | A Network Load Balancer with target groups and listeners. |
| `ec2/launch-template` | A hardened launch template (IMDSv2, encrypted root volume), shared by `ec2/instances` and `ec2/asg`. |
| `ec2/instances` | One or more standalone EC2 instances from a launch template, private by default. |
| `ec2/asg` | An Auto Scaling Group over a launch template, with rolling refresh, tag propagation and scaling policies. |
| `eks/cluster` | An EKS control plane: private endpoint by default, access entries, logging, optional secrets encryption and an IRSA provider. |
| `eks/node-group` | EKS managed node groups, expressed as intent. |
| `eks/addons` | EKS managed add-ons, installed only when listed. |

## `infra-example/`: root configurations built from the modules

A web tier in a VPC: an Application Load Balancer in front of an Auto Scaling Group of instances, backed by Aurora. `dev/web-demo` and `prod/web-demo` are two roots with their own state; they share the code and differ in `inputs.yaml`, plus the production policy that the reviewer enforces (`POLICY-001`).

| File | What it is |
| --- | --- |
| `main.tf` | Reads `inputs.yaml` and `common.yaml`, and works out the root's environment and tags (`local.tags`). It defines no values and validates nothing itself: the modules validate their own inputs and the reviewer checks the project's policy. |
| `network.tf` | The VPC and the three security groups (load balancer, app, database). |
| `database.tf` | The Aurora cluster. |
| `load_balancer.tf` | The Application Load Balancer, target group and listener. |
| `data.tf` | The data sources of the root (the IAM policy to read the database secret). Every `data` block lives here, never in the files that create resources. |
| `ec2.tf` | The instance role, the launch template and the Auto Scaling Group. |
| `outputs.tf` | The values the root exposes (DNS name, endpoints, secret ARN, summary). |
| `inputs.yaml` | The values of this root: tags, network, security rules, database, load balancer, compute. The only file that differs between dev and prod in intent. |
| `web-user-data.sh.tftpl` | The boot script of the web instances (a placeholder web server with `/health`). |
| `README.md`, `README.es.md` (in `infra-example/`) | The example's own notes (English and Spanish): layout, `inputs.yaml` reference, what is checked and design notes. |

## `tests/`: the tests

All the tests live here and **only the pipeline runs them** (job `tests`, step `tools/ci/run_tests.py`). A failed test makes the verdict `REQUEST_CHANGES`.

| Path | What it tests |
| --- | --- |
| `reviewer/conftest.py` | What the tests share: `sandbox` (a copy of the repository to break on purpose) and `findings_of` (what a rule finds in it). |
| `reviewer/test_rules_module.py`, `test_rules_root.py`, `test_rules_policy.py`, `test_rules_plan.py` | One file per theme of `rules.yaml`. Every rule has a test that flags it (`test_<rule id>_flags_<what>`). |
| `reviewer/test_every_rule_has_tests.py` | Fails when a rule has no test that flags it, or when the repository breaks one of its own rules. |
| `reviewer/test_verdict.py` | `PASS` or `REQUEST_CHANGES` from the findings and the checks. |
| `reviewer/test_account_guard.py` | Which account the keys of a branch must belong to (the repository variables), that the PR comment shows only the last four digits, and that no account id is written in `common.yaml`. |
| `reviewer/test_select_roots.py`, `test_affected_roots.py` | Which roots a run or a change reaches, and what a branch may deploy. |
| `reviewer/test_redact_secrets.py` | That keys and passwords are hidden before anything leaves the repository. |
| `reviewer/test_every_module_has_a_terraform_test.py` | Fails when a module has no test in `terraform/`, except the modules listed in its `PENDING` (the backlog). |
| `terraform/<module path with _>.tftest.hcl` | One per module (`elb_alb`, `security_group`...). `terraform test` with the AWS provider mocked: a plan with the minimum inputs, what the module resolves or picks, and the inputs it rejects. |

## `docs/`

| File | What it is |
| --- | --- |
| `install.md` | Setup, from an empty repository to the first PR. |
| `claude.md` | How to work with Claude Code: what the repository gives it (agent, skills, hook, blocks), how to start it and the flow with the agent. |
| `architecture.md` | How discovery, branches and accounts, state, the pipelines, the reviewer and the AI boundary work. |
| `module-standard.md` | The contract every module follows. |
| `files.md` | This file. |
| `checks.md` | Every rule the reviewer enforces: ID, severity, what it flags and where it lives. |
| `es/` | The same documentation in Spanish (`install`, `architecture`, `checks`, `files`, `module-standard`). English is the default language. |
| `images/` | `hero.svg` and `architecture.svg`, used by the README, and `pr-review/`: screenshots of a real review comment. The stack logos in the diagram come from [Simple Icons](https://simpleicons.org) (CC0); the names and marks belong to their owners. |

---

[← Previous: How it works](architecture.md) · [README](../README.md) · [Next: The checks →](checks.md)
