# The checks

[← README](../README.md) · English · [Español](es/checks.md)

Every rule the reviewer enforces, in one place. The catalog itself is [`tools/reviewer/rules/rules.yaml`](../tools/reviewer/rules/rules.yaml): this table mirrors it.

A rule has an **ID** (`FAMILY-NUMBER`), a **severity**, and a **function** that implements it. The function is named after what it flags, and its docstring says which rule it is.

## The families

| Family | What it covers |
| --- | --- |
| `MODULE` | How modules are built, and what must not be built outside one. |
| `TAGS` | Every taggable AWS resource carries the mandatory tags. |
| `ROOT` | The layout of a family of root configurations (opt-in with `terraform.conventions.layout` in `common.yaml`). |
| `COST` | Choices that cost more than needed. |
| `PLAN` | What Terraform will do to the infrastructure. |

## The rules

| Rule | Severity | What it flags | Reads | Function |
| --- | --- | --- | --- | --- |
| `MODULE-001` | High | Reusable capability implemented outside its module | the code | `resource_declared_outside_its_module` |
| `MODULE-002` | Medium | Module is missing required contract files | the code | `module_missing_required_files` |
| `MODULE-003` | Medium | Resource does not follow the `this` naming convention | the code | `resource_has_arbitrary_name` |
| `MODULE-004` | Medium | Variable uses `type = any` | the code | `variable_typed_any` |
| `MODULE-005` | Medium | Domain component placed outside its domain directory | the code | `component_outside_domain_folder` |
| `MODULE-006` | High | Auto Scaling Group managed directly for EKS | the code | `eks_autoscaling_group_declared_directly` |
| `TAGS-001` | High | Taggable resource does not receive mandatory tags | the code | `resource_missing_mandatory_tags` |
| `TAGS-002` | Medium | Module does not expose the mandatory-tag input contract | the code | `module_missing_tag_variables` |
| `TAGS-003` | High | Auto Scaling Group does not propagate mandatory tags | the code | `autoscaling_group_does_not_propagate_tags` |
| `ROOT-001` | High | Root configuration does not follow its layout *(opt-in)* | the code | `root_breaks_layout` |
| `ROOT-002` | High | A root configuration's files differ from its siblings *(opt-in)* | the code | `root_files_differ` |
| `COST-001` | Medium | NAT gateway per AZ in a non-protected configuration | the code | `nat_gateway_per_zone_in_unprotected_root` |
| `COST-002` | Medium | Infracost reports a large monthly increase | the plan / Infracost | `plan_cost_increase_above_threshold` |
| `PLAN-001` | Critical | Plan destroys or replaces a stateful resource | the plan / Infracost | `plan_destroys_stateful_resource` |

- **Checks on the code** (`code_rules.py`) read the `.tf` files. The `repository contract` job runs them over the whole repository; the comment lists the findings in files and folders the PR touches.
- **Checks on the plan** (`plan_rules.py`) read the sanitized Terraform plan and the Infracost estimate of each affected root.

## How a rule becomes a verdict

`REQUEST_CHANGES` when a confirmed finding is **High** or **Critical**, or when an external check failed (`terraform fmt`, `validate`, TFLint, the repository contract). Checkov runs with `--soft-fail`: its findings show as a warning and do not block yet. Anything else is `PASS`; lower severities are still listed in the comment. `PLAN-001` is Critical in a protected root, and in every root of a PR into production.

## Add a rule

1. Add an entry to `rules.yaml`: `id`, `category`, `severity`, `check`, `title`, `explanation`, `recommendation`, plus the check's own parameters.
2. Write the function in `code_rules.py` (decorated with `@check("<name>")`) or in `plan_rules.py` (decorated with `@plan_check("<name>")`), named after what it flags.
3. Add its row to the table above, and to the table in [module-standard](module-standard.md) if it enforces the standard.
4. If the `check:` name has no function, the reviewer stops with an error: a rule is never skipped silently.

## What is deliberately not a rule

`terraform fmt` and `validate`, TFLint and Checkov are the authority for formatting, syntax, lint and generic security, and Infracost for prices. The rules above are only what those tools cannot know: module boundaries, naming, mandatory tags, root layout, and the correlation of the plan and the cost with this repository's own standards.
