# What each file is

[← README](../README.md)

Every file and folder in the repository: what it does, what it is for and what it represents.

## Root

| File | What it is |
| --- | --- |
| `README.md` | Entry point: what the project is, the architecture and where to start. |
| `common.yaml` | The shared configuration. Terraform reads `project` (tags and names); the pipeline and the reviewer read `backend`, `ai`, and `terraform` (`accounts`, `deploy`, and the optional `roots`, `modules`, `protected`, `conventions`). It represents the one place a team edits to adapt the platform to its accounts. |
| `.terraform-version` | The Terraform version for local tooling (for example tfenv). A change to it makes every root "affected". |
| `.tflint.hcl` | TFLint configuration: the Terraform and AWS rule sets and the enabled rules (required version and providers, documented and typed variables and outputs, naming). |
| `.gitignore` | Keeps out state, plans, the Python environment, the `backend.tf` the pipeline generates and editor history. |
| `.geminiignore` | The files the AI summary must not read when it builds the review (one pattern per line). Secrets and state are always blocked by the code, whatever this file says; this list is for what else the AI does not need. |

## `.github/workflows/`: the pipeline

| File | What it does |
| --- | --- |
| `pull-request.yml` | Runs on every pull request. Discovers the affected roots and modules, runs `fmt`, `validate`, TFLint, Checkov and the repository contract, asks `terraform.yml` for a read-only plan of each affected root, then builds the review comment. A PR into production skips the five checks and runs plan, cost and review only. |
| `terraform.yml` | The only workflow that touches AWS. For one root it selects the branch's keys, verifies the account, checks the state bucket, then runs `init` → `plan` → (`apply`). Called by PRs for a plan, triggered by a push to `develop` or `main` for an apply, or started by hand. |

## `tools/reviewer/`: the reviewer

A Python package that the workflows run: each step calls its own file, for example `python -m reviewer.ci.terraform_init`. Its only
dependency is PyYAML. Each folder is one concern:

```
git_diff → what changed  ─►  terraform/ → what it affects  ─►  rules/ → which rules it breaks
                                                                    │
                          review/ → verdict and PR comment  ◄───────┘          ai/ → optional summary
```

| Folder / file | What it is |
| --- | --- |
| `ci/` | What the workflows run, one file per step. |
| `terraform/` | Understanding the Terraform code and the plan. |
| `rules/` | The contract: the catalog of rules and the code that checks them. |
| `review/` | The review itself: the verdict and the PR comment. |
| `infracost/`, `aws/` | Reading the Infracost data; checking which AWS account the keys belong to. |
| `ai/` | The optional AI summary. |
| `redact_secrets.py` | Hides credentials in any text, and decides which files the AI must not read: a fixed floor of sensitive types plus the repository's `.geminiignore`. |

### `terraform/`: understanding the Terraform code and the plan

| File | What it does |
| --- | --- |
| `read_tf_files.py` | Reads a `.tf` file and finds its blocks (`resource`, `module`, `variable`...) and their attributes. |
| `terraform_map.py` | The map of the repository: which folders are roots and which are modules, which module calls which, and which of them a set of changed files affects. Also reads the `terraform:` block of `common.yaml`. |
| `affected_roots.py` | Which roots to act on for a target branch (applying `terraform.deploy`). The decision the workflows rely on. |
| `read_plan_json.py` | Reads the plan (`terraform show -json`) and reduces it to counts and sanitized changes, without state, variable values or secrets. |
| `run_terraform.py` | The one place that starts the `terraform` program in a folder. It knows nothing about GitHub or AWS. |

### `rules/`: the contract

| File | What it does |
| --- | --- |
| `rules.yaml` | The catalog: one entry per rule (id, severity, title, explanation, parameters). The only source of truth. |
| `code_rules.py` | The rules that read the `.tf` files: `MODULE-*`, `TAGS-*`, `ROOT-*` and `COST-001`. |
| `plan_rules.py` | The rules that read the plan and the cost estimate: `PLAN-001` and `COST-002`. |
| `registry.py` | Connects a rule's `check:` name to its function, builds findings, and runs the plan rules. |

The list of rules is in [The checks](checks.md).

### `review/`: the review itself

| File | What it does |
| --- | --- |
| `finding.py` | The shape of a finding (severity, evidence, file, line, rule...) that every rule returns, and the severity order. It is the form a rule fills in to report a problem; it does not say how modules must be built (that is the [module standard](module-standard.md)). |
| `run_review.py` | One review, in order: affected roots, findings, the deterministic verdict and the optional AI summary. |
| `markdown_report.py` | Builds the PR comment in Markdown from a review result. |

### `infracost/` and `aws/`: the cost data and the AWS account

| File | What it does |
| --- | --- |
| `infracost/read_infracost_json.py` | Reads the Infracost result and reduces it to totals, the monthly delta, per-resource cost and what could not be priced. It never runs Infracost and never estimates a price: prices come only from here. |
| `aws/account.py` | Picks the AWS keys of a branch, asks AWS which account they belong to, and checks the state bucket exists. |

