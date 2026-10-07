# terra-ai — Terraform Module Engineering Platform

A reusable Terraform module library, the environments built from it, and a pull-request reviewer that enforces **this
repository's own contract** on top of the standard tools. Code decides pass or fail; Gemini is an optional layer that only
explains the evidence.

```text
terra-ai/
├── .github/workflows/
│   ├── pull-request.yml        discover affected configurations, checks, read-only plans, the PR comment
│   └── terraform.yml           plan / apply of the affected configurations (matrix), or one by hand
├── environments/               EXAMPLE root configurations (dev, prod); yours can live anywhere (infra/web, terraform/networking...)
├── modules/                    reusable capabilities, each with README and `terraform test`
├── tools/reviewer/
│   ├── rules.yaml              the review contract: the ONLY source of truth for checks.py
│   ├── checks.py               the organisation's checks: code contract + terraform plan
│   ├── engine.py               coordination, verdict (PASS | REQUEST_CHANGES) and command line
│   ├── model.py  repo.py  plan.py  cost.py  report.py  sanitize.py
│   └── ai/                     OPTIONAL: client.py · reviewer.py · grounding.py · prompt.md · schema.json
├── common.yaml                 project, state settings, ai.enabled, optional `terraform:`
└── README.md
```

(`.tflint.hcl`, `.terraform-version` and `.gitignore` are configuration of external tools, not architecture.)

## Terraform root configurations

A **root configuration** is a folder with its own state, planned and applied on its own. Nothing in the tooling assumes
`environments/`, `dev` or `prod`: the `terraform:` block of `common.yaml` says which folders are roots (`roots` globs, or
inferred: a folder nobody calls as a module that has resources, modules, a provider or a backend), where the shared modules
live (`modules`) and which roots are `protected` (destroying stateful resources is CRITICAL there; a PR into `main` protects all).

For every PR, `engine.py discover` computes the **affected** roots: the ones with edited files, the ones that use an edited
module (transitively, by local `source`) and the ones that read an edited shared file (`file()`, `templatefile()`,
`yamldecode(file())` with `../` paths). `.terraform-version` affects all; documentation and module tests affect none.
Only affected roots are validated, planned, reviewed and applied (init → plan → checks → cost → report); the rest are never
touched. The AI never decides what runs; it only receives the list of affected configurations as context.

```bash
PYTHONPATH=tools python -m reviewer.engine discover --base origin/main --format text   # or json | matrix
```

The environment comes from the branch, not from folders: PRs and merges to `develop` use the GitHub Environment `develop`,
those to `main` use `main`. Optional `terraform.conventions.layout` (used by the `environments/*` example) enables TF-004 / TF-006: allowed files per
root and files that must be identical across the family. Without it those rules do nothing. Roots that depend on each other
(networking before workloads) are applied one at a time in path order; cross-root ordering beyond that is not modelled.

## How a pull request is judged

Each tool is the authority for its own domain; `reviewer` is not another Checkov or TFLint.

| Concern | Authority |
|---|---|
| Syntax, validation, plan, module tests | `terraform fmt` / `validate` / `test` / `plan` |
| Lint (required versions and providers, documented variables and outputs, naming) | TFLint (`.tflint.hcl`) |
| Generic security (open ingress, secrets, public endpoints, encryption) | Checkov |
| Prices | Infracost (the reviewer only reads its numbers) |
| Module boundaries, naming, mandatory tags, root layout, plan and cost correlated with the standards | **`reviewer`** (`rules.yaml`) |
| Intent versus plan, architectural impact, a summary for a human | the optional AI layer |

1. **Deterministic review.** `engine.py` runs the contract checks on the code and the plan checks on the sanitized
   `terraform plan` and the Infracost estimate, and computes the verdict: `REQUEST_CHANGES` if any confirmed finding is HIGH
   or CRITICAL or any external check failed; otherwise `PASS` (lower severities are still listed). There is no approve and
   no merge.
2. **The PR comment is built by code** (`report.py`): tests, plan, replacements, cost, governance, module standard.
3. **Optional AI analysis.** Gemini receives a controlled, sanitized payload and returns three texts validated against
   `ai/schema.json`: *Intent vs Infrastructure*, *Architecture Impact* and *Reviewer Summary*. It returns no findings, so it
   cannot add, reword or remove one, and it cannot change the verdict.

