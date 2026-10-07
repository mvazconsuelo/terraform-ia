# Module standard

The contract every module in `modules/` follows. Rule IDs refer to [`tools/reviewer/rules.yaml`](../tools/reviewer/rules.yaml).

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
  root configuration.

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
