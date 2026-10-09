---
name: new-module
description: Create or rename a Terraform module in modules/ and leave the repository consistent (module files, reviewer rules, README, docs in both languages). Use when the user asks for a new module, a new capability or a module split.
---

Create the module following `CLAUDE.md` (conventions) and `docs/module-standard.md` (the contract). Ask first if any of this is unknown:
which capability, which resources, which inputs the consumer needs, the defaults, whether it holds state, and the domain folder.

Work through this list in order; do not stop at the code.

1. **Location.** `modules/<capability>`, or `modules/<domain>/<component>` for `eks`, `ec2`, `elb`. Never a top-level `eks-*`, `ec2-*`, `elb-*`.
2. **Files.** `versions.tf` (`required_version >= 1.11.0`, bounded provider range), `variables.tf`, `outputs.tf`, `README.md`; `main.tf`, `locals.tf`, `data.tf` as needed. No `inputs.yaml`.
3. **Inputs.** Typed, described, validated; never `type = any`; secure and cheap defaults. The call holds no logic, so resolve and default inside the module.
4. **Tags and names.** A `tags` object plus `extra_tags`; `locals.tags = merge(var.extra_tags, local.mandatory_tags)`; every taggable resource carries `Name`, `Environment`, `Owner`, `CostCenter`, `Project`, `ManagedBy`. The primary resource of a type is `this`.
5. **The rules know it** (`tools/rules/rules.yaml`): its resource types in the `capabilities` of `MODULE-001`; every taggable type in `taggable_types` of `TAGS-001`; every stateful type in `stateful_types` of `PLAN-001`.
6. **README.** Copy the structure of `modules/api-gateway/README.md`. The `## Usage` example must be valid: its `inputs.yaml` block uses the module's variable names and the call matches `variables.tf`. Check each name and type in the file; do not invent inputs.
7. **Test: every module has one.** `tests/terraform/<path with / and - as _>.tftest.hcl` (`modules/elb/alb` is `elb_alb.tftest.hcl`) with `mock_provider "aws" {}` and one `run` block per case, each with
   `module { source = "../../modules/<path>" }`. At least: a plan that works with the minimum inputs, and an input the module must reject (`expect_failures`); and, if the module resolves,
   defaults or picks something, one case for each. The name of each `run` is a sentence. Copy the shape of `tests/terraform/security_group.tftest.hcl`. If the mock invents a value the provider
   rejects (an ARN, for example), give that resource a valid one with `mock_resource`, as `elb_alb.tftest.hcl` does. If the module was in `PENDING` of `test_every_module_has_a_terraform_test.py`, remove it.
8. **Docs, both languages.** The module in the *Modules* table of `README.md` and `README.es.md`, and in the module tables of `docs/files.md` and `docs/es/files.md`.
9. **Verify.** `terraform fmt -recursive modules`, then `terraform init -backend=false` and `terraform validate` inside the module, and `terraform -chdir=tests/terraform init -backend=false` then `terraform -chdir=tests/terraform test`. Run them and report the output; the pipeline runs the tests from now on.

If a root should use the module, show its `inputs.yaml` block and call as a proposal; do not add it to `infra-example` without approval.
End with the git commands (see `CLAUDE.md`) and the branch the PR targets.
