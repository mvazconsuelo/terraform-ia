# Module standard

[← README](../README.md) · English · [Español](es/module-standard.md)

The contract every module in `modules/` follows. Rule IDs refer to [`tools/reviewer/rules/rules.yaml`](../tools/reviewer/rules/rules.yaml).

**Scope and boundaries**
- A module is one **reusable capability** (VPC, Lambda, S3, Aurora, ALB, IAM, ...), usable independently and never tied to one
  environment. A capability MUST live in its module; root configurations consume modules and MUST NOT declare the underlying
  resources (`MODULE-001`).
- Multi-component domains live under `modules/<domain>/<component>`: `eks` (cluster, node-group, addons), `ec2`
  (launch-template, instances, asg) and `elb` (nlb, alb). Load balancers are not part of the EC2 domain. Top-level
  `modules/eks-*`, `ec2-*`, `elb-*`, `nlb` or `alb` are forbidden (`MODULE-005`).
- `ec2/instances` and `ec2/asg` consume `ec2/launch-template`; the hardened instance definition (IMDSv2, encryption, tags)
  lives only there. EKS capacity is expressed through `eks/node-group`, never a raw Auto Scaling Group (`MODULE-006`).
- Modules do not configure providers and do not call modules of another domain; cross-capability wiring happens in the
  root configuration.

**Structure** (`MODULE-002`): `versions.tf`, `variables.tf`, `outputs.tf` and `README.md` are
required; `main.tf`, `locals.tf` and `data.tf` as needed.

**Public API**
- Inputs express *intent*, not provider plumbing (`groups = { system = {...} }`). Every variable has a `type` and a
  `description`; `type = any` is forbidden (`MODULE-004`); use `object`, `map(object)` and `optional()`.
- Add `validation` for CIDRs, enums, size ranges, names and mutually exclusive options; cross-variable invariants use
  `lifecycle.precondition`. Defaults are secure and cost-conscious (no NAT, private, encrypted, versioned).
- Outputs have a `description`, expose the IDs and ARNs consumers need and never secrets. Breaking changes need a major
  version and a migration note.
- Documented variables/outputs and bounded `required_version` / provider ranges are enforced by TFLint.

**Mandatory tags** (`TAGS-001`, `TAGS-002`, `TAGS-003`): every taggable resource gets `Name`, `Environment`, `Owner`,
`CostCenter`, `Project` and `ManagedBy` (literal `"terraform"`). Modules take a `tags` object (`environment`, `owner`,
`cost_center`, `project`) and a free-form `extra_tags` map; `locals.tags = merge(var.extra_tags, local.mandatory_tags)` so
the mandatory tags always win. Auto Scaling Groups use `tag` blocks with `propagate_at_launch`. Provider `default_tags` do not
replace this.

**Naming** (`MODULE-003`): the primary resource of a type is `this`; extra ones use role names (`public`, `private`); variables,
outputs and locals are snake_case without a type prefix; arbitrary names (`prod_bucket`, `my_bucket`, `bucket123`) are
forbidden. Physical names are `<project>-<env>-<component>[-<qualifier>]`, built in `locals`; per-AZ resources append the AZ;
every taggable resource has a `Name` tag equal to its physical name. Tag keys are PascalCase.

**Terraform style**: Terraform `>= 1.11` (stable S3 lock); `for_each` over `count` (keys are stable identifiers, never list
indexes), `count` only for 0/1 toggles; `dynamic` blocks only for genuinely optional or repeated nested blocks; no hard-coded
accounts, regions or AZs; secrets never in source (`sensitive = true`); `moved` blocks for every rename; `depends_on` as a
last resort and commented; no `local-exec` or `null_resource` unless unavoidable.

**Lifecycle**: stateful resources expose a protection strategy (deletion protection, `force_destroy = false`); every
`ignore_changes` is commented with the system that owns the attribute; the README documents which inputs force replacement.

**Documentation**: each module README has, in order: purpose and non-goals, usage, resources and which are taggable, inputs
and outputs, mandatory tags, lifecycle notes (what forces replacement), cost notes.

**Maintainability**: one responsibility per module (split when two lifecycles are mixed); no copy-pasted logic between modules;
deprecate before removing.

## How the standard is enforced

The standard above is the contract in words. These are the parts the reviewer checks by code: each row is one rule of the
[catalog](checks.md), implemented by one function in [`rules/code_rules.py`](../tools/reviewer/rules/code_rules.py).

| The standard says | Rule | Function |
| --- | --- | --- |
| A capability lives in its module; roots do not declare it | `MODULE-001` | `resource_declared_outside_its_module` |
| A module has `versions.tf`, `variables.tf`, `outputs.tf` and `README.md` | `MODULE-002` | `module_missing_required_files` |
| The primary resource is `this`; no arbitrary names | `MODULE-003` | `resource_has_arbitrary_name` |
| No `type = any` | `MODULE-004` | `variable_typed_any` |
| Components live under their domain folder (`eks/`, `ec2/`, `elb/`) | `MODULE-005` | `component_outside_domain_folder` |
| EKS capacity comes from `eks/node-group`, never a raw Auto Scaling Group | `MODULE-006` | `eks_autoscaling_group_declared_directly` |
| Every taggable resource carries the mandatory tags | `TAGS-001` | `resource_missing_mandatory_tags` |
| A module exposes the `tags` and `extra_tags` variables | `TAGS-002` | `module_missing_tag_variables` |
| An Auto Scaling Group propagates the tags to its instances | `TAGS-003` | `autoscaling_group_does_not_propagate_tags` |
| No NAT gateway per zone outside protected roots | `COST-001` | `nat_gateway_per_zone_in_unprotected_root` |

The rest of the standard (documented variables and outputs, bounded provider versions, formatting) is checked by TFLint and
`terraform fmt`/`validate`, which are the authority for it; the style guidance (`for_each` over `count`, `moved` blocks, comments on
`ignore_changes`) is for the human reviewer.