**Trust boundary.** The payload holds the repository context (derived from the repo itself), the PR title and description,
the changed files, the plan summary and replacements, the cost estimate, the check results and the deterministic findings;
never state, `.terraform`, credentials or the whole repository. Sensitive files are skipped and secrets are redacted before
anything is sent. Gemini has no tools, no filesystem, no shell and no AWS or GitHub access: it receives text and returns
text. The safety comes from the architecture, not from the prompt: the answer is schema-validated (one retry) and every
Terraform address, file and price it mentions is checked against the evidence; what cannot be verified is replaced by
`<unverified …>` and flagged in the comment.

**Failure behaviour.** The AI step is off by default (`ai.enabled: false` in `common.yaml`) and needs `GEMINI_API_KEY`. If it
is disabled, has no key, fails, returns invalid output twice, or the PR comes from a fork, the comment is identical except
for the *AI Analysis* section, which says `AI review was not executed.` and why.

## The review contract (`rules.yaml`)

| Rule | Severity | Title |
|---|---|---|
| `MOD-001` | HIGH | Reusable capability implemented outside its module |
| `MOD-002` | MEDIUM | Module is missing required contract files |
| `MOD-003` | MEDIUM | Resource does not follow the `this` naming convention |
| `MOD-004` | MEDIUM | Variable uses `type = any` |
| `MOD-006` | MEDIUM | Domain component placed outside its domain directory |
| `GOV-001` | HIGH | Taggable resource does not receive mandatory tags |
| `GOV-002` | MEDIUM | Module does not expose the mandatory-tag input contract |
| `GOV-003` | HIGH | Auto Scaling Group does not propagate mandatory tags |
| `AWS-001` | HIGH | Auto Scaling Group managed directly for EKS |
| `NET-001` | MEDIUM | NAT gateway per AZ in a non-protected configuration |
| `TF-003` | MEDIUM | Module has no terraform test files |
| `TF-004` | HIGH | Root configuration does not follow its (optional) layout |
| `TF-006` | HIGH | A root's files differ from its siblings' (optional layout) |
| `PLAN-001` | CRITICAL | Plan destroys or replaces a stateful resource (database, bucket, key, cluster) |
| `PLAN-002` | MEDIUM | Infracost reports a large monthly increase |

To add a rule: add it to `rules.yaml` with `id`, `category`, `severity`, `check`, `title`, `explanation`, `recommendation`,
and implement `@check("<name>")` (code) or `@plan_check("<name>")` (plan) in `checks.py`.

## Module standard

The contract every module in `modules/` follows. Rule IDs refer to `rules.yaml`.

**Scope and boundaries**
- A module is one **reusable capability** (VPC, Lambda, S3, Aurora, ALB, IAM, ...), usable independently and never tied to one
  environment. A capability MUST live in its module; root configurations consume modules and MUST NOT declare the underlying
  resources (`MOD-001`).
- Multi-component domains live under `modules/<domain>/<component>`: `eks` (cluster, node-group, addons), `ec2`
  (launch-template, instances, asg) and `elb` (nlb, alb). Load balancers are not part of the EC2 domain. Top-level
  `modules/eks-*`, `ec2-*`, `elb-*`, `nlb` or `alb` are forbidden (`MOD-006`).
- `ec2/instances` and `ec2/asg` consume `ec2/launch-template`; the hardened instance definition (IMDSv2, encryption, tags)
  lives only there. EKS capacity is expressed through `eks/node-group`, never a raw Auto Scaling Group (`AWS-001`).
- Modules do not configure providers and do not call modules of another domain; cross-capability wiring happens in the
  environment.

**Structure** (`MOD-002`, `TF-003`): `versions.tf`, `variables.tf`, `outputs.tf`, `README.md` and `tests/*.tftest.hcl` are
required; `main.tf`, `locals.tf` and `data.tf` as needed.

**Public API**
- Inputs express *intent*, not provider plumbing (`groups = { system = {...} }`). Every variable has a `type` and a
  `description`; `type = any` is forbidden (`MOD-004`); use `object`, `map(object)` and `optional()`.
- Add `validation` for CIDRs, enums, size ranges, names and mutually exclusive options; cross-variable invariants use
  `lifecycle.precondition`. Defaults are secure and cost-conscious (no NAT, private, encrypted, versioned).
- Outputs have a `description`, expose the IDs and ARNs consumers need and never secrets. Breaking changes need a major
  version and a migration note.
- Documented variables/outputs and bounded `required_version` / provider ranges are enforced by TFLint.