### `ci/`: one file per step of the workflows

Each file is the code one step runs. It reads the environment variables the workflow passes, asks which roots and modules the PR
affects, runs the tool and writes back what the workflow needs (step outputs, the job summary, the comment). The name is the name
of the step you see in GitHub.

| File | Step | What it does |
| --- | --- | --- |
| `git_diff.py` | (the starting point) | `git diff base...HEAD`: the files a PR changes, the first thing every other step asks. Only committed changes count. |
| `discover_roots.py` | affected configurations | The roots (or modules) a PR affects, for the target branch; also listed on screen when you run it by hand. |
| `select_roots.py` | which roots (terraform.yml) | The roots a `terraform.yml` run acts on: those a push affected, or the one asked for. |
| `contract_check.py` | repository contract | The rules that read the code; exits with an error on any High or Critical finding. |
| `terraform_validate.py` | terraform validate | `terraform validate` in the modules and roots a PR affects, with one shared provider cache. |
| `terraform_tflint.py` | TFLint | TFLint, with the repository's `.tflint.hcl`, on the affected modules. |
| `terraform_checkov.py` | Checkov | Checkov on the affected modules; publishes the number of findings. |
| `terraform_init.py` | terraform init | Picks the branch's AWS keys, checks their account against `terraform.accounts`, checks the state bucket, then `terraform init`. |
| `terraform_plan.py` | terraform plan | `terraform plan` of one root, saved to `tfplan`. |
| `terraform_show_json.py` | terraform show -json | The saved plan as JSON (`terraform show -json`) reduced to a sanitized summary the review reads. The raw plan is never written to disk. |
| `infracost_estimate.py` | infracost | The Infracost estimate of the plan, written to `cost-<slug>.json`. It decides by itself whether to run (only a plan, only with an Infracost key) and installs the pinned Infracost release, verifying its checksum, if the machine does not have it. |
| `terraform_apply.py` | terraform apply | Applies the saved plan. Does nothing when the run is only a plan. |
| `pr_review.py` | PR comment | Builds the review and the text of the comment. |
| `local_review.py` | (by hand) | A full review from your machine, with the plan, cost and check results you give it |
| `pr_comment.py` | PR comment | Creates or updates the single PR comment through the GitHub API. |
| `github_actions.py` | (helpers) | Writes to the files GitHub Actions reads (`$GITHUB_OUTPUT`, `$GITHUB_STEP_SUMMARY`), reports errors, and works out whether a run is a plan or an apply and which branch it belongs to. |

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
| `elb/alb` | An Application Load Balancer: HTTP/HTTPS listeners, forwarding rules, redirects, optional WAF and access logs. |
| `elb/nlb` | A Network Load Balancer with target groups and listeners. |
| `ec2/launch-template` | A hardened launch template (IMDSv2, encrypted root volume), shared by `ec2/instances` and `ec2/asg`. |
| `ec2/instances` | One or more standalone EC2 instances from a launch template, private by default. |
| `ec2/asg` | An Auto Scaling Group over a launch template, with rolling refresh, tag propagation and scaling policies. |
| `eks/cluster` | An EKS control plane: private endpoint by default, access entries, logging, optional secrets encryption and an IRSA provider. |
| `eks/node-group` | EKS managed node groups, expressed as intent. |
| `eks/addons` | EKS managed add-ons, installed only when listed. |

## `infra-example/`: root configurations built from the modules

A web tier in a VPC: an Application Load Balancer in front of an Auto Scaling Group of instances, backed by Aurora. `dev/web-demo` and `prod/web-demo` are two roots with their own state; they share the code and differ in `inputs.yaml`, plus the production policy that `main.tf` enforces.

| File | What it is |
| --- | --- |
| `main.tf` | Reads `common.yaml` and `inputs.yaml` into `locals` and validates them with preconditions (required keys, folder name, subnets per zone, the production policy). |
| `network.tf` | The VPC and the three security groups (load balancer, app, database). |
| `database.tf` | The Aurora cluster. |
| `load_balancer.tf` | The Application Load Balancer, target group and listener. |
| `web.tf` (`ec2.tf` in prod) | The instance role, the launch template and the Auto Scaling Group. |
| `outputs.tf` | The values the root exposes (DNS name, endpoints, secret ARN, summary). |
| `inputs.yaml` | The values of this root: tags, network, security rules, database, load balancer, compute. The only file that differs between dev and prod in intent. |
| `web-user-data.sh.tftpl` | The boot script of the web instances (a placeholder web server with `/health`). |
| `infra-example/README.md` | The example's own notes: inputs reference and design notes. |

## `docs/`

| File | What it is |
| --- | --- |
| `install.md` | Setup, from an empty repository to the first PR. |
| `architecture.md` | How discovery, branches and accounts, state, the pipelines, the reviewer and the AI boundary work. |
| `module-standard.md` | The contract every module follows. |
| `files.md` | This file. |
| `checks.md` | Every rule the reviewer enforces: ID, severity, what it flags and where it lives. |
| `images/` | `hero.svg` and `architecture.svg`, used by the README. |
