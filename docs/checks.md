# The checks

English · [Español](es/checks.md)

Every rule the reviewer enforces, in one place. The catalog itself is [`tools/rules/rules.yaml`](../tools/rules/rules.yaml): this table mirrors it.

A rule has an **ID** (`FAMILY-NUMBER`), a **severity**, and a **function** that implements it. The function is named after what it flags, and its docstring says which rule it is.

## The families

| Family | What it covers |
| --- | --- |
| `MODULE` | How modules are built, and what must not be built outside one. |
| `TAGS` | Every taggable AWS resource carries the mandatory tags. |
| `ROOT` | How a root is built: its layout, its files identical across environments, its environment and its tags. |
| `POLICY` | The values of a root's `inputs.yaml` against the project's policy. An environment deployed from the `main` branch (`terraform.environments` in `common.yaml`) is a production one. |
| `PLAN` | What Terraform will do to the infrastructure, and what it will cost. |

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
| `ROOT-001` | High | Root configuration does not follow its layout (only the listed files; no provider, version or backend in `main.tf`) | the code | `root_breaks_layout` |
| `ROOT-002` | High | A root configuration's files differ from its siblings | the code | `root_files_differ` |
| `ROOT-003` | High | Root is not assigned to an environment in `common.yaml` | the root's `inputs.yaml` | `root_not_in_an_environment` |
| `ROOT-004` | High | Root `tags` are invalid (missing owner or cost center, or sets project or environment) | the root's `inputs.yaml` | `root_tags_invalid` |
| `ROOT-005` | Medium | A module call in a root reshapes values with a `for`, a conditional or a function (`try`, `merge`, `lookup`...) | the code | `root_call_holds_logic` |
| `POLICY-001` | High | Production root does not meet a production requirement (HTTPS, database protection and snapshot, NAT per zone, 2+ database instances, `min_size >= 2`) | the root's `inputs.yaml` | `production_requirements_not_met` |
| `PLAN-001` | Critical | Plan destroys or replaces a stateful resource | the plan | `plan_destroys_stateful_resource` |
| `PLAN-002` | Medium | Infracost reports a large monthly increase | Infracost | `plan_cost_increase_above_threshold` |

- **Checks on the code** (`code_rules.py`) read the `.tf` files. The `repository contract` job runs them over the whole repository; the comment lists the findings in files and folders the PR touches.
- **Checks on a root's `inputs.yaml`** (`inputs_rules.py`) read the values a project gives to its modules. The policy is data: `POLICY-001` lists its requirements in `rules.yaml` (a dotted path into `inputs.yaml` and a test), and the environment names come from `common.yaml`, so another project changes the data and not the code.
- **Checks on the plan** (`plan_rules.py`) read the sanitized Terraform plan and the Infracost estimate of each affected root.

## How a rule becomes a verdict

`REQUEST_CHANGES` when a confirmed finding is **High** or **Critical**, or when an external check failed (`terraform fmt`, the Python checks (ruff, mypy), the tests, `validate`, TFLint, the repository contract). Checkov runs with `--soft-fail`: its findings show as a warning and do not block yet. Anything else is `PASS`; lower severities are still listed in the comment. `PLAN-001` is Critical in a root of a protected environment (`protected_environments` of the rule), and in every root of a PR into production.

## Add a rule

1. Add an entry to `rules.yaml`: `id`, `category`, `severity`, `check`, `title`, `explanation`, `recommendation`, plus the check's own parameters.
2. Write the function in `code_rules.py` (decorated with `@check("<name>")`) or in `plan_rules.py` (decorated with `@plan_check("<name>")`), named after what it flags.
3. Add its row to the table above, and to the table in [module-standard](module-standard.md) if it enforces the standard.
4. If the `check:` name has no function, the reviewer stops with an error: a rule is never skipped silently.

## What is deliberately not a rule

`terraform fmt` and `validate`, TFLint and Checkov are the authority for formatting, syntax, lint and generic security, and Infracost for prices. The rules above are only what those tools cannot know: module boundaries, naming, mandatory tags, root layout, and the correlation of the plan and the cost with this repository's own standards.

---

[← Previous: What each file is](files.md) · [README](../README.md) · [Next: Module standard →](module-standard.md)
