---
name: new-root
description: Build infrastructure for a project from the modules - a new environment (dev, staging, prod...) or a new stack (a root with its own inputs.yaml). Use when the user wants to deploy something new, add an environment, or start a project that calls the modules.
---

A root is a folder with its own state that calls modules. Follow `CLAUDE.md` (the Roots conventions) and the model in `infra-example/dev/web-demo`. Say first which case it is.

**A new environment of an existing stack** (for example `staging` for `web-demo`):
1. Copy `infra-example/dev/web-demo` to `infra-example/<environment>/web-demo`. The `.tf` files stay identical (`ROOT-002` checks it); only `inputs.yaml` differs.
2. Give it its own values in `inputs.yaml`: CIDRs, sizes, names (`"${project}-${environment}-<component>"`), ports, `tags` with only `owner` and `cost_center`.
3. Register it in `common.yaml`: an entry under `terraform.environments` with its `branch`, its AWS `account` and its `roots`. Environments of one branch share its keys, so they name the same account.
4. Check the rules that now apply to it: `ROOT-003` (it is in an environment), `ROOT-001`/`ROOT-002` (its `roots` pattern in `rules.yaml`), and `POLICY-001` if it is deployed from `main`.

**A new stack** (a different set of components, for example `data-platform`):
1. Create `infra-example/<environment>/<stack>` (or the folder the project uses). Build it only from modules; a capability that has a module is never declared directly (`MODULE-001`). If no module fits, stop and use the `new-module` skill first.
2. Files: `main.tf` (reads `inputs.yaml` and `common.yaml`, defines `local.tags`; copy it from `web-demo`), one `.tf` per area (`network.tf`, `database.tf`...), `data.tf` for every `data` block, `outputs.tf`, `inputs.yaml`.
3. Calls hold no logic: they pass `local.inputs.*` as they are, with `tags = local.tags` and names completed by `templatestring(local.inputs.<x>.name, local.tags)`. If a module needs the caller to reshape a value, change the module, not the call.
4. `inputs.yaml`: block-style YAML, a `# ---- name ----` divider before each top-level block, no literal value left in the `.tf`.
5. Extend the rules: add the new stack's `roots` pattern, `files` and `identical` to `ROOT-001` and `ROOT-002`, and its requirements to `POLICY-001` if it needs them.

**For both:**
- **The AWS side is the owner's, by hand** (give the commands, never run them): the state bucket `<project>-tfstate-<account>-<region>` once per account and region (`docs/install.md`), and the branch's key secrets (`gh secret set`). Never write a key or an account id into a file other than the `account` in `common.yaml`.
- **Docs, both languages:** `infra-example/README.md` and `README.es.md` (the tree and the tables), `docs/files.md` and `docs/es/files.md` if there are new files.
- **Verify** in the new root: `terraform fmt -recursive`, `terraform init -backend=false`, `terraform validate`, and `terraform console` for `local.environment`, `local.tags` and one name. Then the reviewer on the repository with no findings.
- **Deploy** is never part of the change: the owner runs `terraform.yml` by hand, first as `plan`, after the PR is merged (`gh workflow run terraform.yml --ref <branch> -f mode=plan -f root=<root>`).

End with the git commands (see `CLAUDE.md`) and the branch the PR targets (`develop` for non-production, `main` for production).