**Mandatory tags** (`GOV-001`, `GOV-002`, `GOV-003`): every taggable resource gets `Name`, `Environment`, `Owner`,
`CostCenter`, `Project` and `ManagedBy` (literal `"terraform"`). Modules take a `tags` object (`environment`, `owner`,
`cost_center`, `project`) and a free-form `extra_tags` map; `locals.tags = merge(var.extra_tags, local.mandatory_tags)` so
the mandatory tags always win. Auto Scaling Groups use `tag` blocks with `propagate_at_launch`. Provider `default_tags` do not
replace this.

**Naming** (`MOD-003`): the primary resource of a type is `this`; extra ones use role names (`public`, `private`); variables,
outputs and locals are snake_case without a type prefix; arbitrary names (`prod_bucket`, `my_bucket`, `bucket123`) are
forbidden. Physical names are `<project>-<env>-<component>[-<qualifier>]`, built in `locals`; per-AZ resources append the AZ;
every taggable resource has a `Name` tag equal to its physical name. Tag keys are PascalCase.

**Terraform style**: Terraform `>= 1.7` (`mock_provider`); `for_each` over `count` (keys are stable identifiers, never list
indexes), `count` only for 0/1 toggles; `dynamic` blocks only for genuinely optional or repeated nested blocks; no hard-coded
accounts, regions or AZs; secrets never in source (`sensitive = true`); `moved` blocks for every rename; `depends_on` as a
last resort and commented; no `local-exec` or `null_resource` unless unavoidable.

**Lifecycle**: stateful resources expose a protection strategy (deletion protection, `force_destroy = false`); every
`ignore_changes` is commented with the system that owns the attribute; the README documents which inputs force replacement.

**Testing**: each module ships `tests/*.tftest.hcl` with `mock_provider` (no credentials) covering secure defaults, resource
counts, mandatory tags (callers cannot override them), one `expect_failures` run per non-trivial validation and each mode of
enum-like inputs.

**Documentation**: each module README has, in order: purpose and non-goals, usage, resources and which are taggable, inputs
and outputs, mandatory tags, lifecycle notes (what forces replacement), cost notes and how to run the tests.

**Maintainability**: one responsibility per module (split when two lifecycles are mixed); no copy-pasted logic between modules;
deprecate before removing.

## Modules

`vpc`, `s3`, `security-group`, `iam`, `aurora` (PostgreSQL or MySQL via `engine`), `lambda`, `eventbridge`, `api-gateway`
(HTTP API + VPC Link V2), `elb/{alb,nlb}`, `ec2/{launch-template,instances,asg}`, `eks/{cluster,node-group,addons}`. Each has
its README (usage, tags, lifecycle, cost) and a `terraform test` suite.

## Using it

```bash
# an environment (see environments/README.md): credentials + region from the environment, no wrapper tool
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-1
cd environments/dev && terraform init && terraform plan

# module tests, no credentials
cd modules/vpc && terraform init -backend=false && terraform test

# the reviewer, no installation (only PyYAML)
python -m pip install pyyaml
PYTHONPATH=tools python -m reviewer.engine check --all
PYTHONPATH=tools python -m reviewer.engine review --base origin/main --markdown review.md           # AI off
GEMINI_API_KEY=... PYTHONPATH=tools python -m reviewer.engine review --base origin/main --ai --markdown review.md
PYTHONPATH=tools python -m reviewer.engine review --base origin/main --print-ai-payload              # what Gemini would see
```

Credentials and the GitHub setup (Environments, secrets, variables) are in [environments/README.md](environments/README.md).

## Roadmap

Not built yet: `sqs`, `vpc-endpoints` and an EKS microservices environment (API Gateway → VPC Link → private NLB → EKS →
Aurora). Design notes for that one: a **VPC Link** (HTTP API: `aws_apigatewayv2_vpc_link`; REST API: `aws_api_gateway_vpc_link`)
carries API Gateway → private NLB traffic, while **VPC endpoints** carry workload → AWS-service traffic; they are different
mechanisms and different modules. Gateway endpoints (S3, DynamoDB) are free; interface endpoints (ECR, STS, Logs, Secrets
Manager) cost per AZ-hour and are added only where NAT is avoided.

## Known limits

- Gemini and Infracost have only been exercised through fakes and mocked data; the workflows have not run on GitHub. Verify
  them on a first real PR.
- The HCL scanner is shallow by design (blocks in column 0, as `terraform fmt` leaves them); grounding of the AI text is
  heuristic and flags what it cannot verify.
- The reviewer has no unit tests in this tree by design (the structure is fixed); module behaviour is covered by the modules'
  own `terraform test` suites.
